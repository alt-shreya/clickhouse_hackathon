"""
Instrumentation Agent
Turns feature specs into production-ready ClickHouse schemas.
Uses ContextAgent for base context, meta_context_registry for existing table metadata,
and OpenRouter LLM for intelligent schema generation.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import json
import re
import clickhouse_connect

from agents.tracing.agent import get_tracer



@dataclass
class ColumnSpec:
    """Column specification for a ClickHouse table."""
    name: str
    type: str
    description: str = ""
    nullable: bool = False
    low_cardinality: bool = False
    codec: str = ""
    
    def to_ch_type(self) -> str:
        """Convert to ClickHouse type string."""
        ch_type = self.type.strip()

        # Normalize any accidental double wrappers from upstream generation.
        while ch_type.startswith("Nullable(") and ch_type.endswith(")"):
            ch_type = ch_type[len("Nullable("):-1].strip()
        while ch_type.startswith("LowCardinality(") and ch_type.endswith(")"):
            ch_type = ch_type[len("LowCardinality("):-1].strip()

        # ClickHouse is strict about LowCardinality + Nullable nesting.
        # For this pipeline, keep nullable strings as plain Nullable(String)
        # and reserve LowCardinality for non-nullable scalar strings.
        if self.low_cardinality and ch_type.lower() == "string" and not self.nullable:
            ch_type = f"LowCardinality({ch_type})"
        if self.nullable:
            ch_type = f"Nullable({ch_type})"
        return ch_type
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TableSchema:
    """Represents a ClickHouse table schema."""
    name: str
    columns: List[ColumnSpec]
    engine: str = "MergeTree"
    partition_by: str = ""
    order_by: str = ""
    settings: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    kind: str = ""  # funnel, supporting, dimension, etc.
    related_tables: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    def to_ddl(self, database: str) -> str:
        """Generate CREATE TABLE DDL."""
        cols = []
        for col in self.columns:
            col_def = f"    {col.name} {col.to_ch_type()}"
            if col.description:
                col_def += f" COMMENT '{col.description}'"
            if col.codec:
                col_def += f" CODEC({col.codec})"
            cols.append(col_def)
        
        nl = "\n"
        comma_nl = ",\n"
        ddl = f"CREATE TABLE {database}.{self.name}\n(\n{comma_nl.join(cols)}\n)\n"
        ddl += f"ENGINE = {self.engine}"
        if self.partition_by:
            ddl += f"\nPARTITION BY {self.partition_by}"
        if self.order_by:
            order_expr = self.order_by
            if not order_expr.startswith("("):
                order_expr = f"({order_expr})"
            ddl += f"\nORDER BY {order_expr}"
        if self.settings:
            settings_str = ", ".join(f"{k}={v}" for k, v in self.settings.items())
            ddl += f"\nSETTINGS {settings_str}"
        ddl += ";"
        if self.description:
            ddl = f"-- {self.description}\n{ddl}"
        return ddl


@dataclass
class SpecAnalysis:
    """Result of analyzing a feature spec."""
    feature_name: str
    description: str
    entities: List[Dict[str, Any]]
    events: List[Dict[str, Any]]
    properties: Dict[str, Any]
    relationships: List[Dict[str, Any]]
    suggested_tables: List[Dict[str, Any]]
    raw_spec_md: str = ""
    raw_events_sample: List[Dict[str, Any]] = field(default_factory=list)


class InstrumentationAgent:
    """
    Agent that converts feature specs to ClickHouse schemas.
    
    Pipeline:
    1. Load context (base_context.md + meta_context_registry)
    2. Parse spec.md + events.ndjson
    3. Analyze with LLM to extract entities, events, relationships
    4. Generate ClickHouse schema with proper partitioning, ordering, codecs
    5. Validate against existing tables and best practices
    6. Emit DDL + register in meta_context_registry
    """
    
    def __init__(
        self,
        clickhouse_client=None,
        context_agent=None,
        openrouter_config=None,
        database: str = "atlys",
        registry_table: str = "meta_context_registry",
        control_db: str = "agent_control",
    ):
        self.client = clickhouse_client
        self.context_agent = context_agent
        self.openrouter_config = openrouter_config
        self.database = database
        self.registry_table = registry_table
        self.control_db = control_db
        
        # Generated schemas
        self.schemas: Dict[str, TableSchema] = {}
        
        # Cached context
        self._existing_tables: Dict[str, Any] = {}
        self._context_cache: Dict[str, Any] = {}
        
        # LLM client
        self._llm_client = None
        if openrouter_config and openrouter_config.enabled:
            self._llm_client = openrouter_config.get_client()
    
    # ============================================================
    # Context Loading
    # ============================================================
    
    def load_context(self) -> Dict[str, Any]:
        """Load all context: base_context.md + meta_context_registry + agent_control."""
        # 1. Base context from markdown
        if self.context_agent:
            self.context_agent.load_context()
            self._context_cache = self.context_agent.get_context_for_agent("instrumentation")
        
        # 2. Existing tables from registry
        if self.client:
            self._load_registry()
        
        # 3. Control flags (if any)
        if self.client:
            self._load_control_flags()
        
        return {
            "base_context": self._context_cache,
            "existing_tables": self._existing_tables,
            "control_flags": self._context_cache.get("control_flags", {}),
        }
    
    def _load_registry(self):
        """Load existing table metadata from meta_context_registry."""
        query = f"""
        SELECT 
            entity_name, entity_type, kind, description,
            columns, source_spec, ordering_key, partition_key,
            ttl_expression, related_entities, tags,
            version, is_current
        FROM {self.database}.{self.registry_table}
        WHERE is_current = 1
        """
        result = self.client.query(query)
        for row in result.result_rows:
            entity_name = row[0]
            self._existing_tables[entity_name] = {
                "entity_name": row[0],
                "entity_type": row[1],
                "kind": row[2],  # funnel, supporting
                "description": row[3],
                "columns": row[4],  # Array of column objects
                "source_spec": row[5],
                "ordering_key": row[6],
                "partition_key": row[7],
                "ttl_expression": row[8],
                "related_entities": row[9],
                "tags": row[10],
                "version": row[11],
                "is_current": row[12],
            }
    
    def _load_control_flags(self):
        """Load control flags from agent_control.context_flags."""
        try:
            query = f"SELECT flag_name, flag_value, description FROM {self.control_db}.context_flags"
            result = self.client.query(query)
            flags = {}
            for row in result.result_rows:
                flags[row[0]] = {"value": row[1], "description": row[2]}
            self._context_cache["control_flags"] = flags
        except Exception:
            pass  # Table might be empty or not exist
    
    def get_existing_table(self, name: str) -> Optional[Dict[str, Any]]:
        """Get existing table metadata by name."""
        return self._existing_tables.get(name)
    
    def get_all_existing_tables(self) -> Dict[str, Any]:
        """Get all existing table metadata."""
        return self._existing_tables
    
    def get_context_summary(self) -> str:
        """Get a text summary of all context for LLM prompts."""
        parts = []
        
        # Base context
        if self._context_cache:
            entities = self._context_cache.get("entities", {})
            metrics = self._context_cache.get("metrics", {})
            issues = self._context_cache.get("issues", [])
            
            parts.append("=== BASE CONTEXT (from base_context.md) ===")
            parts.append(f"Entities ({len(entities)}):")
            for name, e in entities.items():
                parts.append(f"  - {name}: {e.get('description', '')[:100]}")
                if e.get("tables"):
                    parts.append(f"    Tables: {', '.join(e['tables'])}")
                if e.get("key_columns"):
                    parts.append(f"    Key columns: {', '.join(e['key_columns'])}")
            
            parts.append(f"\nMetrics ({len(metrics)}):")
            for name, m in metrics.items():
                parts.append(f"  - {name}: {m.get('formula', '')[:100]}")
            
            parts.append(f"\nKnown Issues ({len(issues)}):")
            for issue in issues:
                parts.append(f"  - {issue.get('id', '')}: {issue.get('description', '')[:100]}")
        
        # Existing tables
        if self._existing_tables:
            parts.append("\n=== EXISTING TABLES (from meta_context_registry) ===")
            for name, t in self._existing_tables.items():
                parts.append(f"\nTable: {name} ({t['kind']})")
                parts.append(f"  Description: {t['description']}")
                parts.append(f"  Ordering: {t['ordering_key']}")
                parts.append(f"  Partition: {t['partition_key']}")
                parts.append(f"  Related: {', '.join(t['related_entities'])}")
                parts.append(f"  Tags: {', '.join(t['tags'])}")
                parts.append("  Columns:")
                for col in t["columns"]:
                    nullable = " nullable" if col.get("name", "").endswith("_id") else ""
                    parts.append(f"    - {col['name']}: {col['type']}{nullable} — {col.get('description', '')}")
        
        return "\n".join(parts)
    
    # ============================================================
    # Spec Parsing
    # ============================================================
    
    def parse_spec(self, spec_dir: Path) -> SpecAnalysis:
        """Parse spec.md and events.ndjson from a spec directory."""
        with get_tracer().trace_span("instrumentation.parse_spec", input_data={"spec_dir": str(spec_dir)}):
            spec_file = spec_dir / "spec.md"
            events_file = spec_dir / "events.ndjson"
            
            # Read spec.md
            spec_md = ""
            if spec_file.exists():
                spec_md = spec_file.read_text()
            
            # Read events.ndjson (sample first 10)
            events_sample = []
            if events_file.exists():
                with open(events_file) as f:
                    for i, line in enumerate(f):
                        if i >= 10:
                            break
                        line = line.strip()
                        if line:
                            try:
                                events_sample.append(json.loads(line))
                            except json.JSONDecodeError:
                                pass
            
            # Extract key info from spec.md using LLM
            analysis = self._analyze_with_llm(spec_md, events_sample)
            
            # Add raw content
            analysis.raw_spec_md = spec_md
            analysis.raw_events_sample = events_sample
            
            return analysis

    
    def _analyze_with_llm(self, spec_md: str, events_sample: List[Dict]) -> SpecAnalysis:
        """Use LLM to analyze spec and extract structured info."""
        if not self._llm_client:
            # Fallback: basic parsing
            return self._basic_parse(spec_md, events_sample)
        
        prompt = self._build_analysis_prompt(spec_md, events_sample)
        
        try:
            response = self._llm_client.chat.completions.create(
                model=self.openrouter_config.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )
            
            content = (response.choices[0].message.content or "").strip()

            # Strip code fences if the model added them.
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                # Recover the first JSON object if the model added stray text
                start = content.find("{")
                end = content.rfind("}")
                if start == -1 or end == -1 or end <= start:
                    raise
                parsed = json.loads(content[start:end + 1])
            
            return SpecAnalysis(
                feature_name=parsed.get("feature_name", "unknown"),
                description=parsed.get("description", ""),
                entities=parsed.get("entities", []),
                events=parsed.get("events", []),
                properties=parsed.get("properties", {}),
                relationships=parsed.get("relationships", []),
                suggested_tables=parsed.get("suggested_tables", []),
            )
        except Exception as e:
            print(f"LLM analysis failed: {e}, falling back to basic parsing")
            return self._basic_parse(spec_md, events_sample)
    
    def _get_system_prompt(self) -> str:
        return """You are an expert ClickHouse schema designer for Atlys, a digital visa platform.
Analyze feature specifications and extract structured information for schema generation.

Return JSON with:
- feature_name: short kebab-case name
- description: one-sentence summary
- entities: list of {name, description, properties[], identifiers[]}
- events: list of {name, description, trigger, entity_refs[], properties[]}
- properties: dict of property_name -> {type, description, examples[]}
- relationships: list of {from, to, type, description}
- suggested_tables: list of {name, kind (funnel/supporting/dimension), description, columns[], partition_by, order_by, related_tables[]}

Focus on:
- Reusing existing patterns from Atlys (user_id, application_id, timestamp envelope)
- Proper ClickHouse types (LowCardinality for enums, Nullable appropriately)
- Monthly partitioning by timestamp
- Ordering by (id, timestamp, user_id) for event tables
- Distinguishing funnel vs supporting tables"""

    def _build_analysis_prompt(self, spec_md: str, events_sample: List[Dict]) -> str:
        context = self.get_context_summary()
        
        events_json = json.dumps(events_sample, indent=2, default=str) if events_sample else "[]"
        
        return f"""Analyze this feature specification and extract schema requirements.

{context}

=== FEATURE SPEC ===
{spec_md}

=== EVENTS SAMPLE (first 10) ===
{events_json}

Extract all entities, events, properties, and relationships. Suggest new table designs that follow Atlys patterns."""

    def _basic_parse(self, spec_md: str, events_sample: List[Dict]) -> SpecAnalysis:
        """Basic regex-based parsing as fallback."""
        # Extract feature name from directory or first heading
        feature_name = "unknown"
        match = re.search(r"^#\s+(.+)$", spec_md, re.MULTILINE)
        if match:
            feature_name = match.group(1).lower().replace(" ", "-").replace("_", "-")
        
        # Extract event names from spec.md
        event_names = []
        # Look for backtick event names like `express_checkout_shown` - only those with underscores that look like event types
        event_matches = re.findall(r"`(\w+_+\w+)`", spec_md)
        # Filter: only keep ones that look like event names (not field names like device_type, geoip_country_code)
        # Event names typically have 2+ underscores or match known patterns
        for m in event_matches:
            # Skip common field names that appear in backticks
            if m not in ["device_type", "geoip_country_code", "app_version", "user_id", "application_id", 
                         "saved_method_type", "otp_attempts", "otp_success", "shown_amount", "latency_ms"]:
                event_names.append(m)
        # Also look for event: "name" pattern
        event_matches2 = re.findall(r'event["\s:]+(\w+_+\w+)', spec_md, re.IGNORECASE)
        event_names.extend(event_matches2)
        # From events sample - extract actual event field values ONLY
        for e in events_sample:
            if "event" in e:
                event_names.append(e["event"])
        
        # Deduplicate
        event_names = list(dict.fromkeys(event_names))
        
        # Build entities from event properties (not creating tables for each property)
        entities = []
        events = []
        
        # Infer event properties from sample
        event_properties = {}
        for e in events_sample:
            event_type = e.get("event", "unknown")
            for key, value in e.items():
                if key in ["user_id", "application_id", "timestamp", "id", "event"]:
                    continue
                prop_type = "String"
                if isinstance(value, bool):
                    prop_type = "UInt8"
                elif isinstance(value, int):
                    prop_type = "Int64"
                elif isinstance(value, float):
                    prop_type = "Float64"
                if event_type not in event_properties:
                    event_properties[event_type] = {}
                event_properties[event_type][key] = prop_type
        
        # Add entities for each event's properties
        for event_type, props in event_properties.items():
            for prop_name, prop_type in props.items():
                entities.append({
                    "name": f"{event_type}.{prop_name}",
                    "description": f"Property {prop_name} of {event_type}",
                    "properties": [{"name": prop_name, "type": prop_type}],
                    "identifiers": []
                })
        
        # Create suggested tables from event names (one table per event type)
        suggested_tables = []
        for ename in event_names:
            # Convert to snake_case table name
            table_name = ename.lower().replace("-", "_")
            # Determine kind from context or default to supporting
            kind = "supporting"
            # Check if it's a funnel event based on base context
            funnel_keywords = ["destination_card_clicked", "application_started", "document_uploaded", "purchase_completed"]
            if any(fk in table_name for fk in funnel_keywords):
                kind = "funnel"
            
            suggested_tables.append({
                "name": table_name,
                "kind": kind,
                "description": f"Event table for {ename}",
            })
        
        return SpecAnalysis(
            feature_name=feature_name,
            description=spec_md[:500] if spec_md else "Parsed from spec",
            entities=entities,
            events=[{"name": e, "description": f"Event: {e}"} for e in event_names],
            properties={},
            relationships=[],
            suggested_tables=suggested_tables,
        )
    
    # ============================================================
    # Schema Generation
    # ============================================================
    
    def generate_schema(self, analysis: SpecAnalysis) -> List[TableSchema]:
        """Generate ClickHouse schemas from spec analysis."""
        with get_tracer().trace_span("instrumentation.generate_schema", input_data={"feature": analysis.feature_name}):
            if not self._llm_client:
                return self._basic_generate(analysis)
            
            prompt = self._build_generation_prompt(analysis)
            
            try:
                response = self._llm_client.chat.completions.create(
                    model=self.openrouter_config.model,
                    messages=[
                        {"role": "system", "content": self._get_generation_system_prompt()},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=6000,
                    response_format={"type": "json_object"},
                )
                
                content = response.choices[0].message.content.strip()
                # Strip markdown formatting if present
                if content.startswith("```json"):
                    content = content[7:]
                elif content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                
                parsed = json.loads(content)
                
                return self._parse_generated_schemas(parsed)
            except Exception as e:
                print(f"LLM generation failed: {e}, falling back to basic generation")
                return self._basic_generate(analysis)
    
    def _get_generation_system_prompt(self) -> str:
        return """You are an expert ClickHouse schema designer for Atlys.
Generate production-ready table schemas from analyzed feature specifications.

CRITICAL: Return ONLY valid JSON. Do not include markdown blocks, explanations, or any other text.

Return JSON with:
- tables: list of table schemas, each with:
  - name: table name (snake_case)
  - kind: "funnel" or "supporting" or "dimension"
  - description: one-line purpose
  - columns: list of {name, type, description, nullable, low_cardinality, codec}
  - partition_by: partition expression (e.g., "toYYYYMM(timestamp)")
  - order_by: ordering key (e.g., "id, timestamp, user_id")
  - engine: "MergeTree" (default)
  - settings: dict of engine settings
  - related_tables: list of related table names
  - tags: list of tags

Atlys conventions:
- All event tables have envelope: id UUID, timestamp DateTime, user_id String, application_id Nullable(String)
- Partition by toYYYYMM(timestamp)
- Order by (id, timestamp, user_id) for event tables
- Use LowCardinality for enum-like strings (device_type, visa_type, etc.)
- Use Nullable for optional fields
- Funnel tables: destination_card_clicked -> application_started -> document_uploaded -> purchase_completed
- Supporting tables: search, scroll, auth, pay_now clicks
- Reuse existing column names and types where possible"""

    def _build_generation_prompt(self, analysis: SpecAnalysis) -> str:
        context = self.get_context_summary()
        
        return f"""Generate ClickHouse table schemas for this feature.

{context}

=== SPEC ANALYSIS ===
Feature: {analysis.feature_name}
Description: {analysis.description}

Entities:
{json.dumps(analysis.entities, indent=2)}

Events:
{json.dumps(analysis.events, indent=2)}

Properties:
{json.dumps(analysis.properties, indent=2)}

Relationships:
{json.dumps(analysis.relationships, indent=2)}

Raw Events Sample:
{json.dumps(analysis.raw_events_sample[:3], indent=2, default=str)}

Generate schemas for any NEW tables needed. Also suggest modifications to existing tables if the spec requires it.
Focus on: proper ClickHouse types, partitioning, ordering, codecs, and integration with existing funnel."""

    def _parse_generated_schemas(self, parsed: Dict) -> List[TableSchema]:
        """Parse LLM-generated schema JSON into TableSchema objects."""
        schemas = []
        for t in parsed.get("tables", []):
            columns = []
            for col in t.get("columns", []):
                columns.append(ColumnSpec(
                    name=col["name"],
                    type=col["type"],
                    description=col.get("description", ""),
                    nullable=col.get("nullable", False),
                    low_cardinality=col.get("low_cardinality", False),
                    codec=col.get("codec", ""),
                ))
            
            schema = TableSchema(
                name=t["name"],
                columns=columns,
                engine=t.get("engine", "MergeTree"),
                partition_by=t.get("partition_by", ""),
                order_by=t.get("order_by", ""),
                settings=t.get("settings", {}),
                description=t.get("description", ""),
                kind=t.get("kind", ""),
                related_tables=t.get("related_tables", []),
                tags=t.get("tags", []),
            )
            schemas.append(schema)
            self.schemas[schema.name] = schema
        
        return schemas
    
    def _basic_generate(self, analysis: SpecAnalysis) -> List[TableSchema]:
        """Basic schema generation fallback."""
        # Create one table per suggested table or inferred from events
        schemas = []
        
        # If no suggested tables, create one based on feature name
        if not analysis.suggested_tables and analysis.events:
            for event in analysis.events:
                event_name = event.get("name", "").lower().replace(" ", "_")
                if event_name:
                    analysis.suggested_tables.append({
                        "name": event_name,
                        "kind": "supporting",
                        "description": event.get("description", ""),
                    })
        
        for st in analysis.suggested_tables:
            columns = self._build_basic_columns(st, analysis)
            schema = TableSchema(
                name=st["name"],
                columns=columns,
                partition_by="toYYYYMM(timestamp)",
                order_by="(id, timestamp, user_id)",
                description=st.get("description", ""),
                kind=st.get("kind", "supporting"),
                related_tables=st.get("related_tables", []),
                tags=st.get("tags", []),
            )
            schemas.append(schema)
            self.schemas[schema.name] = schema
        
        return schemas
    
    def _build_basic_columns(self, table_spec: Dict, analysis: SpecAnalysis) -> List[ColumnSpec]:
        """Build basic columns for a table."""
        # Standard envelope
        columns = [
            ColumnSpec(name="id", type="UUID", description="Event ID"),
            ColumnSpec(name="timestamp", type="DateTime", description="Event timestamp"),
            ColumnSpec(name="user_id", type="String", description="User identifier"),
            ColumnSpec(name="application_id", type="String", description="Application ID", nullable=True),
            ColumnSpec(name="app_session_id", type="String", description="App session ID", nullable=True),
            ColumnSpec(name="device", type="String", description="Device model", nullable=True, low_cardinality=True),
            ColumnSpec(name="device_type", type="String", description="Device type", nullable=True, low_cardinality=True),
            ColumnSpec(name="os", type="String", description="Operating system", nullable=True, low_cardinality=True),
            ColumnSpec(name="app_version", type="String", description="App version", nullable=True),
            ColumnSpec(name="client_lib", type="String", description="Client library", nullable=True),
            ColumnSpec(name="geoip_country_code", type="String", description="Country code", nullable=True, low_cardinality=True),
            ColumnSpec(name="geoip_subdivision_1_code", type="String", description="Subdivision code", nullable=True),
            ColumnSpec(name="city", type="String", description="City", nullable=True),
            ColumnSpec(name="client_ip", type="String", description="Client IP", nullable=True),
            ColumnSpec(name="latitude", type="Float64", description="Latitude", nullable=True),
            ColumnSpec(name="longitude", type="Float64", description="Longitude", nullable=True),
            ColumnSpec(name="locale", type="String", description="Locale", nullable=True),
            ColumnSpec(name="language", type="String", description="Language", nullable=True),
            ColumnSpec(name="funnel_type", type="String", description="Funnel variant", nullable=True, low_cardinality=True),
            ColumnSpec(name="co_travelers", type="UInt8", description="Co-travelers count", nullable=True),
            ColumnSpec(name="is_guest", type="UInt8", description="Is guest user", nullable=True),
            ColumnSpec(name="is_referral", type="UInt8", description="Is referral", nullable=True),
            ColumnSpec(name="is_enterprise", type="UInt8", description="Is enterprise", nullable=True),
            ColumnSpec(name="gclid", type="String", description="Google click ID", nullable=True),
            ColumnSpec(name="fbclid", type="String", description="Facebook click ID", nullable=True),
            ColumnSpec(name="gad_source", type="String", description="Google Ads source", nullable=True),
            ColumnSpec(name="citizenship", type="String", description="User citizenship", nullable=True, low_cardinality=True),
            ColumnSpec(name="destination", type="String", description="Destination country", nullable=True, low_cardinality=True),
            ColumnSpec(name="is_back_filled", type="UInt8", description="Backfilled event", nullable=True),
            ColumnSpec(name="duplicate_id", type="String", description="Deduplication ID", nullable=True),
        ]
        
        # Add event-specific columns from analysis
        for entity in analysis.entities:
            # Only add properties that belong to this specific event table
            entity_name = entity.get("name", "")
            if "." in entity_name:
                entity_event = entity_name.split(".")[0].lower().replace("-", "_")
                if entity_event != table_spec["name"]:
                    continue
                    
            for prop in entity.get("properties", []):
                col_name = prop.get("name", "").lower().replace(" ", "_")
                col_type = prop.get("type", "String")
                # Map common types
                type_map = {
                    "string": "String",
                    "int": "Int64",
                    "integer": "Int64",
                    "float": "Float64",
                    "boolean": "UInt8",
                    "bool": "UInt8",
                    "uuid": "UUID",
                    "datetime": "DateTime",
                }
                ch_type = type_map.get(col_type.lower(), col_type)
                
                # Check if already in envelope
                if not any(c.name == col_name for c in columns):
                    columns.append(ColumnSpec(
                        name=col_name,
                        type=ch_type,
                        description=f"From {entity.get('name', 'spec')}",
                        nullable=True,
                        low_cardinality=False if col_name in {"application_id", "user_id", "id"} else (
                            ch_type == "String" and "type" in col_name.lower()
                        ),
                    ))
        
        return columns
    
    # ============================================================
    # Validation
    # ============================================================
    
    def validate_schema(self, schema: TableSchema) -> List[str]:
        """Validate schema against best practices and existing tables."""
        issues = []
        
        # 1. Check required envelope columns
        envelope_cols = {"id", "timestamp", "user_id", "application_id"}
        schema_cols = {c.name for c in schema.columns}
        missing = envelope_cols - schema_cols
        if missing:
            issues.append(f"Missing envelope columns: {missing}")
        
        # 2. Check partition_by
        if not schema.partition_by:
            issues.append("Missing partition_by (recommend: toYYYYMM(timestamp))")
        elif "timestamp" not in schema.partition_by:
            issues.append("partition_by should reference timestamp")
        
        # 3. Check order_by
        if not schema.order_by:
            issues.append("Missing order_by (recommend: id, timestamp, user_id)")
        elif "id" not in schema.order_by or "timestamp" not in schema.order_by:
            issues.append("order_by should include id and timestamp")
        
        # 4. Check for duplicate column names
        col_names = [c.name for c in schema.columns]
        dupes = set([x for x in col_names if col_names.count(x) > 1])
        if dupes:
            issues.append(f"Duplicate column names: {dupes}")
        
        # 5. Check against existing tables for conflicts
        for existing_name, existing in self._existing_tables.items():
            if existing_name == schema.name:
                issues.append(f"Table {schema.name} already exists in registry (version {existing.get('version', '?')})")
        
        # 6. Check LowCardinality usage
        for col in schema.columns:
            if col.low_cardinality and col.type not in ("String", "LowCardinality(String)"):
                issues.append(f"LowCardinality only works with String types: {col.name}")
        
        return issues
    
    def validate_all(self) -> Dict[str, List[str]]:
        """Validate all generated schemas."""
        return {name: self.validate_schema(schema) for name, schema in self.schemas.items()}
    
    # ============================================================
    # Registry Operations
    # ============================================================
    
    def register_table(self, schema: TableSchema, version: int = 1) -> bool:
        """Register a new table schema in meta_context_registry."""
        if not self.client:
            print("No ClickHouse client, skipping registry")
            return False
        
        # Convert columns to JSON array format
        columns_json = json.dumps([{
            "name": c.name,
            "type": c.type,
            "description": c.description,
            "nullable": c.nullable,
            "low_cardinality": c.low_cardinality,
            "codec": c.codec,
        } for c in schema.columns])
        
        insert_query = f"""
        INSERT INTO {self.database}.{self.registry_table} 
        (entity_name, entity_type, kind, description, columns, source_spec, 
         ordering_key, partition_key, ttl_expression, related_entities, tags,
         version, is_current, created_at, updated_at)
        VALUES
        """
        
        values = f"""(
            '{schema.name}', 'table', '{schema.kind}', 
            '{schema.description.replace("'", "''")}', 
            {columns_json},
            'generated',
            '{schema.order_by}', '{schema.partition_by}', '',
            {json.dumps(schema.related_tables)}, {json.dumps(schema.tags)},
            {version}, 1, now(), now()
        )"""
        
        try:
            self.client.command(insert_query + values)
            print(f"Registered {schema.name} in meta_context_registry")
            return True
        except Exception as e:
            print(f"Failed to register {schema.name}: {e}")
            return False
    
    def register_all(self) -> Dict[str, bool]:
        """Register all generated schemas."""
        return {name: self.register_table(schema) for name, schema in self.schemas.items()}
    
    # ============================================================
    # Full Pipeline
    # ============================================================
    
    def process_spec(self, spec_dir: Path) -> List[TableSchema]:
        """Full pipeline: spec -> analysis -> schemas -> validation -> register."""
        with get_tracer().trace_span("instrumentation.process_spec", input_data={"spec_dir": str(spec_dir)}):
            print(f"Processing spec: {spec_dir}")
            
            # Reset schemas for this spec
            self.schemas = {}
            
            # 1. Load context
            self.load_context()
            print(f"  Loaded {len(self._existing_tables)} existing tables")
            
            # 2. Parse spec
            analysis = self.parse_spec(spec_dir)
            print(f"  Analyzed: {analysis.feature_name} ({len(analysis.entities)} entities, {len(analysis.events)} events)")
            
            # 3. Generate schemas
            schemas = self.generate_schema(analysis)
            print(f"  Generated {len(schemas)} table schemas")
            
            # 4. Validate
            all_issues = self.validate_all()
            for name, issues in all_issues.items():
                if issues:
                    print(f"  Validation warnings for {name}: {issues}")
                else:
                    print(f"  {name}: OK")
            
            # 5. Register (optional - uncomment to enable)
            # self.register_all()
            
            return schemas
    
    def emit_ddl(self, database: str = None, output_path: Path = None) -> str:
        """Emit all schemas as DDL statements."""
        db = database or self.database
        ddl_parts = []
        for schema in self.schemas.values():
            ddl_parts.append(schema.to_ddl(db))
        nl = "\n"
        full_ddl = f"{nl}{nl}".join(ddl_parts)
        if output_path:
            output_path.write_text(full_ddl)
        return full_ddl
    
    def get_schema(self, name: str) -> Optional[TableSchema]:
        """Get a generated schema by name."""
        return self.schemas.get(name)
