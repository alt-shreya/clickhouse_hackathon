"""
ContextAgent -- the single object every other agent talks to for context.
Fixed interface: load_v1, get_latest_context, update_context, run_audit, resolve_flag.
"""

import json
import re
import clickhouse_connect
from load_base_context import ROWS, build_insert_rows
from audit_base_context import fetch_current_rows, cross_check_against_schema, AUDIT_PROMPT


UPDATE_PROMPT = """A new ClickHouse table has been created for a feature spec.
Given its DDL and the spec description, produce TWO separate lists:

1. "schema_comments": one short semantic description per column, plus one for
   the table's overall role -- this is Tier 1, schema-native metadata, applied
   as native COMMENT ON TABLE/COLUMN statements. Purely descriptive facts about
   what a field captures.
2. "business_rules": ONLY include an entry here if the spec implies something
   that is NOT just "what a column means" -- e.g. a new metric formula, a new
   known-issue-style caveat, or a new join relationship to an existing table.
   Leave this empty if nothing qualifies; most new tables won't need one.

Respond as JSON: {{"schema_comments": {{"table": "<desc>", "<col>": "<desc>", ...}},
"business_rules": [{{"key": "...", "value": "...", "value_type": "metric_definition|business_rule|entity_relationship"}}]}}
No prose, no markdown fences.

SPEC: {source_spec}
DDL:
{schema_ddl}
"""

RESOLVE_PROMPT = """You are resolving an open context flag in an analytics system.
Flag Description: {description}
Current Related Context Rows:
{conflicting_rows}

Provide a single, corrected context value that unifies or supersedes these rules.
Respond in JSON: {{"resolved_value": "...", "resolution_notes": "..."}}
No prose, no markdown fences.
"""


def parse_llm_json(raw_text: str):
    """Safely extracts JSON even if the LLM wraps it in markdown blocks or extra whitespace."""
    cleaned = raw_text.strip()
    match = re.search(r'(\{.*\}|\[.*\])', cleaned, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    return json.loads(cleaned)


class ContextAgent:
    def __init__(self, client, llm_call_fn):
        self.client = client
        self.llm_call_fn = llm_call_fn  # Wrapped in Langfuse span at call sites

    def load_v1(self) -> int:
        """Initializes Tier 2 base context into agent_control.context_layer."""
        records = build_insert_rows(ROWS)
        self.client.insert(
            "agent_control.context_layer",
            [list(r.values()) for r in records],
            column_names=list(records[0].keys()),
        )
        return len(records)

    def get_latest_context(self, entities: list[str] | None = None) -> dict:
        """Returns a unified view merging both context tiers:
        - Tier 1: Native COMMENTs on atlys.* tables/columns (metadata)
        - Tier 2: agent_control.context_layer (metrics, known issues, joins)
        - Active Flags: Open warnings for the Analytics Agent
        """
        tier2 = self._get_tier2(entities)
        tier1 = self._get_tier1(entities)
        flags = self._open_flags(entities)
        max_version = max((r["version"] for r in tier2), default=0)
        return {
            "schema_context": tier1,     # Table/column comments from system.columns/tables
            "business_context": tier2,   # Versioned rows: metrics/known-issues/joins
            "flags": flags,              # Open contradictions or ambiguities
            "context_version": max_version,
        }

    def _get_tier2(self, entities: list[str] | None) -> list[dict]:
        where = ""
        if entities:
            in_list = ",".join(f"'{e.replace('\'', '\'\'')}'" for e in entities)
            where = f"WHERE entity IN ({in_list})"
        query = f"""
            SELECT entity, key, argMax(value, version) AS value,
                   argMax(value_type, version) AS value_type,
                   max(version) AS version
            FROM agent_control.context_layer
            {where}
            GROUP BY entity, key
            HAVING argMax(change_type, version) != 'deprecation'
            ORDER BY entity, key
        """
        result = self.client.query(query)
        return [dict(zip(result.column_names, r)) for r in result.result_rows]

    def _get_tier1(self, entities: list[str] | None) -> dict:
        table_filter = ""
        col_filter = ""
        if entities:
            in_list = ",".join(f"'{e.replace('\'', '\'\'')}'" for e in entities)
            table_filter = f"AND name IN ({in_list})"
            col_filter = f"AND table IN ({in_list})"

        tables = self.client.query(f"""
            SELECT name AS entity, comment
            FROM system.tables
            WHERE database = 'atlys' AND comment != '' {table_filter}
        """)
        columns = self.client.query(f"""
            SELECT table AS entity, name AS column, comment
            FROM system.columns
            WHERE database = 'atlys' AND comment != '' {col_filter}
        """)
        return {
            "tables": [dict(zip(tables.column_names, r)) for r in tables.result_rows],
            "columns": [dict(zip(columns.column_names, r)) for r in columns.result_rows],
        }

    def _open_flags(self, entities: list[str] | None) -> list[dict]:
        where = "WHERE status = 'open'"
        if entities:
            in_list = ",".join(f"'{e.replace('\'', '\'\'')}'" for e in entities)
            where += f" AND entity IN ({in_list})"
        result = self.client.query(f"""
            SELECT flag_id, entity, key, flag_type, description
            FROM agent_control.context_flags {where}
        """)
        return [dict(zip(result.column_names, r)) for r in result.result_rows]

    def run_audit(self, scope: list[str] | None = None) -> list[dict]:
        if scope is None:
            print("WARNING: run_audit() called with scope=None -- auditing ENTIRE context layer.")
        
        rows = fetch_current_rows(self.client) if scope is None else self._get_tier2(entities=scope)
        if not rows:
            return []

        prompt = AUDIT_PROMPT.format(rows_json=json.dumps(rows, indent=2, default=str))
        
        try:
            raw = self.llm_call_fn(prompt, span_name="context_audit")
        except TypeError:
            raw = self.llm_call_fn(prompt)

        flags = parse_llm_json(raw)
        if not isinstance(flags, list):
            flags = [flags] if isinstance(flags, dict) else []

        flags = cross_check_against_schema(self.client, flags)

        if flags:
            self.client.insert(
                "agent_control.context_flags",
                [[f.get("entity", ""), f.get("key", ""), f.get("flag_type", "ambiguous_definition"),
                  f.get("description", ""), f.get("conflicting_keys", []), "open"] for f in flags],
                column_names=["entity", "key", "flag_type", "description",
                              "conflicting_versions", "status"],
            )
        return flags

    def update_context(self, new_table: str, schema_ddl: str, source_spec: str) -> int | None:
        prompt = UPDATE_PROMPT.format(source_spec=source_spec, schema_ddl=schema_ddl)
        
        try:
            raw = self.llm_call_fn(prompt, span_name="context_update")
        except TypeError:
            raw = self.llm_call_fn(prompt)

        parsed = parse_llm_json(raw)

        # --- Tier 1: Native ClickHouse Comments ---
        schema_comments = parsed.get("schema_comments", {})
        for field, desc in schema_comments.items():
            desc_escaped = str(desc).replace("'", "''")
            if field == "table":
                self.client.command(f"ALTER TABLE atlys.{new_table} MODIFY COMMENT '{desc_escaped}'")
            else:
                self.client.command(f"ALTER TABLE atlys.{new_table} COMMENT COLUMN {field} '{desc_escaped}'")

        # --- Tier 2: Business Rules ---
        business_rules = parsed.get("business_rules", [])
        next_version = None
        if business_rules:
            current = {(r["entity"], r["key"]): r for r in self._get_tier2(None)}
            next_version = max((r["version"] for r in current.values()), default=1) + 1
            insert_rows = []
            for nr in business_rules:
                key = (new_table, nr["key"])
                existing = current.get(key)
                change_type = "correction" if (existing and existing["value"] != nr["value"]) else "insert"
                supersedes = existing["version"] if change_type == "correction" else None
                insert_rows.append([
                    next_version, new_table, nr["key"], str(nr["value"]),
                    nr.get("value_type", "business_rule"),
                    new_table, "context_agent_llm", change_type, supersedes, 1.0,
                ])
            self.client.insert(
                "agent_control.context_layer",
                insert_rows,
                column_names=["version", "entity", "key", "value", "value_type",
                              "source_table", "updated_by", "change_type",
                              "supersedes_version", "confidence"],
            )

        # Re-audit new scope
        self.run_audit(scope=[new_table])
        return next_version

    def resolve_flag(self, flag_id: str, entity: str, key: str) -> None:
        """Resolves an open flag by generating a corrected Tier 2 rule and updating flag status."""
        flag = self.client.query(
            f"SELECT description FROM agent_control.context_flags WHERE flag_id = '{flag_id}' AND status = 'open'"
        ).result_rows
        if not flag:
            return

        conflicting_rows = self._get_tier2(entities=[entity])
        prompt = RESOLVE_PROMPT.format(description=flag[0][0], conflicting_rows=json.dumps(conflicting_rows))
        
        try:
            raw = self.llm_call_fn(prompt, span_name="context_resolve")
        except TypeError:
            raw = self.llm_call_fn(prompt)

        res = parse_llm_json(raw)
        resolved_value = res.get("resolved_value", "")

        if resolved_value:
            latest_v = max([r["version"] for r in conflicting_rows], default=1) + 1
            self.client.insert(
                "agent_control.context_layer",
                [[latest_v, entity, key, resolved_value, "business_rule", entity, "context_agent_resolve", "correction", latest_v - 1, 1.0]],
                column_names=["version", "entity", "key", "value", "value_type", "source_table", "updated_by", "change_type", "supersedes_version", "confidence"]
            )

        self.client.command(
            f"ALTER TABLE agent_control.context_flags UPDATE status = 'resolved', resolved_at = now() WHERE flag_id = '{flag_id}'"
        )


if __name__ == "__main__":
    client = clickhouse_connect.get_client(
        host="<your-service-host>", username="<user>", password="<password>", database="atlys",
    )

    def llm_call_fn(prompt: str, span_name: str = "test") -> str:
        raise NotImplementedError("Wire to Anthropic / OpenAI API call")

    agent = ContextAgent(client, llm_call_fn)
    print("ContextAgent initialized successfully.")