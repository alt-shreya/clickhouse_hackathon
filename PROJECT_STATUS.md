# Atlys Click-a-thon 2026 — Project Status

## Problem Statement

Build a **system of three agents on ClickHouse** that:

1. **Instrumentation Agent** — Feature spec → production-ready ClickHouse schemas
2. **Analytics Agent** — Queries data, applies context, writes actionable insights
3. **Context Agent** — Maintains living business context layer, feeds it to other agents

**Plus:**
- **Tracing** (Langfuse) for full pipeline observability
- **Visualization** layer for the pipeline
- Handle **Day 2 sealed spec** (unseen 6th spec released during hackathon)

**Data**: 8 existing event tables (~2.5M rows, 264 MB parquet) modeling Atlys's pre-purchase conversion funnel:

```
destination_card_clicked → application_started → document_uploaded → purchase_completed
```

Plus 4 supporting tables: `search_typed`, `landing_page_scrolled`, `auth_completed`, `pay_now_clicked`

**Specs**: 5 feature specs (1-page brief + raw NDJSON events), no schemas provided — your job is to design them.

---

## MVP Definition

A working pipeline that:
1. Loads context from `base_context.md` + `meta_context_registry` (existing 8 tables)
2. Parses any feature spec (spec.md + events.ndjson)
3. Generates valid ClickHouse DDL with proper envelope, partitioning, ordering
4. Validates against best practices and existing tables
5. Registers schemas in `meta_context_registry`
6. Traces the entire flow in Langfuse
7. Produces visualizations of the generated schemas

---

## What's Built ✅

| Component | Status | Details |
|-----------|--------|---------|
| **Data Loader** | ✅ | `load_to_clickhouse.py` — loads 8 parquet files via `INSERT ... FORMAT Parquet` |
| **Config System** | ✅ | `ClickHouseConfig`, `LangfuseConfig`, `OpenRouterConfig` with `.env` loading |
| **ContextAgent** | ✅ | Parses `base_context.md` → 6 entities, 6 metrics, 7 issues; loads `meta_context_registry` (8 tables with full column metadata) |
| **InstrumentationAgent** | ✅ | **Core pipeline working**: parses spec.md + events.ndjson → extracts 5-9 event types per spec → generates ClickHouse DDL with envelope columns, monthly partitioning, `(id, timestamp, user_id)` ordering, LowCardinality enums. Validates & registers in registry. **LLM integration ready** (rate-limited on free tier). |
| **TracingAgent** | ✅ | Langfuse spans/generations/events, context managers, auto-disables if not configured |
| **VisualizationAgent** | ✅ | Funnel, bar charts, time series, heatmaps, metric cards, HTML dashboard export |
| **Specs Processed** | ✅ | All 5 specs parsed: 5→9→8→7→9 tables generated respectively |

---

## What's Still Needed 🔨

| Priority | Component | Details |
|----------|-----------|---------|
| **HIGH** | **AnalyticsAgent LLM insights** | Feed query results + context to LLM for narrative insights (currently rule-based only) |
| **HIGH** | **Pipeline Orchestrator** | `run_pipeline(spec_dir)` that chains: Context → Instrumentation → Analytics → Visualization → Tracing |
| **HIGH** | **InstrumentationAgent LLM mode** | Fix rate limit (add Google AI Studio key to OpenRouter) for smarter schema generation |
| **MEDIUM** | **Per-event column specialization** | Basic parser puts ALL properties on ALL tables — need event-specific columns only |
| **MEDIUM** | **Langfuse integration in agents** | Wrap key methods with `@trace_span` in Instrumentation/Analytics/Context agents |
| **MEDIUM** | **Day 2 sealed spec handler** | Code to process unseen 6th spec and produce submission artifacts |
| **LOW** | **CLI entry point** | `python -m agents.instrumentation spec_dir` |
| **LOW** | **Integration tests** | Verify generated DDL loads in ClickHouse, end-to-end trace verification |

---

## Spec Results (5/5 Processed)

| Spec | Tables Generated | Events |
|------|-----------------|--------|
| 01_express_checkout | 5 | express_checkout_shown, express_checkout_selected, saved_method_used, otp_entered, express_payment_confirmed |
| 02_group_family | 9 | group_started, group_id, group_size, traveller_added, traveller_index, docs_complete, traveller_removed, group_submitted, travellers_submitted |
| 03_status_sharing | 8 | share_clicked, status_shared, channel_selected, link_generated, share_id, link_opened, recipient_is_new_user, recipient_cta_clicked |
| 04_abandoned_checkout_recovery | 7 | abandonment_detected, drop_step, reminder_sent, hours_since_drop, reminder_opened, reminder_cta_clicked, resumed_at_step |
| 05_instant_forex | 9 | forex_offer_shown, from_currency, to_currency, fx_rate, currency_selected, amount_entered, forex_added_to_cart, addon_value_inr, forex_purchased |

---

## Quick Test Commands

```bash
# Load data (run once)
cd click-a-thon-2026/Atlys && python load_to_clickhouse.py

# Test InstrumentationAgent (basic, works now)
cd atlys-agent && python -c "
from agents import get_config, ContextAgent, InstrumentationAgent
import clickhouse_connect
from pathlib import Path

ch, lf, orc = get_config()
client = clickhouse_connect.get_client(host=ch.host, port=ch.port, username=ch.user, password=ch.password, secure=ch.secure)
ca = ContextAgent('click-a-thon-2026/Atlys/base_context.md')
ia = InstrumentationAgent(client, ca, openrouter_config=None)
schemas = ia.process_spec(Path('click-a-thon-2026/Atlys/specs/01_express_checkout'))
print(ia.emit_ddl())
"
```

---

## Architecture

```
atlys-agent/
├── agents/
│   ├── config.py              # ClickHouse, Langfuse, OpenRouter configs
│   ├── instrumentation/agent.py   # Spec → ClickHouse schemas (MAIN)
│   ├── analytics/agent.py         # Queries + insights (needs LLM)
│   ├── context/agent.py           # base_context.md + registry parser
│   ├── tracing/agent.py           # Langfuse integration
│   └── visualization/agent.py     # Charts + dashboard
├── requirements.txt
└── .env.example
```

The **InstrumentationAgent is the core** and it's working with basic fallback. The main blockers for full MVP are LLM rate limits and wiring the orchestrator.

---

## Verification

| Check | Result |
|-------|--------|
| `py_compile` syntax | ✅ |
| Load context (8 existing tables) | ✅ |
| Parse spec (5 events) | ✅ |
| Generate 5 table schemas | ✅ |
| All validation OK | ✅ |
| Emit DDL (12KB) | ✅ |