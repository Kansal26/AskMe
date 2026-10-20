"""Unit tests for Stage 2b SQL Result Comparators (Strict vs Lenient)."""

from datetime import date, datetime
from eval.qa_eval import _lenient_match, _strict_match, _values_match


def test_values_match_float_tolerance():
    assert _values_match(31284974.750001892, 31284974.75)
    assert _values_match(1564.248, 1564.25)
    assert not _values_match(100.0, 150.0)


def test_values_match_date_normalization():
    # datetime.date vs 'YYYY-MM'
    assert _values_match(date(2023, 1, 1), "2023-01")
    assert _values_match("2023-01-01", "2023-01")
    assert _values_match(datetime(2024, 5, 12, 0, 0), "2024-05")
    assert not _values_match("2023-02-01", "2023-01")


def test_values_match_case_insensitivity():
    assert _values_match("GlowBotanica", "glowbotanica ")
    assert _values_match("SKU-001", "sku-001")


def test_strict_match_requires_exact_columns_and_order():
    agent = [{"col1": 10, "col2": "A"}, {"col1": 20, "col2": "B"}]
    gold = [{"col1": 10, "col2": "A"}, {"col1": 20, "col2": "B"}]
    assert _strict_match(agent, gold)

    # Different column order fails strict
    agent_diff_col_order = [{"col2": "A", "col1": 10}, {"col2": "B", "col1": 20}]
    assert not _strict_match(agent_diff_col_order, gold)

    # Extra column fails strict
    agent_extra = [{"col1": 10, "col2": "A", "col3": 99}, {"col1": 20, "col2": "B", "col3": 99}]
    assert not _strict_match(agent_extra, gold)

    # Different row order fails strict
    agent_diff_row_order = [{"col1": 20, "col2": "B"}, {"col1": 10, "col2": "A"}]
    assert not _strict_match(agent_diff_row_order, gold)


def test_lenient_match_allows_extra_columns():
    gold = [{"name": "Serum", "brand": "Luxe", "mrp": 999.0}]
    agent = [{"sku": "SKU-01", "name": "Serum", "brand": "Luxe", "category": "Skin", "mrp": 999.0}]
    gold_sql = "SELECT name, brand, mrp FROM products ORDER BY mrp DESC LIMIT 1;"

    assert not _strict_match(agent, gold)
    assert _lenient_match(agent, gold, gold_sql)


def test_lenient_match_ignores_row_order_without_limit():
    gold = [{"category": "A", "cnt": 10}, {"category": "B", "cnt": 20}]
    agent = [{"category": "B", "cnt": 20}, {"category": "A", "cnt": 10}]
    gold_sql = "SELECT category, COUNT(*) AS cnt FROM products GROUP BY category;"

    assert not _strict_match(agent, gold)
    assert _lenient_match(agent, gold, gold_sql)


def test_lenient_match_enforces_row_order_with_order_by_and_limit():
    gold = [{"brand": "A", "rev": 1000}, {"brand": "B", "rev": 800}]
    agent = [{"brand": "B", "rev": 800}, {"brand": "A", "rev": 1000}]
    gold_sql = "SELECT brand, rev FROM sales ORDER BY rev DESC LIMIT 2;"

    # When ORDER BY + LIMIT is present, ranking order must be preserved
    assert not _lenient_match(agent, gold, gold_sql)

    agent_ordered = [{"brand": "A", "rev": 1000}, {"brand": "B", "rev": 800}]
    assert _lenient_match(agent_ordered, gold, gold_sql)
