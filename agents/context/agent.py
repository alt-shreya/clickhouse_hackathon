"""
Context Agent
Maintains living context layer, feeds it to other agents.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import json
import re

from agents.tracing.agent import get_tracer



@dataclass
class EntityDefinition:
    """Business entity definition from context layer."""
    name: str
    description: str
    tables: List[str] = field(default_factory=list)
    key_columns: List[str] = field(default_factory=list)
    relationships: Dict[str, str] = field(default_factory=dict)  # entity -> relationship type


@dataclass
class MetricDefinition:
    """Business metric definition with formula."""
    name: str
    description: str
    formula: str
    unit: str = ""
    depends_on: List[str] = field(default_factory=list)


@dataclass
class KnownIssue:
    """Known data quality or definition issue."""
    id: str
    description: str
    affected_tables: List[str]
    severity: str = "medium"
    workaround: str = ""
    status: str = "open"  # open, acknowledged, fixed


class ContextAgent:
    """Agent that maintains and serves the living business context layer."""
    
    def __init__(self, context_path: str = None, clickhouse_client=None):
        self.context_path = context_path or "base_context.md"
        self.client = clickhouse_client
        self.entities: Dict[str, EntityDefinition] = {}
        self.metrics: Dict[str, MetricDefinition] = {}
        self.issues: Dict[str, KnownIssue] = {}
        self.raw_context: str = ""
        self._last_parsed: Optional[str] = None
    
    def load_context(self) -> str:
        """Load and parse the context file."""
        with get_tracer().trace_span("context.load_context", input_data={"path": self.context_path}):
            path = Path(self.context_path)
            if not path.exists():
                raise FileNotFoundError(f"Context file not found: {self.context_path}")
            
            self.raw_context = path.read_text()
            self._parse_context()
            self.sync_to_db()
            return self.raw_context
    
    def _parse_context(self):
        """Parse base_context.md into structured data."""
        content = self.raw_context
        
        # Extract entities section
        entity_section = self._extract_section(content, "## 2. Entity definitions", "## 3. The eight raw event tables")
        if entity_section:
            self._parse_entities(entity_section)
        
        # Extract metrics section
        metric_section = self._extract_section(content, "## 4. Metric definitions", "## 5. Known-issues log")
        if metric_section:
            self._parse_metrics(metric_section)
        
        # Extract issues section
        issues_section = self._extract_section(content, "## 5. Known-issues log", "## 6. Entity relationships")
        if issues_section:
            self._parse_issues(issues_section)
    
    def _extract_section(self, content: str, start_marker: str, end_marker: Optional[str]) -> Optional[str]:
        """Extract a section between two markers."""
        start_idx = content.find(start_marker)
        if start_idx == -1:
            return None
        start_idx = content.find("\n", start_idx) + 1
        
        if end_marker:
            end_idx = content.find(end_marker, start_idx)
            if end_idx == -1:
                return content[start_idx:]
            return content[start_idx:end_idx]
        return content[start_idx:]
    
    def _parse_entities(self, section: str):
        """Parse entity definitions from markdown."""
        # Pattern: **Entity Name** — description\n\n**Tables:** table1, table2\n**Key Columns:** col1, col2
        # Split by double asterisks at start of line
        entity_blocks = re.split(r'\n\*\*([^*]+)\*\*', section)
        
        # First element is before first entity, skip it
        for i in range(1, len(entity_blocks), 2):
            name = entity_blocks[i].strip()
            body = entity_blocks[i + 1] if i + 1 < len(entity_blocks) else ""
            
            tables = []
            key_cols = []
            relationships = {}
            
            tables_match = re.search(r"\*\*Tables:\*\*\s*(.+)", body)
            if tables_match:
                tables = [t.strip() for t in tables_match.group(1).split(",")]
            
            keys_match = re.search(r"\*\*Key Columns:\*\*\s*(.+)", body)
            if keys_match:
                key_cols = [k.strip() for k in keys_match.group(1).split(",")]
            
            rel_match = re.search(r"\*\*Relationships:\*\*\s*(.+)", body)
            if rel_match:
                for rel in rel_match.group(1).split(","):
                    parts = rel.split("->")
                    if len(parts) == 2:
                        relationships[parts[0].strip()] = parts[1].strip()
            
            # Description is everything before **Tables:
            desc = body.split("**Tables:**")[0].strip()
            # Clean up the leading em dash
            if desc.startswith("—"):
                desc = desc[1:].strip()
            
            self.entities[name] = EntityDefinition(
                name=name,
                description=desc,
                tables=tables,
                key_columns=key_cols,
                relationships=relationships
            )
    
    def _parse_metrics(self, section: str):
        """Parse metric definitions from markdown."""
        # Pattern: **Metric Name** = formula. Description.
        # **Unit:** unit
        # **Depends On:** dep1, dep2
        metric_blocks = re.split(r'\n\*\*([^*]+)\*\*\s*=', section)
        
        for i in range(1, len(metric_blocks), 2):
            name = metric_blocks[i].strip()
            body = "=" + metric_blocks[i + 1] if i + 1 < len(metric_blocks) else ""
            
            formula = ""
            unit = ""
            depends = []
            
            # Extract formula (everything before first period or newline)
            formula_match = re.search(r"^(.+?)(?:\.|\n)", body)
            if formula_match:
                formula = formula_match.group(1).strip()
            
            unit_match = re.search(r"\*\*Unit:\*\*\s*(.+)", body)
            if unit_match:
                unit = unit_match.group(1).strip()
            
            dep_match = re.search(r"\*\*Depends On:\*\*\s*(.+)", body)
            if dep_match:
                depends = [d.strip() for d in dep_match.group(1).split(",")]
            
            # Description is the rest
            desc = body.split(formula)[-1].strip() if formula in body else body
            desc = desc.lstrip(". ").strip()
            
            self.metrics[name] = MetricDefinition(
                name=name,
                description=desc,
                formula=formula,
                unit=unit,
                depends_on=depends
            )
    
    def _parse_issues(self, section: str):
        """Parse known issues from markdown."""
        # Pattern: 1. **K1 — Title.** Description. **Affected Tables:** table1, table2
        # **Severity:** severity
        # **Workaround:** workaround
        issue_blocks = re.split(r'\n\d+\.\s+\*\*([^*]+)\*\*', section)
        
        for i in range(1, len(issue_blocks), 2):
            header = issue_blocks[i].strip()
            body = issue_blocks[i + 1] if i + 1 < len(issue_blocks) else ""
            
            # Extract issue ID and title from header like "K1 — iOS WebKit OTP autofill regression."
            parts = header.split("—", 1)
            issue_id = parts[0].strip().lower().replace(" ", "-")
            title = parts[1].strip() if len(parts) > 1 else ""
            
            affected = []
            severity = "medium"
            workaround = ""
            
            affected_match = re.search(r"\*\*Affected Tables:\*\*\s*(.+)", body)
            if affected_match:
                affected = [t.strip() for t in affected_match.group(1).split(",")]
            
            sev_match = re.search(r"\*\*Severity:\*\*\s*(.+)", body)
            if sev_match:
                severity = sev_match.group(1).strip().lower()
            
            work_match = re.search(r"\*\*Workaround:\*\*\s*(.+)", body)
            if work_match:
                workaround = work_match.group(1).strip()
            
            # Description is everything before **Affected Tables:
            desc = body.split("**Affected Tables:**")[0].strip()
            # Combine title and description
            if title:
                desc = f"{title}. {desc}"
            
            self.issues[issue_id] = KnownIssue(
                id=issue_id,
                description=desc,
                affected_tables=affected,
                severity=severity,
                workaround=workaround
            )
    
    def get_entity(self, name: str) -> Optional[EntityDefinition]:
        """Get entity definition by name (fuzzy match)."""
        name_lower = name.lower()
        for key, entity in self.entities.items():
            if key.lower() == name_lower or name_lower in key.lower():
                return entity
        return None
    
    def get_metric(self, name: str) -> Optional[MetricDefinition]:
        """Get metric definition by name."""
        name_lower = name.lower()
        for key, metric in self.metrics.items():
            if key.lower() == name_lower:
                return metric
        return None
    
    def get_issues_for_table(self, table: str) -> List[KnownIssue]:
        """Get all known issues affecting a table."""
        return [issue for issue in self.issues.values() if table in issue.affected_tables]
    
    def get_context_for_agent(self, agent_type: str) -> Dict[str, Any]:
        """Get relevant context subset for a specific agent."""
        if agent_type == "instrumentation":
            return {
                "entities": {k: {"name": v.name, "tables": v.tables, "key_columns": v.key_columns} 
                           for k, v in self.entities.items()},
                "metrics": {k: {"name": v.name, "formula": v.formula} for k, v in self.metrics.items()},
                "issues": [{"id": v.id, "description": v.description, "tables": v.affected_tables} 
                          for v in self.issues.values()],
            }
        elif agent_type == "analytics":
            return {
                "metrics": {k: {"name": v.name, "description": v.description, "formula": v.formula, "unit": v.unit} 
                           for k, v in self.metrics.items()},
                "issues": [{"id": v.id, "description": v.description, "tables": v.affected_tables, "severity": v.severity} 
                          for v in self.issues.values()],
            }
        elif agent_type == "context":
            return {
                "entities": {k: v.__dict__ for k, v in self.entities.items()},
                "metrics": {k: v.__dict__ for k, v in self.metrics.items()},
                "issues": {k: v.__dict__ for k, v in self.issues.items()},
            }
        return {}
    
    def validate_context(self) -> List[str]:
        """Validate context for consistency issues."""
        warnings = []
        
        # Check for tables referenced in entities but not in DDL
        # Check for metrics that reference non-existent entities
        # Check for circular dependencies in metrics
        
        for metric in self.metrics.values():
            for dep in metric.depends_on:
                if dep not in self.metrics:
                    warnings.append(f"Metric '{metric.name}' depends on unknown metric '{dep}'")
        
        return warnings
    
    def export_context(self, output_path: Path, format: str = "json"):
        """Export context to file."""
        data = {
            "entities": {k: v.__dict__ for k, v in self.entities.items()},
            "metrics": {k: v.__dict__ for k, v in self.metrics.items()},
            "issues": {k: v.__dict__ for k, v in self.issues.items()},
        }
        if format == "json":
            output_path.write_text(json.dumps(data, indent=2, default=str))

    def sync_to_db(self):
        """Sync parsed context to agent_control ClickHouse DB."""
        if not self.client:
            return

        with get_tracer().trace_span("context.sync_to_db"):
            from datetime import datetime
            now = datetime.now()
            
            # Sync context_layer
            layer_data = []
            
            version = 1
            source_table = 'base_context.md'
            updated_by = 'ContextAgent'
            change_type = 'initial_sync'
            confidence = 1.0
            
            for name, entity in self.entities.items():
                layer_data.append((
                    version, 'entity', name,
                    json.dumps({"description": entity.description, "tables": entity.tables, "key_columns": entity.key_columns, "relationships": entity.relationships}),
                    'json', source_table, updated_by, change_type, None, confidence, now
                ))
            for name, metric in self.metrics.items():
                layer_data.append((
                    version, 'metric', name,
                    json.dumps({"description": metric.description, "formula": metric.formula, "unit": metric.unit, "depends_on": metric.depends_on}),
                    'json', source_table, updated_by, change_type, None, confidence, now
                ))
            for i_id, issue in self.issues.items():
                layer_data.append((
                    version, 'issue', i_id,
                    json.dumps({"description": issue.description, "affected_tables": issue.affected_tables, "severity": issue.severity, "workaround": issue.workaround, "status": issue.status}),
                    'json', source_table, updated_by, change_type, None, confidence, now
                ))
            
            if layer_data:
                self.client.insert(
                    'agent_control.context_layer',
                    layer_data,
                    column_names=['version', 'entity', 'key', 'value', 'value_type', 'source_table', 'updated_by', 'change_type', 'supersedes_version', 'confidence', 'updated_at']
                )
            
            # Sync context_flags
            flags_data = [
                ('system', 'last_context_update', 'update', now.isoformat(), [], 'open', now, None),
                ('system', 'context_version', 'version', str(version), [], 'open', now, None)
            ]
            self.client.insert(
                'agent_control.context_flags',
                flags_data,
                column_names=['entity', 'key', 'flag_type', 'description', 'conflicting_versions', 'status', 'detected_at', 'resolved_at']
            )