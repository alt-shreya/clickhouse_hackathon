# Click-a-thon 2026 — Atlys: Execution Plan

## Overview
Build an **agentic analytics system** on ClickHouse with four components:
1. **Instrumentation Agent** — feature spec → production-ready ClickHouse schemas
2. **Analytics Agent** — queries + context → actionable insights (PM-ready)
3. **Context Agent** — maintains living context layer, feeds other agents
4. **Tracing & Visualization** — Langfuse traces + dashboard/CLI for full observability

**Critical constraint**: Build for the **unseen 6th spec** (released Day 2). The 5 known specs are for development/validation only.

---

## Phase 0: Environment Setup (Hour 1)

### 0.1 ClickHouse Cloud
- Provision ClickHouse Cloud service using event credits
- Create database `atlys`
- Run `cd data && ./load.sh` to load all 8 tables (~2.5M rows)
- Verify: `SELECT count() FROM atlys.destination_card_clicked` → expect 1,000,000

### 0.2 Langfuse Setup
- Spin up Langfuse (Cloud or self-hosted via Docker)
- Configure API keys for tracing all three agents

### 0.3 Repository Structure
```
atlys-agent/
├── agents/
│   ├── instrumentation/
│   ├── analytics/
│   ├── context/
│   └── shared/           # ClickHouse client, Langfuse wrapper, utilities
├── context_layer/        # Living context (JSON/YAML + vector store)
├── visualization/
│   ├── dashboard/        # Lightweight web UI (Streamlit/Gradio)
│   └── cli/              # Structured CLI output
├── tests/
│   ├── known_specs/      # Test against the 5 specs
│   └── unseen_sim/       # Simulate unseen spec processing
└── traces/               # Exported Langfuse traces for submission
```

### 0.4 Core Dependencies
```bash
# Python stack (recommended for LLM + ClickHouse + Langfuse)
pip install clickhouse-connect langfuse openai anthropic pydantic pyyaml pandas
# For dashboard
pip install streamlit plotly
```

---

## Phase 1: Shared Infrastructure (Hours 2–3)

### 1.1 ClickHouse Client Wrapper (`agents/shared/ch_client.py`)
- Connection pooling, query execution with timing
- Schema introspection: `DESCRIBE TABLE`, `SHOW CREATE TABLE`
- DDL execution with dry-run mode (human approval gate)
- Query builder for common patterns (funnel, windowFunnel, segment cuts)

### 1.2 Langfuse Tracer (`agents/shared/tracer.py`)
- Decorator/context manager for agent spans
- Auto-capture: prompt, response, tokens, latency, tool calls
- Link spans across agents (context → instrumentation → analytics)
- Export traces as JSON for submission

### 1.3 LLM Router (`agents/shared/llm.py`)
- Multi-provider (OpenAI, Anthropic, local via Ollama)
- Structured output via Pydantic models
- Token budget management (push compute to ClickHouse, not raw rows)

### 1.4 Context Store (`agents/shared/context_store.py`)
- Dual backend: **YAML files** (human-readable, git-tracked) + **vector store** (Chroma/FAISS for semantic search)
- Schema: business_definitions, metric_formulas, entity_relationships, known_issues, table_registry
- Versioning: every change = new commit + changelog entry
- API: `get_context()`, `update_context()`, `search_context()`, `diff_context()`

---

## Phase 2: Instrumentation Agent (Hours 4–8)

### 2.1 Input: Feature Spec Parser
Parse spec.md + events.ndjson → structured representation:
```python
class FeatureSpec:
    name: str
    description: str
    events: List[EventSpec]  # name, fields, envelope fields
    pm_questions: List[str]
    raw_sample: List[dict]   # from events.ndjson
```

### 2.2 Schema Designer (LLM + Rules Engine)
**Prompt includes:**
- Full base_context.md (business, entities, metrics, known issues)
- Existing 8 table schemas (from ddl.sql) — as anti-patterns to improve upon
- Feature spec + sample events
- ClickHouse best practices guide (partitioning, ordering keys, TTL, codecs)

**Output (structured):**
```python
class TableSchema:
    table_name: str
    engine: str  # MergeTree family
    partition_by: str  # toYYYYMM(timestamp) or toStartOfDay(timestamp)
    order_by: tuple[str]  # OPTIMAL: (user_id, timestamp, event_type) for funnel analysis
    ttl: str | None
    columns: List[ColumnDef]  # name, type, nullable, codec, comment
    materialized_views: List[MVDef]  # pre-aggregated funnels, segment rollups
    rationale: str  # why each choice (for trace)
```

**Key Design Decisions (learn from existing tables' mistakes):**
- ❌ Current: `ORDER BY (id, timestamp, user_id)` — queries never filter by `id`
- ✅ New: `ORDER BY (user_id, timestamp, event_type)` or `(application_id, timestamp)` for funnel tables
- Partition by `toStartOfDay(timestamp)` for faster time-range queries
- Use `LowCardinality(String)` for high-cardinality enums (device_type, os, channel)
- `CODEC(ZSTD(3))` on large string columns
- TTL for raw events (e.g., 90 days) + keep aggregations forever
- Materialized views for common funnel queries

### 2.3 DDL Generator & Executor
- Generate `CREATE TABLE` + `CREATE MATERIALIZED VIEW` statements
- Dry-run → human approval gate (optional but allowed)
- Execute against ClickHouse Cloud
- Register new tables in context_store (table_registry)

### 2.4 Event Mapper & Loader
- Map raw NDJSON → table columns (handle missing/extra fields)
- Generate `INSERT` statements or use ClickHouse `input` format
- Idempotent load (handle `duplicate_id`, `is_back_filled`)

### 2.5 Validation
- Query row counts, distinct users, funnel steps against expectations
- Schema quality checks: partition size, order key cardinality, compression ratio

### 2.6 Test Against 5 Known Specs
Run full pipeline on each spec → verify:
- Schemas create without error
- Sample data loads
- Basic queries return sensible results
- Trace exported to Langfuse

---

## Phase 3: Context Agent (Hours 9–12)

### 3.1 Initial Context Ingestion
- Parse `base_context.md` → structured YAML in context_store
- Extract: business_overview, entity_definitions, metric_definitions, known_issues, join_map, analysis_guidelines
- Load existing table schemas into table_registry

### 3.2 Context Evolution Triggers
- **On new table creation** (from Instrumentation Agent):
  - Add to table_registry with columns, partitioning, ordering keys
  - Infer entity relationships (join keys, funnel position)
  - Update metric definitions if new columns enable new metrics
- **On analytics insight generation**:
  - New known issues discovered → append to known_issues
  - Metric formula clarifications → update metric_definitions
  - Entity relationship corrections → update join_map

### 3.3 Context Freshness Mechanism
- **Version vector**: each context section has `version` and `updated_at`
- **Staleness detector**: before Analytics Agent runs, check if any table_registry entry is newer than context version → auto-refresh
- **Contradiction detector**: LLM prompt to compare context vs. actual schemas + data samples
  - Example: context says "conversion = purchase_completed / sessions" but funnel uses application_started as denominator → flag

### 3.4 Context API for Other Agents
```python
def get_context_for_agent(agent_name: str) -> ContextBundle:
    # Returns only relevant sections + recent changelog
    # Includes: business_overview, relevant metrics, known_issues for this domain, table schemas
```

### 3.5 Human Review Gate
- Context changes → diff shown in visualization layer
- Human can approve/reject/override

---

## Phase 4: Analytics Agent (Hours 13–18)

### 4.1 Analysis Planner (LLM)
**Input:** Feature spec + ContextBundle + new table schemas + PM questions
**Output:** Structured analysis plan:
```python
class AnalysisPlan:
    queries: List[QuerySpec]  # SQL, description, expected insight type
    segment_cuts: List[SegmentCut]  # device, geo, destination, funnel_stage
    comparisons: List[Comparison]   # Express vs Standard, pre vs post, segment A vs B
    statistical_tests: List[TestSpec]  # chi2, t-test, proportion test
```

### 4.2 Query Executor
- Execute planned queries via ClickHouse client
- Push ALL aggregation to ClickHouse (no raw row fetch)
- Use `windowFunnel`, `sequenceMatch`, `quantiles`, `uniqCombined`
- Return structured results (DataFrame → JSON)

### 4.3 Insight Generator (LLM)
**Prompt includes:**
- Analysis plan
- Query results (aggregates only)
- Full ContextBundle
- PM questions from spec
- Output format specification

**Output (structured):**
```python
class Insight:
    title: str
    finding: str  # what the data shows
    why: str      # business interpretation with context
    confidence: float  # 0-1
    supporting_evidence: List[Evidence]  # query ref, key numbers
    recommended_action: str  # what PM should do
    segment_scope: dict  # which segments this applies to
    related_known_issues: List[str]  # e.g., ["K1 iOS WebKit OTP"]
```

### 4.4 Insight Validation
- Cross-check: does insight contradict known issues?
- Sanity check: are numbers plausible given base rates?
- Confidence calibration: higher confidence for larger samples, clear patterns

### 4.5 Output Format
- **Markdown report** for PM consumption
- **Structured JSON** for traceability and visualization
- **Key metrics snapshot** for dashboard

---

## Phase 5: Tracing & Visualization (Hours 19–22)

### 5.1 Langfuse Integration (already in shared/tracer.py)
- Every agent run = trace
- Spans: spec_parse → schema_design → ddl_exec → load → analysis_plan → query_exec → insight_gen
- Metadata: model, tokens, latency, ClickHouse query IDs
- Links: context_version, table_versions

### 5.2 Visualization Layer

#### Option A: Streamlit Dashboard (recommended for hackathon)
Pages:
1. **Pipeline Overview** — latest run, status, duration
2. **Schema Evolution** — timeline of table creations, diff viewer
3. **Insights Feed** — all generated insights, filterable by feature/spec/confidence
4. **Context Changelog** — diff view of context layer over time
5. **Trace Explorer** — Langfuse-style trace tree for any run
6. **Unseen Spec Output** — dedicated page for Day 2 submission

#### Option B: Structured CLI (fallback)
```bash
atlys-agent run --spec specs/06_unseen/spec.md --output traces/
atlys-agent inspect --trace-id <id> --format markdown
atlys-agent dashboard --port 8501
```

### 5.3 Trace Export for Submission
- Export all Langfuse traces as JSON
- Include: full prompt/response chains, ClickHouse queries executed, context versions used
- Package with unseen spec output for judges

---

## Phase 6: Unseen Spec Readiness (Hours 23–24)

### 6.1 Dry-Run Simulation
Create a **6th synthetic spec** (different from the 5) to test full pipeline:
- Run end-to-end: spec → schemas → load → analysis → insights → traces
- Verify trace completeness
- Time the full pipeline (target: < 10 min for unseen spec)

### 6.2 Submission Package Prep
```
submission/
├── unseen_spec_output/
│   ├── generated_schema.sql
│   ├── insight_summary.md
│   └── trace.json          # Full Langfuse trace
├── architecture.md         # System design, agent interactions
├── schema_quality.md       # Justification for key design choices
├── context_strategy.md     # Why YAML + vector, versioning approach
└── traceability.md         # How judges can verify pipeline execution
```

---

## Key Technical Decisions & Rationale

| Decision | Rationale |
|----------|-----------|
| **Python + ClickHouse Connect** | Best LLM ecosystem, native ClickHouse driver, async support |
| **YAML + Vector Store for Context** | Human-readable (git diffs), semantic search for LLM retrieval, versionable |
| **ORDER BY (user_id, timestamp, event_type)** | Matches funnel query patterns; existing tables' `(id, ...)` is anti-pattern |
| **Partition by toStartOfDay(timestamp)** | Finer granularity than month; better for recent-window queries |
| **Materialized Views for Funnels** | Pre-compute step counts per segment; Analytics Agent reads aggregates |
| **Langfuse for Tracing** | Purpose-built for LLM agents; query linking; exportable |
| **Streamlit Dashboard** | Fast to build, interactive, judges can explore live |
| **Human Approval Gates** | Allowed by rules; adds safety for DDL execution |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LLM hallucinates invalid ClickHouse DDL | Rules engine validates: partition key exists, order key columns exist, types valid |
| Analytics Agent pulls too many rows | Hard limit: max 10k rows returned; enforce `LIMIT` + aggregation in SQL |
| Context drift between agents | Context version passed explicitly; Analytics Agent fails if context stale |
| Unseen spec has unexpected event structure | Instrumentation Agent handles extra/missing fields gracefully (Nullable, default) |
| Token budget exhaustion | Push compute to ClickHouse; LLM only sees aggregates; use structured output |
| Langfuse not available | Fallback: local JSONL traces with same schema |

---

## Day-by-Day Timeline (24-Hour Hackathon)

### Day 1 (Hours 1–18)
| Time | Milestone |
|------|-----------|
| 0–1  | ClickHouse + Langfuse + repo setup |
| 1–3  | Shared infra (CH client, tracer, LLM, context store) |
| 3–8  | Instrumentation Agent (spec parser → schema designer → DDL exec → loader) |
| 8–12 | Context Agent (ingest base_context, evolution triggers, freshness) |
| 12–18| Analytics Agent (planner → executor → insight generator) |
| 18–20| Test all 5 known specs end-to-end |

### Day 2 (Hours 19–24)
| Time | Milestone |
|------|-----------|
| 19–21| Visualization layer (dashboard + CLI) |
| 21–22| Dry-run with synthetic 6th spec |
| 22–23| Unseen spec released → run pipeline → capture output + traces |
| 23–24| Package submission, verify trace completeness |

---

## Success Criteria (Mapping to Judging)

| Criterion | How We Satisfy |
|-----------|----------------|
| **Schema quality** | Optimal order keys, partitioning, codecs, MVs; rationale in trace |
| **Insight quality** | PM-ready format: finding + why + action + confidence; tied to known issues |
| **Context freshness** | Versioned context; auto-refresh on new tables; contradiction detection |
| **Traceability** | Full Langfuse traces: spec → schema → queries → insights; exported for unseen spec |
| **Unseen spec** | Pipeline tested on synthetic 6th spec; runs automatically on Day 2 release |

---

## Next Immediate Steps

1. **Provision ClickHouse Cloud** and run `data/load.sh`
2. **Set up Langfuse** (Docker: `docker run -p 3000:3000 langfuse/langfuse`)
3. **Create repo structure** and install dependencies
4. **Build shared infrastructure** (CH client, tracer, context store)
5. **Start Instrumentation Agent** with spec parser + schema designer

---

*Plan created for Click-a-thon 2026 — Atlys track. Adjust timing based on team velocity.*