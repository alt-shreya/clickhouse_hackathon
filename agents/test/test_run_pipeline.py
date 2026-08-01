"""
Test suite for End-to-End Pipeline Runner using the real ContextAgent.
"""

import pytest
from unittest.mock import MagicMock
from pathlib import Path

from agents.analytics.agent import AnalyticsAgent
from agents.context.agent import ContextAgent


def test_run_pipeline_with_real_context_agent():
    print("Initializing pipeline components...")

    # 1. Mock Database Client for ClickHouse
    mock_client = MagicMock()
    mock_result = MagicMock()
    mock_result.column_names = ["user_id"]
    mock_result.result_rows = [(101,), (102,), (103,)]
    mock_client.query.return_value = mock_result
    mock_client.command.return_value = 150

    # 2. Mock LLM call function required by the real ContextAgent
    mock_llm_call = MagicMock(return_value='{"schema_comments": {}, "business_rules": []}')

    # 3. Initialize the REAL ContextAgent using its true constructor signature
    context_agent = ContextAgent(client=mock_client, llm_call_fn=mock_llm_call)

    # Mock the return value of get_latest_context so AnalyticsAgent gets the
    # data structure it expects: the unified business-context document.
    context_agent.get_latest_context = MagicMock(return_value={
        "doc_id": "atlys_base_context",
        "content": (
            "## 5. Known-issues log\n\n"
            "1. **K1** -- New OTP verification introduces a 2s latency spike on mobile web, "
            "causing drop-offs on `purchase_completed`.\n"
        ),
        "version": 1,
        "changelog_summary": "Initial seed from base_context.md",
        "updated_at": None,
    })

    # 4. Mock LLM Config for AnalyticsAgent
    openrouter_config = MagicMock()
    openrouter_config.enabled = False

    # 5. Initialize AnalyticsAgent linking the real ContextAgent instance
    analytics_agent = AnalyticsAgent(
        client=mock_client,
        database="atlys",
        context_agent=context_agent,
        openrouter_config=openrouter_config
    )

    print("Running full analysis pipeline across tables and context...")
    
    # 6. Execute Analysis
    insights = analytics_agent.run_full_analysis()
    
    # 7. Assertions
    assert len(insights) > 0
    assert context_agent.get_latest_context.called