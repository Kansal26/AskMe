"""sqlglot-based SQL Validator and Safety Guard for Read-Only DuckDB Queries.

Security checks:
1. Exactly one SQL statement.
2. Root AST statement must be a Select expression.
3. Strictly forbids DDL/DML (DROP, ALTER, CREATE, INSERT, UPDATE, DELETE, PRAGMA, ATTACH).
4. Table allowlist check: allows only 'products', 'orders', 'returns', 'reviews' (and internal CTE aliases).
5. Row limit enforcement: automatically limits output to at most 100 rows.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

ALLOWED_TABLES = {"products", "orders", "returns", "reviews"}
MAX_ROW_LIMIT = 100


def validate_sql_query(query: str) -> tuple[bool, str]:
    """Parses and validates SQL with sqlglot.

    Returns:
        (True, validated_sql_string_with_limit) if safe.
        (False, error_message) if rejected.
    """
    clean_query = query.strip()
    if not clean_query:
        return False, "Query is empty."

    # 1. Parse AST
    try:
        parsed_statements = sqlglot.parse(clean_query, read="duckdb")
    except Exception as e:
        return False, f"SQL syntax error: {e}"

    if not parsed_statements:
        return False, "No valid SQL statement detected."

    # 2. Reject multi-statement queries
    if len(parsed_statements) > 1:
        return (
            False,
            f"Security violation: Multi-statement execution blocked. Detected {len(parsed_statements)} statements.",
        )

    stmt = parsed_statements[0]
    if stmt is None:
        return False, "Parsed statement is empty."

    # 3. Check statement type: must be Select
    if not isinstance(stmt, exp.Select):
        return (
            False,
            f"Security violation: Only SELECT queries are permitted. Got statement type: {stmt.key.upper()}",
        )

    # 4. Check for forbidden mutating expressions
    forbidden_types = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Drop,
        exp.Alter,
        exp.Create,
        exp.Command,
        exp.Pragma,
    )
    for forbidden in forbidden_types:
        if stmt.find(forbidden):
            return (
                False,
                f"Security violation: Prohibited mutating SQL operation '{forbidden.__name__}' detected.",
            )

    # 5. Extract CTE aliases defined within query
    cte_aliases: set[str] = set()
    for with_expr in stmt.find_all(exp.With):
        for cte in with_expr.expressions:
            if isinstance(cte, exp.CTE) and cte.alias:
                cte_aliases.add(cte.alias.lower())

    # 6. Check table allowlist
    referenced_tables: set[str] = set()
    for table_expr in stmt.find_all(exp.Table):
        # Reject function calls used as table sources (e.g. read_csv, read_parquet)
        if isinstance(table_expr.this, exp.Func) or not isinstance(table_expr.this, (exp.Identifier, str)):
            func_name = getattr(table_expr.this, "key", type(table_expr.this).__name__)
            return False, f"Security violation: Table function '{func_name}' is disallowed in queries."

        tbl_name = table_expr.name.lower() if table_expr.name else ""
        if tbl_name:
            referenced_tables.add(tbl_name)

    # All referenced tables must be either in ALLOWED_TABLES or a declared CTE alias
    unauthorized_tables = referenced_tables - (ALLOWED_TABLES | cte_aliases)
    if unauthorized_tables:
        return (
            False,
            f"Security violation: Unauthorized table reference {sorted(unauthorized_tables)}. "
            f"Allowed schema tables are: {sorted(ALLOWED_TABLES)}",
        )

    # 7. Row limit enforcement
    limit_expr = stmt.args.get("limit")
    if limit_expr is None:
        stmt = stmt.limit(MAX_ROW_LIMIT)
    else:
        # Check current limit value
        try:
            curr_limit = int(limit_expr.expression.this)
            if curr_limit > MAX_ROW_LIMIT:
                stmt = stmt.limit(MAX_ROW_LIMIT)
        except Exception:
            stmt = stmt.limit(MAX_ROW_LIMIT)

    validated_sql = stmt.sql(dialect="duckdb")
    return True, validated_sql
