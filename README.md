# Granule Gang

## Atlys Track

## Project name

Feature spec in, ClickHouse schema and PM-ready insight out — three agents, one
pipeline.

## Team Members
- Krishna @cybraia
- Shreya @alt-shreya

## What it does

Atlys Shrugged takes a raw feature spec (a markdown doc plus a sample events file) and
runs it through three cooperating agents: an **Instrumentation Agent** that designs
and executes the ClickHouse DDL for the new feature, an **Analytics Agent** that
runs sequenced funnel and segment analysis over both the new tables and the
existing funnel and writes a PM-readable insight report, and a **Context Agent**
that keeps a single living business-context document up to date as new tables get
instrumented and flags anything that goes stale or contradictory. Every run is
traced end to end in Langfuse, and each spec produces a self-contained HTML
dashboard alongside its generated schema and insight summary — so a team can go
from "here's a new feature spec" to "here's the schema, the dashboard, and what it
means" without anyone hand-writing SQL or a changelog.

## Hosted Demo

_TODO: add the live, hosted demo link here (mandatory for submission)._

## Demo Video

_TODO: add the 2–3 minute recorded demo video link here (mandatory for submission)._

## Architecture

Atlys Shrugged is three agents plus a shared context layer, run sequentially by
`main.py` for a single spec directory: **Context → Instrumentation → Analytics →
Visualization**.

- **Instrumentation Agent** (`agents/instrumentation/`) reads a feature spec and
  generates ClickHouse table DDL plus a daily segment-rollup materialized view,
  executes it against the live ClickHouse Cloud service, and registers the new
  tables' schema in `atlys.meta_context_registry`.
- **Analytics Agent** (`agents/analytics/`) hands off from Instrumentation once
  the new tables exist. It runs sequenced funnel analysis (`windowFunnel`, not
  independent per-table counts) across both the core funnel and the spec's new
  tables, then generates LLM narrative insights that directly answer the spec's
  own "Questions the PM will ask."
- **Context Agent** (`agents/context/`) runs both before and after the other two:
  it seeds/reads the current business-context document going in, and after
  Instrumentation creates new tables, it auto-documents them under an
  "Auto-instrumented tables" section. A deterministic freshness check (does every
  registered table still exist?) plus an LLM pass surface contradictions, gaps,
  and obsolete facts into an "Open flags" section.

**Where the context layer lives, and why:** the whole business-context document is
stored as **one Markdown blob per version** in a ClickHouse table,
`analytics_context.business_context` (`doc_id`, `content`, `version`,
`changelog_summary`, `updated_at`), a `ReplacingMergeTree` keyed on `doc_id`. Every
change — the initial seed, an auto-documented table, a new audit flag, a resolved
flag — is a new `INSERT` with `version = previous + 1` rather than a mutation.
That makes the table double as its own audit trail: readers always
`ORDER BY version DESC LIMIT 1` to get current state, but the full history of how
the context evolved is queryable directly, in the same store as the data it
describes, with no separate file store or vector DB to keep in sync. We chose a
ClickHouse table over a file on disk specifically so context history survives
independent of the repo and is queryable the same way the data is.

**Langfuse tracing:** all three agents emit spans/generations through a shared
tracer in `agents/tracing/`, so a single spec run produces one trace showing the
Context Agent's read, the Instrumentation Agent's DDL generation and execution,
the Analytics Agent's funnel queries and narrative generation, and the Context
Agent's post-run audit — in call order, with LLM prompts/completions attached. If
Langfuse isn't configured (no keys in `.env`), the same spans fall back to a local
JSONL file so the pipeline never depends on external tracing to run.

**LLM provider(s):** every agent calls through one shared entry point,
`agents/config.py:make_llm_call_fn()`. The primary provider is **Anthropic**
(`claude-haiku-4-5-20251001` by default) for fast, cheap structured generation
across schema design, narrative insights, and the context audit; **OpenRouter** is
a configured fallback if only that key is set. If neither key is present, every
agent still runs end to end but degrades to rule-based logic instead of LLM
reasoning, rather than crashing — deliberately, so the pipeline is demo-able even
without API keys configured.

## How we built it

**Stack:** Python, ClickHouse Cloud (via the `clickhouse-connect` client),
Anthropic/OpenRouter for LLM calls, Langfuse for tracing, and a self-contained
HTML/JS dashboard builder (`agents/visualization/dashboard_builder.py`) with no
external frontend framework.

**Sample analysis — quarterly & monthly funnel and revenue.** Three worked,
hand-run queries against the live base dataset (as of 2026-08-02), in the same
"CTEs down to a handful of meaningful rows" style the Analytics Agent's
`nl_to_sql()` few-shot examples use (`agents/analytics/agent.py`,
`_GOOD_QUERY_EXAMPLES`). Kept here as a reproducible reference for what
"PM-readable insight" looks like end to end — query, then result.

**Read the Q3 2026 / July 2026 rows in every table below as incomplete, not
anomalous** — see the callout after the tables.

### 1. Quarterly session → purchase conversion rate

Unions the four funnel tables per `app_session_id`, per quarter, and marks a
session `has_purchased` if it ever fires `purchase_completed` — a presence check
via `max(CASE ...)`, not a sequenced `windowFunnel()`, since the question is "did
this session convert at all," not "in what order."

```sql
WITH
    quarterly_sessions AS (
        SELECT
            toStartOfQuarter(timestamp) AS quarter_start,
            app_session_id,
            max(CASE WHEN _table = 'purchase_completed' THEN 1 ELSE 0 END) AS has_purchased
        FROM (
            SELECT app_session_id, timestamp, 'destination_card_clicked' AS _table FROM atlys.destination_card_clicked WHERE timestamp IS NOT NULL AND app_session_id != '' AND app_session_id IS NOT NULL
            UNION ALL
            SELECT app_session_id, timestamp, 'application_started' AS _table FROM atlys.application_started WHERE timestamp IS NOT NULL AND app_session_id != '' AND app_session_id IS NOT NULL
            UNION ALL
            SELECT app_session_id, timestamp, 'document_uploaded' AS _table FROM atlys.document_uploaded WHERE timestamp IS NOT NULL AND app_session_id != '' AND app_session_id IS NOT NULL
            UNION ALL
            SELECT app_session_id, timestamp, 'purchase_completed' AS _table FROM atlys.purchase_completed WHERE timestamp IS NOT NULL AND app_session_id != '' AND app_session_id IS NOT NULL
        )
        GROUP BY quarter_start, app_session_id
    )
SELECT
    quarter_start,
    uniq(app_session_id) AS total_sessions,
    sum(has_purchased) AS completed_purchases,
    round(sum(has_purchased) * 100.0 / nullIf(uniq(app_session_id), 0), 4) AS conversion_rate_pct
FROM quarterly_sessions
GROUP BY quarter_start
ORDER BY quarter_start ASC;
```

| quarter_start | total_sessions | completed_purchases | conversion_rate_pct |
|---|---:|---:|---:|
| 2026-01-01 | 440,496 | 3,228 | 0.7328% |
| 2026-04-01 | 560,520 | 3,824 | 0.6822% |
| 2026-07-01 | 14 | 2 | 14.2857% |

### 2. Quarterly revenue (currency-normalized) + applications started

Sums `purchase_completed.value` per native `currency`, converts every currency to
USD with a fixed rate table, then joins in `application_started` volume per
quarter to compute revenue per conversion. All rows share
`currency_group = 'USD (All Currencies Converted)'` (omitted from the table below
as constant).

```sql
WITH
    currency_subtotals AS (
        SELECT
            toStartOfQuarter(timestamp) AS quarter_start,
            coalesce(currency, 'UNKNOWN') AS currency,
            sum(coalesce(value, 0)) AS native_sum,
            count() AS conversion_count
        FROM atlys.purchase_completed
        WHERE timestamp IS NOT NULL
        GROUP BY quarter_start, currency
    ),
    normalized_to_usd AS (
        SELECT
            quarter_start,
            'USD (All Currencies Converted)' AS currency_group,
            sum(
                CASE currency
                    WHEN 'USD' THEN native_sum
                    WHEN 'INR' THEN native_sum * 0.012
                    WHEN 'AED' THEN native_sum * 0.272
                    WHEN 'GBP' THEN native_sum * 1.28
                    WHEN 'AUD' THEN native_sum * 0.65
                    WHEN 'SAR' THEN native_sum * 0.267
                    WHEN 'QAR' THEN native_sum * 0.274
                    WHEN 'OMR' THEN native_sum * 2.60
                    WHEN 'SGD' THEN native_sum * 0.75
                    ELSE native_sum * 1.0
                END
            ) AS total_converted_revenue_usd,
            sum(conversion_count) AS total_conversions
        FROM currency_subtotals
        GROUP BY quarter_start
    ),
    quarterly_applications AS (
        SELECT toStartOfQuarter(timestamp) AS quarter_start, count() AS applications_started_count
        FROM atlys.application_started
        WHERE timestamp IS NOT NULL
        GROUP BY quarter_start
    )
SELECT
    COALESCE(n.quarter_start, a.quarter_start) AS quarter_start,
    n.currency_group,
    n.total_converted_revenue_usd,
    n.total_conversions,
    round(n.total_converted_revenue_usd / nullIf(n.total_conversions, 0), 2) AS revenue_per_conversion,
    a.applications_started_count
FROM normalized_to_usd AS n
FULL OUTER JOIN quarterly_applications AS a ON n.quarter_start = a.quarter_start
ORDER BY quarter_start ASC;
```

| quarter_start | total_converted_revenue_usd | total_conversions | revenue_per_conversion | applications_started_count |
|---|---:|---:|---:|---:|
| 2026-01-01 | $207,380.92 | 3,228 | $64.24 | 68,089 |
| 2026-04-01 | $243,651.67 | 3,824 | $63.72 | 86,315 |
| 2026-07-01 | $89.78 | 2 | $44.89 | 9 |

### 3. Monthly revenue (currency-normalized) + applications started

Same shape as (2), bucketed by `toStartOfMonth` instead of `toStartOfQuarter`.

```sql
WITH
    currency_subtotals AS (
        SELECT
            toStartOfMonth(timestamp) AS month_start,
            coalesce(currency, 'UNKNOWN') AS currency,
            sum(coalesce(value, 0)) AS native_sum,
            count() AS conversion_count
        FROM atlys.purchase_completed
        WHERE timestamp IS NOT NULL
        GROUP BY month_start, currency
    ),
    normalized_to_usd AS (
        SELECT
            month_start,
            'USD (All Currencies Converted)' AS currency_group,
            sum(
                CASE currency
                    WHEN 'USD' THEN native_sum
                    WHEN 'INR' THEN native_sum * 0.012
                    WHEN 'AED' THEN native_sum * 0.272
                    WHEN 'GBP' THEN native_sum * 1.28
                    WHEN 'AUD' THEN native_sum * 0.65
                    WHEN 'SAR' THEN native_sum * 0.267
                    WHEN 'QAR' THEN native_sum * 0.274
                    WHEN 'OMR' THEN native_sum * 2.60
                    WHEN 'SGD' THEN native_sum * 0.75
                    ELSE native_sum * 1.0
                END
            ) AS total_converted_revenue_usd,
            sum(conversion_count) AS total_conversions
        FROM currency_subtotals
        GROUP BY month_start
    ),
    monthly_applications AS (
        SELECT toStartOfMonth(timestamp) AS month_start, count() AS applications_started_count
        FROM atlys.application_started
        WHERE timestamp IS NOT NULL
        GROUP BY month_start
    )
SELECT
    COALESCE(n.month_start, a.month_start) AS month_start,
    n.currency_group,
    n.total_converted_revenue_usd,
    n.total_conversions,
    round(n.total_converted_revenue_usd / nullIf(n.total_conversions, 0), 2) AS revenue_per_conversion,
    a.applications_started_count
FROM normalized_to_usd AS n
FULL OUTER JOIN monthly_applications AS a ON n.month_start = a.month_start
ORDER BY month_start ASC;
```

| month_start | total_converted_revenue_usd | total_conversions | revenue_per_conversion | applications_started_count |
|---|---:|---:|---:|---:|
| 2026-01-01 | $68,675.07 | 1,060 | $64.79 | 21,580 |
| 2026-02-01 | $62,935.26 | 1,001 | $62.87 | 21,211 |
| 2026-03-01 | $75,770.59 | 1,167 | $64.93 | 25,298 |
| 2026-04-01 | $84,247.20 | 1,290 | $65.31 | 26,280 |
| 2026-05-01 | $84,172.00 | 1,332 | $63.19 | 29,665 |
| 2026-06-01 | $75,232.52 | 1,202 | $62.59 | 30,370 |
| 2026-07-01 | $89.78 | 2 | $44.89 | 9 |

**Reading these numbers:** Q1 → Q2 2026 session volume grew ~27% (440k → 561k)
with applications started up a matching ~27% (68k → 86k) and revenue per
conversion essentially flat (~$64); conversion rate held steady around 0.7%. The
2026-07-01 row in every table above is **not** a real 14%-conversion,
$44.89-revenue-per-conversion quarter/month — it's `toStartOfQuarter`/
`toStartOfMonth` bucketing the handful of rows that exist for July 2026 so far
(this dataset's "now" trails the wall-clock date this repo was written on,
2026-08-02). A bucket with 2 conversions swings wildly on tiny-sample noise. **Any
dashboard or agent-generated insight that buckets by calendar period must either
exclude the in-progress period or flag it as partial** — otherwise a correct query
silently produces a misleading PM-facing anomaly.

**Implementation notes:**

- **In-progress calendar buckets read as false anomalies.** The current
  quarter/month at query time will always show a session/conversion count far
  below prior periods, because it's partial — see the July 2026 rows above. The
  Analytics Agent's narrative insights, and any dashboard built on
  `toStartOfQuarter`/`toStartOfMonth`/`toDate` grouping, filter out or explicitly
  caveat the current, still-accumulating bucket rather than reporting its skewed
  rate/average at face value.
- `meta_context_registry.columns` is `Array(Tuple(name, type, description))` —
  registration writes must match this shape exactly (see
  `InstrumentationAgent.register_table()`); a raw JSON string does not parse.
- `analytics_context.business_context` never gets mutated in place — every
  change (seed, auto-documented table, audit flag, resolved flag) is a new
  `INSERT` with `version = previous + 1`; readers always
  `ORDER BY version DESC LIMIT 1` rather than relying on background-merge dedup.
  See `agents/context/agent.py` module docstring.
- `ContextAgent.run_audit()` dedups against already-open flags for the same
  `(entity, key, flag_type)` before inserting, so re-running the pipeline on an
  unchanged context layer doesn't pile up duplicate flags.

## How to run it

1. **Python deps**: `pip install -r requirements.txt`
2. **Copy `.env.example` to `.env`** and fill in:
   - `CLICKHOUSE_HOST` / `CLICKHOUSE_USER` / `CLICKHOUSE_PASSWORD` (ClickHouse Cloud service)
   - `ANTHROPIC_API_KEY` (preferred LLM provider — see `agents/config.py:AnthropicConfig`,
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
6. **Run the pipeline**:

   ```bash
   python main.py specs/01_express_checkout
   ```

   This runs Context → Instrumentation → Analytics → Visualization end to end and
   writes, into the spec directory:
   - `generated_schema.sql` — the DDL record (tables + materialized view)
   - `insight_summary.md` — the Analytics Agent's markdown insights
   - `dashboard.html` — a self-contained visual dashboard
