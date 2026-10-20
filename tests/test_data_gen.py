"""Unit tests for Phase 0: Synthetic Data Generation and Ground-Truth Corruption."""


import pandas as pd

from src.data_gen.corrupter import inject_corruptions
from src.data_gen.generator import (
    CHANNELS,
    CITIES,
    generate_clean_dataset,
)


def test_clean_data_shapes_and_columns():
    """Verify clean dataset row counts, schemas, and referential validity."""
    datasets = generate_clean_dataset(
        seed=42,
        num_products=150,
        num_orders=2000,   # test with scaled subset for fast unit testing
        num_returns=200,
        num_reviews=300,
    )

    df_p = datasets["products"]
    df_o = datasets["orders"]
    df_r = datasets["returns"]
    df_rev = datasets["reviews"]

    # Check products
    assert len(df_p) == 150
    assert set(df_p.columns) == {"sku", "name", "brand", "category", "mrp"}
    assert df_p["mrp"].min() >= 100.0

    # Check orders
    assert len(df_o) == 2000
    expected_order_cols = {
        "order_id", "customer_id", "order_date", "sku", "channel",
        "quantity", "gross_amount", "discount_amount", "net_amount", "city",
    }
    assert expected_order_cols.issubset(set(df_o.columns))
    assert set(df_o["channel"]).issubset(set(CHANNELS))
    assert set(df_o["city"]).issubset(set(CITIES))

    # Financial math integrity: net_amount == gross_amount - discount_amount
    diff = (df_o["gross_amount"] - df_o["discount_amount"] - df_o["net_amount"]).abs()
    assert (diff < 0.02).all()

    # Repeat customer presence
    unique_custs = df_o["customer_id"].nunique()
    assert unique_custs < len(df_o), "Orders must include repeat customers"

    # Check returns
    assert len(df_r) == 200
    assert set(df_r.columns) == {"return_id", "order_id", "return_date", "reason", "refund_amount"}
    # Foreign key check
    assert set(df_r["order_id"]).issubset(set(df_o["order_id"]))

    # Check reviews
    assert len(df_rev) == 300
    assert set(df_rev.columns) == {"review_id", "sku", "rating", "review_text", "review_date"}
    assert df_rev["rating"].between(1, 5).all()
    assert set(df_rev["sku"]).issubset(set(df_p["sku"]))


def test_seed_determinism():
    """Verify that identical seeds produce bitwise-identical datasets."""
    ds1 = generate_clean_dataset(
        seed=42, num_products=30, num_orders=100, num_returns=10, num_reviews=20
    )
    ds2 = generate_clean_dataset(
        seed=42, num_products=30, num_orders=100, num_returns=10, num_reviews=20
    )

    for k in ds1:
        pd.testing.assert_frame_equal(ds1[k], ds2[k])


def test_corruption_injection_and_manifest():
    """Verify corruption injection mechanics, cell-level tracking, and duplicate alignment."""
    datasets = generate_clean_dataset(
        seed=42, num_products=50, num_orders=500, num_returns=50, num_reviews=100
    )
    messy_dfs, manifest = inject_corruptions(datasets, seed=42)

    assert len(manifest) > 0, "Manifest must not be empty"

    issue_types = {item["issue_type"] for item in manifest}
    expected_issues = {
        "duplicate_row",
        "dirty_whitespace",
        "inconsistent_casing",
        "mixed_date_format",
        "dirty_numeric",
        "missing_value",
    }
    missing = expected_issues - issue_types
    assert expected_issues.issubset(issue_types), f"Missing issue types: {missing}"

    # Verify duplicate row tracking and alignment
    dupe_entries = [m for m in manifest if m["issue_type"] == "duplicate_row"]
    assert len(dupe_entries) > 0
    for d in dupe_entries:
        assert isinstance(d["_row_id"], int)
        assert d["column"] == "_row"
        assert "original_row_id" in d["details"]
        orig_id = d["details"]["original_row_id"]
        assert orig_id < d["_row_id"], "Original row must exist before the duplicate clone"

    # Verify ambiguous date tracking
    ambiguous_dates = [
        m for m in manifest
        if m["issue_type"] == "mixed_date_format"
        and m.get("details", {}).get("is_ambiguous") is True
    ]
    assert len(ambiguous_dates) > 0, "Must inject ambiguous date formats for human flagging"

    # Verify manifest cell-level keys
    for entry in manifest:
        assert "_row_id" in entry
        assert "table" in entry
        assert "column" in entry
        assert "issue_type" in entry
        assert "original_value" in entry
        assert "corrupted_value" in entry
