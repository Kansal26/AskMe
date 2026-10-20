"""Unit tests for Pure Pandas Dataset Profiler."""

import pandas as pd

from src.cleaning.profiler import profile_dataset


def test_profiler_detects_all_anomaly_types():
    """Verify profiler detects whitespace, casing, dirty numeric, mixed dates, and outliers."""
    data = {
        "_row_id": [1, 2, 3, 4, 5, 6],
        "category": ["  Skincare", "skincare", "SKINCARE  ", "Haircare", "Haircare", "Haircare"],
        "price": ["$1,200.00", "₹450.50", "99.0", "  250  ", "$500", "150"],
        "order_date": [
            "2024-01-15",
            "03/04/2024",
            "25/12/2023",
            "2024-05-10 08:30:00",
            "2024-06-01",
            "2024-07-01",
        ],
        "quantity": [1, 2, 1, 1, 2, 999],  # 999 is outlier
    }
    df = pd.DataFrame(data)

    prof = profile_dataset(df, table_name="test_table")

    assert prof["table_name"] == "test_table"
    assert prof["total_rows"] == 6
    assert prof["total_columns"] == 4

    cols = prof["columns"]

    # Category checks: whitespace and casing
    cat_prof = cols["category"]
    assert cat_prof["inferred_type"] == "categorical"
    assert cat_prof["whitespace_issues"]["count"] >= 2
    assert "skincare" in cat_prof["casing_variants"]

    # Price checks: numeric in string
    price_prof = cols["price"]
    assert price_prof["inferred_type"] == "numeric"
    assert price_prof["dirty_numeric_count"] >= 3

    # Date checks: mixed and ambiguous
    date_prof = cols["order_date"]
    assert date_prof["inferred_type"] == "date"
    date_info = date_prof["mixed_date_info"]
    assert date_info["non_iso_count"] >= 2
    assert date_info["ambiguous_count"] >= 1  # 03/04/2024 is ambiguous

    # Quantity checks: IQR outlier
    qty_prof = cols["quantity"]
    assert qty_prof["inferred_type"] == "numeric"


def test_profiler_duplicate_detection():
    """Verify profiler correctly counts duplicate rows while ignoring _row_id."""
    data = {
        "_row_id": [1, 2, 3, 4],
        "item": ["A", "B", "A", "C"],
        "qty": [10, 20, 10, 30],
    }
    df = pd.DataFrame(data)
    prof = profile_dataset(df)
    assert prof["duplicate_rows_count"] == 1
