"""Unit tests for Rule-Based and LLM-assisted Planners."""

from unittest.mock import MagicMock

import pandas as pd

from src.cleaning.planner import generate_llm_plan, generate_rule_based_plan
from src.common.llm import LLMClient


def test_rule_based_planner_generates_valid_steps():
    """Verify rule-based planner creates conforming steps from a profile."""
    profile = {
        "table_name": "orders",
        "total_rows": 100,
        "duplicate_rows_count": 2,
        "columns": {
            "channel": {
                "inferred_type": "categorical",
                "null_count": 0,
                "whitespace_issues": {"count": 4},
                "casing_variants": {"amazon": ["Amazon", "amazon"]},
            },
            "net_amount": {
                "inferred_type": "numeric",
                "null_count": 2,
                "null_rate": 0.02,
                "dirty_numeric_count": 5,
            },
        },
    }

    plan = generate_rule_based_plan(profile)

    assert plan.table_name == "orders"
    assert len(plan.steps) >= 3

    # Check duplicate step
    dupe_step = next((s for s in plan.steps if s.operation == "drop_duplicates"), None)
    assert dupe_step is not None
    assert dupe_step.column == "_row"

    # Check high-stakes net_amount missing step: must use leave_and_flag
    missing_step = next(
        (s for s in plan.steps if s.column == "net_amount" and s.operation == "fill_missing"), None
    )
    assert missing_step is not None
    assert missing_step.params["strategy"] == "leave_and_flag"


def test_llm_planner_fallback_on_error():
    """Verify planner gracefully falls back to rule-based planner if LLM call fails."""
    mock_client = MagicMock(spec=LLMClient)
    mock_client.generate_structured.side_effect = RuntimeError("API rate limit exceeded")

    profile = {
        "table_name": "orders",
        "total_rows": 10,
        "duplicate_rows_count": 0,
        "columns": {
            "city": {
                "inferred_type": "categorical",
                "null_count": 0,
                "whitespace_issues": {"count": 3},
            }
        },
    }
    sample_df = pd.DataFrame({"city": ["Mumbai ", " Delhi", "Bengaluru"]})

    plan, notes = generate_llm_plan(profile, sample_df, client=mock_client, max_retries=1)

    assert len(plan.steps) >= 1
    assert "Fallback to Rule-Based" in plan.summary
    assert plan.steps[0].operation == "strip_whitespace"
