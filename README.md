# Atlys Agent Pipeline — Click-a-thon 2026

A system of three agents on ClickHouse that turns a feature spec into a production
schema, loads its sample events, and produces PM-readable insights:

- **Instrumentation Agent** (`agents/instrumentation/`) — feature spec → ClickHouse
  table schemas (DDL + a daily segment-rollup materialized view), executed and
  registered in `atlys.meta_context_registry`.
- **Analytics Agent** (`agents/analytics/`) — sequential funnel + segment analysis
  (via `windowFunnel`, not independent per-table counts) over both the core funnel
  and the spec's own new tables, plus LLM narrative insights that answer the
  spec's own "Questions the PM will ask".
- **Context Agent** (`agents/context/`) — a two-tier living context layer: native
  ClickHouse `COMMENT`s on `atlys.*` tables/columns (Tier 1, schema-native facts)
  plus a versioned `agent_control.context_layer` table (Tier 2, metrics/known
  issues/join map), with an LLM audit pass that surfaces contradictions/gaps
  into `agent_control.context_flags`.
- **Tracing** (`agents/tracing/`) — Langfuse spans/generations across all three
  agents, with a local JSONL fallback if Langfuse isn't configured.
- **Visualization** (`agents/visualization/dashboard_builder.py`) — a self-contained
  HTML dashboard per spec run.

All three agents share one LLM provider (OpenRouter, OpenAI-compatible) — see
`agents/config.py:make_llm_call_fn()`.

## Setup

1. **Python deps**: `pip install -r requirements.txt`
2. **Copy `.env.example` to `.env`** and fill in:
   - `CLICKHOUSE_HOST` / `CLICKHOUSE_USER` / `CLICKHOUSE_PASSWORD` (ClickHouse Cloud service)
   - `OPENROUTER_API_KEY` (get one at https://openrouter.ai/keys) — without this,
     every agent still runs, but falls back to rule-based logic instead of LLM
     reasoning (schema generation, narrative insights, context audit all degrade
     gracefully rather than crashing).
   - `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` (optional, for tracing)
3. **Load the base dataset** (8 existing funnel/engagement tables, ~2.5M rows) into
   your ClickHouse Cloud service per the challenge package's `data/load.sh`.
4. **Control-plane tables** (`agent_control.context_layer`, `agent_control.context_flags`,
   `atlys.meta_context_registry`) are created automatically by `main.py` on first
   run via `agents/setup.py:ensure_control_tables()` (`CREATE TABLE IF NOT EXISTS`,
   idempotent). No manual step needed.
5. **Challenge specs**: fetch `specs/<name>/{spec.md,events.ndjson}` from the
   challenge repo into a local `specs/` directory (gitignored — these are large
   and spec-provider-specific, not checked in).

## Running the pipeline

```bash
python main.py specs/01_express_checkout
```

This runs Context → Instrumentation → Analytics → Visualization end to end and
writes, into the spec directory:
- `generated_schema.sql` — the DDL record (tables + materialized view)
- `insight_summary.md` — the Analytics Agent's markdown insights
- `dashboard.html` — a self-contained visual dashboard

## Notes

- `meta_context_registry.columns` is `Array(Tuple(name, type, description))` —
  registration writes must match this shape exactly (see
  `InstrumentationAgent.register_table()`); a raw JSON string does not parse.
- `agent_control.context_flags.conflicting_versions` is `Array(String)` (holds
  `"entity.key"` identifiers, not version numbers).
- `ContextAgent.run_audit()` dedups against already-open flags for the same
  `(entity, key, flag_type)` before inserting, so re-running the pipeline on an
  unchanged context layer doesn't pile up duplicate flags.
