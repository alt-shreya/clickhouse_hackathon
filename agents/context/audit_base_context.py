"""
One-time (or on-change) audit pass over agent_control.context_layer.
Single LLM call. Input is the ~39 already-parsed atomic rows (a few KB of text)
-- never raw event rows. Output is written to agent_control.context_flags.

Token math: 39 short rows * ~40 tokens each ~= 1.5-2K input tokens, one call.
This is not the thing the "don't burn tokens" warning is about.
"""

import json
import re
import clickhouse_connect

AUDIT_PROMPT = """You are auditing a business context layer for an analytics system.
Below are atomic context rows (entity, key, value, value_type, source_table) for a
visa-application funnel product. Identify ONLY issues you can support from the text
itself. For each issue return: flag_type, entity, key, description.

flag_type must be one of:
- contradiction        (two rows conflict, e.g. same concept defined two ways)
- stale_metric         (a definition that looks outdated or superseded)
- missing_relationship (schema/columns imply a join or entity link not stated)
- ambiguous_definition (a term used but never concretely defined, e.g. an undefined field)

Respond with ONLY a JSON array of objects with keys:
flag_type, entity, key, description, conflicting_keys (array of "entity.key" strings, may be empty).
No prose, no markdown fences.

CONTEXT ROWS:
{rows_json}
"""


def fetch_current_rows(client):
    result = client.query("""
        SELECT entity, key, argMax(value, version) AS value,
               argMax(value_type, version) AS value_type,
               argMax(source_table, version) AS source_table
        FROM agent_control.context_layer
        GROUP BY entity, key
        HAVING argMax(change_type, version) != 'deprecation'
        ORDER BY entity, key
    """)
    return [dict(zip(result.column_names, row)) for row in result.result_rows]


def cross_check_against_schema(client, flags):
    """Verify any flag claiming a table/column doesn't exist, rather than
    trusting the LLM's claim. Cheap metadata-only query, no event rows."""
    existing = client.query("""
        SELECT table, name FROM system.columns WHERE database = 'atlys'
    """)
    existing_pairs = {(r[0], r[1]) for r in existing.result_rows}
    existing_tables = {t for t, _ in existing_pairs}

    verified = []
    for f in flags:
        flag_type = f.get("flag_type", "")
        entity = f.get("entity", "")
        
        if flag_type == "missing_relationship" and entity not in existing_tables:
            f["description"] = f.get("description", "") + " [UNVERIFIED: referenced table not found in system.columns -- confirm manually]"
        verified.append(f)
    return verified


def parse_llm_json(raw_text: str):
    """Safely extracts JSON even if the LLM wraps it in markdown blocks or extra whitespace."""
    cleaned = raw_text.strip()
    match = re.search(r'(\{.*\}|\[.*\])', cleaned, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    return json.loads(cleaned)



def run_audit(client, llm_call_fn):
    rows = fetch_current_rows(client)
    if not rows:
        print("No active context rows found to audit.")
        return []

    prompt = AUDIT_PROMPT.format(rows_json=json.dumps(rows, indent=2, default=str))

    # Pass span_name if llm_call_fn supports it for Langfuse tracking
    try:
        raw_response = llm_call_fn(prompt, span_name="context_audit")
    except TypeError:
        raw_response = llm_call_fn(prompt)

    # Use robust JSON extraction helper
    flags = parse_llm_json(raw_response)
    
    if not isinstance(flags, list):
        print(f"Warning: Expected JSON list from LLM, got {type(flags)}. Normalizing...")
        flags = [flags] if isinstance(flags, dict) else []

    flags = cross_check_against_schema(client, flags)

    insert_rows = []
    for f in flags:
        insert_rows.append([
            f.get("entity", ""),
            f.get("key", ""),
            f.get("flag_type", "ambiguous_definition"),
            f.get("description", ""),
            f.get("conflicting_keys", []),  # Populates conflicting_versions/keys if provided
            "open",
        ])

    if insert_rows:
        client.insert(
            "agent_control.context_flags",
            insert_rows,
            column_names=["entity", "key", "flag_type", "description", "conflicting_versions", "status"],
        )
    
    print(f"Audit complete: {len(flags)} flags written to agent_control.context_flags.")
    return flags


if __name__ == "__main__":
    # Test client connection wrapper
    client = clickhouse_connect.get_client(
        host="<your-service-host>", 
        username="<user>", 
        password="<password>", 
        database="atlys"
    )

    def llm_call_fn(prompt: str, span_name: str = "context_audit") -> str:
        # Mock wrapper: Replace this with your actual Anthropic call + Langfuse span
        raise NotImplementedError("Wire this function to your LLM completion provider.")

    run_audit(client, llm_call_fn)


