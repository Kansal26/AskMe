"""Unit tests for Cleaning Executor, Whitelist Enforcement, and Safety Invariants."""

import pandas as pd

from src.cleaning.executor import execute_plan, execute_step
from src.cleaning.schemas import CleaningPlan, CleaningStep
from src.cleaning.whitelist import validate_step


def test_whitelist_blocks_illegal_operations():
    """Verify whitelist rejects non-approved operations and dangerous commands."""
    # Check invalid operation rejection
    fake_step = CleaningStep.model_construct(
        step_id=1,
        column="all",
        issue="delete",
        operation="drop_table",  # Not in whitelist
        params={},
        confidence=1.0,
        rationale="dangerous",
    )
    is_valid, msg = validate_step(fake_step)
    assert not is_valid
    assert "not in the approved whitelist" in msg


def test_high_stakes_imputation_is_strictly_blocked():
    """Verify safety rule: monetary amounts and IDs cannot be imputed."""
    step = CleaningStep(
        step_id=1,
        column="net_amount",
        issue="missing",
        operation="fill_missing",
        params={"strategy": "median"},  # Disallowed for net_amount!
        confidence=1.0,
        rationale="test",
    )
    is_valid, msg = validate_step(step)
    assert not is_valid
    assert "High-stakes column" in msg
    assert "leave_and_flag" in msg


def test_deterministic_step_executions():
    """Test every whitelisted operation executes accurately and deterministically."""
    df = pd.DataFrame(
        {
            "_row_id": [1, 2, 3, 4],
            "category": ["  Skincare", "skincare", "Hair Care", "Fragrance"],
            "price": ["$1,299.00", "₹450.00", "500", "99.9"],
            "order_date": ["2024-01-15", "03/04/2024", "25/12/2023", "2024-05-10 10:00:00"],
            "quantity": [1, 2, 1, 999],
        }
    )

    # 1. Strip whitespace
    s1 = CleaningStep(
        step_id=1,
        column="category",
        issue="ws",
        operation="strip_whitespace",
        params={},
        confidence=1.0,
        rationale="trim",
    )
    df, log1, _ = execute_step(df, s1)
    assert df.at[0, "category"] == "Skincare"
    assert log1.rows_affected >= 1

    # 2. To numeric
    s2 = CleaningStep(
        step_id=2,
        column="price",
        issue="currency",
        operation="to_numeric",
        params={},
        confidence=1.0,
        rationale="num",
    )
    df, log2, _ = execute_step(df, s2)
    assert df.at[0, "price"] == 1299.0
    assert df.at[1, "price"] == 450.0

    # 3. Parse dates & flag ambiguous
    s3 = CleaningStep(
        step_id=3,
        column="order_date",
        issue="dates",
        operation="parse_dates",
        params={"flag_ambiguous": True},
        confidence=1.0,
        rationale="date",
    )
    df, log3, _ = execute_step(df, s3)
    assert "is_ambiguous_order_date" in df.columns
    # Row 1 (03/04/2024) is ambiguous and flagged
    assert bool(df.at[1, "is_ambiguous_order_date"]) is True
    # Row 2 (25/12/2023) is unambiguous and converted to ISO
    assert df.at[2, "order_date"] == "2023-12-25"
    # Row 3 timestamp stripped
    assert df.at[3, "order_date"] == "2024-05-10"

    # 4. Map categories
    s4 = CleaningStep(
        step_id=4,
        column="category",
        issue="typo",
        operation="map_categories",
        params={"mapping": {"Hair Care": "Haircare"}},
        confidence=1.0,
        rationale="map",
    )
    df, log4, _ = execute_step(df, s4)
    assert df.at[2, "category"] == "Haircare"

    # 5. Flag outliers (Never delete)
    s5 = CleaningStep(
        step_id=5,
        column="quantity",
        issue="outlier",
        operation="flag_outliers",
        params={"method": "iqr"},
        confidence=1.0,
        rationale="flag",
    )
    df, log5, _ = execute_step(df, s5)
    assert len(df) == 4, "Outlier step must NEVER delete rows"
    assert "is_outlier_quantity" in df.columns


def test_dry_run_leaves_dataframe_unmutated():
    """Verify dry_run mode generates audit log and report without changing data."""
    df_orig = pd.DataFrame(
        {
            "_row_id": [1, 2],
            "category": ["  Skincare", "Haircare  "],
        }
    )
    plan = CleaningPlan(
        table_name="test",
        summary="summary",
        steps=[
            CleaningStep(
                step_id=1,
                column="category",
                issue="ws",
                operation="strip_whitespace",
                params={},
                confidence=1.0,
                rationale="trim",
            )
        ],
    )
    df_out, report, script = execute_plan(df_orig, plan, dry_run=True)

    # In dry run, df_out remains identical to original
    pd.testing.assert_frame_equal(df_out, df_orig)
    assert report.steps_applied == 1
    assert "def clean_dataset" in script
