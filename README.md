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
- **Context Agent** (`agents/context/`) — a living business-context layer stored as
  ONE whole Markdown document per version in `analytics_context.business_context`
  (`doc_id`, `content`, `version`, `changelog_summary`, `updated_at`; a
  ReplacingMergeTree keyed on `doc_id` -- every change INSERTs a new version rather
  than mutating a row, so the table is also the audit trail). Seeded from
  `base_context.md`; auto-documents new tables under its "Auto-instrumented tables"
  section as InstrumentationAgent creates them; a deterministic freshness check
  (does every registered table still exist?) plus an LLM pass surface
  contradictions/gaps/obsolete facts into its "Open flags" section.
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
   - `ANTHROPIC_API_KEY` (preferred LLM provider -- see `agents/config.py:AnthropicConfig`,
     default model `claude-haiku-4-5-20251001`) or `OPENROUTER_API_KEY` (fallback if
     Anthropic isn't set). Without either, every agent still runs, but falls back to
     rule-based logic instead of LLM reasoning (schema generation, narrative insights,
     context audit all degrade gracefully rather than crashing).
   - `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` (optional, for tracing)
3. **Load the base dataset** (8 existing funnel/engagement tables, ~2.5M rows) into
   your ClickHouse Cloud service per the challenge package's `data/load.sh`.
4. **Control-plane tables** (`analytics_context.business_context`,
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
- `analytics_context.business_context` never gets mutated in place -- every
  change (seed, auto-documented table, audit flag, resolved flag) is a new
  `INSERT` with `version = previous + 1`; readers always
  `ORDER BY version DESC LIMIT 1` rather than relying on background-merge
  dedup. See `agents/context/agent.py` module docstring.
- `ContextAgent.run_audit()` dedups against already-open flags for the same
  `(entity, key, flag_type)` before inserting, so re-running the pipeline on an
  unchanged context layer doesn't pile up duplicate flags.
