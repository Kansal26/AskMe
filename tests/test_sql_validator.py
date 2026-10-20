"""Unit tests for SQL Security Validator (sqlglot AST inspection)."""


from src.db.validator import validate_sql_query


def test_valid_select_queries_pass():
    """Verify standard analytical SELECT queries pass validation."""
    valid_sql = "SELECT channel, ROUND(SUM(net_amount), 2) AS rev FROM orders GROUP BY channel ORDER BY rev DESC;"
    ok, validated = validate_sql_query(valid_sql)
    assert ok
    assert "LIMIT 100" in validated.upper()


def test_cte_queries_pass():
    """Verify Common Table Expressions (CTEs) pass table allowlist validation."""
    cte_sql = """
    WITH customer_spending AS (
        SELECT customer_id, SUM(net_amount) AS spend
        FROM orders
        GROUP BY customer_id
    )
    SELECT * FROM customer_spending WHERE spend > 5000;
    """
    ok, validated = validate_sql_query(cte_sql)
    assert ok, f"CTE query failed validation: {validated}"


def test_multi_statement_queries_are_blocked():
    """Verify SQL injection attempting multi-statement execution is rejected."""
    bad_sql = "SELECT * FROM products; DROP TABLE products;"
    ok, err = validate_sql_query(bad_sql)
    assert not ok
    assert "Multi-statement execution blocked" in err


def test_mutating_statements_are_blocked():
    """Verify DDL and DML operations are strictly rejected."""
    mutations = [
        "DROP TABLE products;",
        "DELETE FROM orders WHERE order_id = 'ORD-001';",
        "UPDATE orders SET net_amount = 0;",
        "INSERT INTO products VALUES ('SKU-1', 'Name', 'Brand', 'Cat', 100);",
        "ALTER TABLE orders ADD COLUMN hack VARCHAR;",
        "PRAGMA table_info('orders');",
    ]
    for sql in mutations:
        ok, err = validate_sql_query(sql)
        assert not ok, f"Expected mutation to be blocked: {sql}"
        assert "Security violation" in err


def test_unauthorized_tables_are_blocked():
    """Verify queries targeting unauthorized or system tables are blocked."""
    unauthorized = [
        "SELECT * FROM secret_table;",
        "SELECT * FROM users;",
        "SELECT * FROM read_csv('data/clean/orders.csv');",
    ]
    for sql in unauthorized:
        ok, err = validate_sql_query(sql)
        assert not ok, f"Expected unauthorized table to be blocked: {sql}"
        assert "Security violation" in err or "Unauthorized" in err


def test_row_limit_enforcement():
    """Verify row limit is automatically clamped to 100."""
    # No limit provided
    ok1, val1 = validate_sql_query("SELECT * FROM products;")
    assert ok1
    assert "LIMIT 100" in val1.upper()

    # Small limit preserved
    ok2, val2 = validate_sql_query("SELECT * FROM products LIMIT 5;")
    assert ok2
    assert "LIMIT 5" in val2.upper()

    # Huge limit clamped
    ok3, val3 = validate_sql_query("SELECT * FROM products LIMIT 10000;")
    assert ok3
    assert "LIMIT 100" in val3.upper()
