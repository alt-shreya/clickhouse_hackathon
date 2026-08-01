# test_context_pipeline.py
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agents.instrumentation.agent import InstrumentationAgent, TableSchema, ColumnSpec
from agents.context.agent import ContextAgent

@pytest.fixture
def mock_clickhouse_client():
    """Mock ClickHouse client to prevent actual DB execution during tests."""
    client = MagicMock()
    # Mock system queries returning default empty results
    client.query.return_value.result_rows = []
    client.query.return_value.column_names = [
        "version", "entity", "key", "value", "value_type", "source_table", "updated_by", "change_type", "supersedes_version", "confidence"
    ]
    return client


@pytest.fixture
def mock_llm_call():
    """Mock LLM response function matching ContextAgent interface."""
    def _llm_call(prompt: str, span_name: str = "test") -> str:
        if "schema_comments" in prompt:
            # Response for update_context
            return json.dumps({
                "schema_comments": {
                    "table": "Table tracking user checkout express attempts",
                    "express_method": "Payment method used for express checkout"
                },
                "business_rules": [
                    {
                        "key": "express_checkout_conversion_rate",
                        "value": "count(purchase_completed) / count(express_checkout_shown)",
                        "value_type": "metric_definition"
                    }
                ]
            })
        elif "resolving an open context flag" in prompt:
            # Response for resolve_flag
            return json.dumps({
                "resolved_value": "count(purchase_completed) / count(express_checkout_shown) WHERE is_success = 1",
                "resolution_notes": "Unified metric definition to only count successful checkouts."
            })
        elif "AUDIT_PROMPT" in prompt or "audit" in span_name:
            # Response for run_audit surfacing a gap/contradiction
            return json.dumps([
                {
                    "entity": "express_checkout_events",
                    "key": "express_checkout_conversion_rate",
                    "flag_type": "ambiguous_definition",
                    "description": "Metric formula missing success filter condition.",
                    "conflicting_keys": ["express_checkout_conversion_rate"]
                }
            ])
        return "{}"
    return _llm_call


@pytest.fixture
def sample_spec_dir(tmp_path: Path):
    """Creates a temporary spec directory with spec.md and events.ndjson."""
    spec_dir = tmp_path / "express_checkout_spec"
    spec_dir.mkdir()

    # Create spec.md
    spec_md = """# Express Checkout Feature Spec
    
This spec captures user interactions with the express checkout flow.

Events:
`express_checkout_shown`
`express_checkout_clicked`

Properties:
- `express_method`: String (e.g. apple_pay, google_pay)
- `latency_ms`: Int
"""
    (spec_dir / "spec.md").write_text(spec_md)

    # Create events.ndjson sample
    events = [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "timestamp": "2026-08-01 12:00:00",
            "user_id": "usr_123",
            "application_id": "app_abc",
            "event": "express_checkout_shown",
            "express_method": "apple_pay",
            "latency_ms": 120
        }
    ]
    with open(spec_dir / "events.ndjson", "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    return spec_dir


# ============================================================================
# TESTS
# ============================================================================

def test_auto_update_context_on_new_schema(mock_clickhouse_client, mock_llm_call, sample_spec_dir):
    """
    Test 1: Auto-update context layer when new tables or columns are created.
    """
    context_agent = ContextAgent(client=mock_clickhouse_client, llm_call_fn=mock_llm_call)
    
    # Spy on update_context
    context_agent.update_context = MagicMock(side_effect=context_agent.update_context)

    instrumentation = InstrumentationAgent(
        clickhouse_client=mock_clickhouse_client,
        context_agent=context_agent,
        openrouter_config=None  # Triggers fallback basic parsing for reproducible test
    )

    # Run full process_spec pipeline
    schemas = instrumentation.process_spec(sample_spec_dir, execute_ddl=True)

    assert len(schemas) > 0
    # Verify ContextAgent.update_context was called for generated table
    assert context_agent.update_context.called
    
    # Check that tier 1 ALTER TABLE MODIFY COMMENT was executed via ClickHouse client
    command_calls = [call[0][0] for call in mock_clickhouse_client.command.call_args_list]
    assert any("MODIFY COMMENT" in cmd or "COMMENT COLUMN" in cmd for cmd in command_calls)


def test_analytics_agent_receives_latest_context(mock_clickhouse_client, mock_llm_call):
    """
    Test 2: Ensure the Analytics Agent reads a merged view of Tier 1 & Tier 2.
    """
    context_agent = ContextAgent(client=mock_clickhouse_client, llm_call_fn=mock_llm_call)

    # Mock DB returns for Tier 1 & Tier 2
    mock_clickhouse_client.query.side_effect = [
        # Tier 2 response
        MagicMock(
            column_names=["entity", "key", "value", "value_type", "version"],
            result_rows=[["express_checkout", "conversion_rate", "count()", "metric_definition", 2]]
        ),
        # Tier 1 system.tables
        MagicMock(column_names=["entity", "comment"], result_rows=[["express_checkout", "Express payment events"]]),
        # Tier 1 system.columns
        MagicMock(column_names=["entity", "column", "comment"], result_rows=[["express_checkout", "express_method", "Apple/Google pay"]]),
        # Open flags
        MagicMock(column_names=["flag_id", "entity", "key", "flag_type", "description"], result_rows=[])
    ]

    latest_ctx = context_agent.get_latest_context(entities=["express_checkout"])

    assert latest_ctx["context_version"] == 2
    assert len(latest_ctx["schema_context"]["tables"]) == 1
    assert latest_ctx["schema_context"]["tables"][0]["entity"] == "express_checkout"
    assert len(latest_ctx["business_context"]) == 1

from unittest.mock import MagicMock

def test_surface_and_resolve_context_flags(mock_clickhouse_client, mock_llm_call):
    """
    Test 3: Surface contradictions/gaps and verify resolution workflow.
    """
    context_agent = ContextAgent(client=mock_clickhouse_client, llm_call_fn=mock_llm_call)

    # --- ADD THIS: Route the mock queries to return simulated data ---
    def mock_query(sql):
        mock_res = MagicMock()
        if "context_flags" in sql:
            # Simulate an open flag existing when resolve_flag() checks for it
            mock_res.result_rows = [("Simulated conflict description",)]
            mock_res.column_names = ["description"]
        else:
            # Simulate existing context rows for run_audit() to evaluate
            mock_res.result_rows = [("express_checkout", "formula", "a/b", "metric_definition", 1)]
            mock_res.column_names = ["entity", "key", "value", "value_type", "version"]
        return mock_res
        
    mock_clickhouse_client.query.side_effect = mock_query
    # -----------------------------------------------------------------

    # 1. Run audit to surface a flag
    flags = context_agent.run_audit(scope=["express_checkout"])
    
    assert len(flags) > 0

    # 2. Extract flag data (adjust keys based on what your mock_llm_call returns)
    flag_id = "test_flag_123" 
    entity = flags[0].get("entity", "express_checkout")
    key = flags[0].get("key", "formula")

    # 3. Resolve the flag
    context_agent.resolve_flag(flag_id=flag_id, entity=entity, key=key)

    # 4. Verify insertion and status update
    assert mock_clickhouse_client.insert.called
    
    update_calls = [call for call in mock_clickhouse_client.command.call_args_list if "UPDATE status = 'resolved'" in call[0][0]]
    assert len(update_calls) > 0