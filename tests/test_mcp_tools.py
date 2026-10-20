"""Unit tests for shared core MCP analytical tools."""


from src.mcp_server.tools import get_metric_definition, get_schema, run_sql


def test_get_schema_returns_all_tables():
    """Verify get_schema introspects products, orders, returns, and reviews."""
    schema_str = get_schema()
    assert "products" in schema_str
    assert "orders" in schema_str
    assert "returns" in schema_str
    assert "reviews" in schema_str
    assert "mrp" in schema_str
    assert "net_amount" in schema_str
    assert "is_ambiguous_order_date" in schema_str


def test_get_metric_definition_returns_formulas():
    """Verify official metric formulas can be retrieved."""
    res_aov = get_metric_definition("aov")
    assert res_aov["status"] == "found"
    assert "Average Order Value" in res_aov["metric"]["metric_name"]
    assert "COUNT(DISTINCT order_id)" in res_aov["metric"]["formula"]

    res_ret = get_metric_definition("return rate")
    assert res_ret["status"] == "found"
    assert "Return Rate" in res_ret["metric"]["metric_name"]

    res_ambig = get_metric_definition("ambiguous dates")
    assert res_ambig["status"] == "found"
    assert "Ambiguous Order Dates Governance" in res_ambig["metric"]["metric_name"]
    assert "is_ambiguous_order_date" in res_ambig["metric"]["formula"]


def test_run_sql_executes_valid_query():
    """Verify run_sql returns structured output with execution timing."""
    res = run_sql("SELECT channel, COUNT(*) as cnt FROM orders GROUP BY channel ORDER BY cnt DESC LIMIT 3")
    assert res["status"] == "success"
    assert res["row_count"] == 3
    assert "columns" in res
    assert "rows" in res
    assert res["execution_ms"] >= 0


def test_run_sql_blocks_forbidden_mutations():
    """Verify run_sql safely rejects DROP TABLE or mutating statements."""
    res = run_sql("DROP TABLE orders;")
    assert res["status"] == "error"
    assert res["error_type"] == "security_validation_error"
