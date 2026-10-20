"""Core Analytical Tools shared by both in-process Agent and FastMCP Server.

Exposes:
1. get_schema(): Introspects DuckDB relational schema, column types, and sample records.
2. get_metric_definition(term): Retrieves governance definitions and formulas from data dictionary.
3. run_sql(query): Strictly validates with sqlglot, executes on read-only DuckDB, and returns structured data.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from src.db.connection import get_duckdb_connection
from src.db.validator import validate_sql_query

DOCS_DATA_DICT = Path("docs/data_dictionary.md")


def get_schema(db_path: Path | str | None = None) -> str:
    """Returns database schema information including tables, column types, and primary/foreign keys."""
    try:
        con = get_duckdb_connection(db_path=db_path, read_only=True)
        tables = ["products", "orders", "returns", "reviews"]
        schema_parts = ["# DuckDB Relational Database Schema\n"]

        for tbl in tables:
            cols_info = con.execute(f"PRAGMA table_info('{tbl}')").fetchall()
            row_count = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]

            schema_parts.append(f"### Table: `{tbl}` ({row_count:,} rows)")
            schema_parts.append("| Column | Type | Primary Key |")
            schema_parts.append("| :--- | :--- | :---: |")
            for col in cols_info:
                # col structure: (cid, name, type, notnull, dflt_value, pk)
                col_name, col_type, pk = col[1], col[2], bool(col[5])
                schema_parts.append(f"| `{col_name}` | `{col_type}` | {'YES' if pk else 'NO'} |")

            # Sample row
            sample_rows = con.execute(f"SELECT * FROM {tbl} LIMIT 2").fetchall()
            col_names = [c[1] for c in cols_info]
            schema_parts.append(f"**Sample record**: {dict(zip(col_names, sample_rows[0])) if sample_rows else 'None'}\n")

        con.close()
        return "\n".join(schema_parts)
    except Exception as e:
        return (
            f"Error inspecting live DuckDB database: {e}. "
            "Please ensure data has been loaded into DuckDB via src.db.loader."
        )


def get_metric_definition(term: str) -> dict[str, Any]:
    """Retrieves business metric definition, governance formula, and SQL pattern from data dictionary."""
    clean_term = term.strip().lower()

    # Pre-compiled high-precision metric registry
    METRICS_REGISTRY: dict[str, dict[str, Any]] = {
        "gross revenue": {
            "metric_name": "Gross Revenue",
            "aliases": ["gross sales", "total sales", "gross amount", "gmv"],
            "definition": "Total monetary value of merchandise sold before promotional discounts.",
            "formula": "SUM(gross_amount)",
            "sql_example": "SELECT ROUND(SUM(gross_amount), 2) AS gross_revenue FROM orders;",
            "tables_involved": ["orders"],
        },
        "net revenue": {
            "metric_name": "Net Revenue",
            "aliases": ["net sales", "revenue", "top-line", "net amount"],
            "definition": "Top-line revenue recognized after deducting promotional discounts.",
            "formula": "SUM(net_amount) = SUM(gross_amount - discount_amount)",
            "sql_example": "SELECT ROUND(SUM(net_amount), 2) AS net_revenue FROM orders;",
            "tables_involved": ["orders"],
        },
        "discounts": {
            "metric_name": "Promotional Discounts",
            "aliases": ["discount amount", "total discounts", "promo"],
            "definition": "Total customer discounts granted across all sales channels.",
            "formula": "SUM(discount_amount)",
            "sql_example": "SELECT ROUND(SUM(discount_amount), 2) AS total_discounts FROM orders;",
            "tables_involved": ["orders"],
        },
        "aov": {
            "metric_name": "Average Order Value (AOV)",
            "aliases": ["average order value", "order size", "basket size"],
            "definition": "The average net revenue generated per order transaction.",
            "formula": "SUM(net_amount) / COUNT(DISTINCT order_id)",
            "sql_example": "SELECT ROUND(SUM(net_amount) * 1.0 / COUNT(DISTINCT order_id), 2) AS aov FROM orders;",
            "tables_involved": ["orders"],
        },
        "return rate": {
            "metric_name": "Return Rate (Volume-Based)",
            "aliases": ["order return rate", "returns percentage", "returns"],
            "definition": "The percentage of completed orders that resulted in a customer return.",
            "formula": "(COUNT(DISTINCT returns.order_id) * 100.0) / COUNT(DISTINCT orders.order_id)",
            "sql_example": (
                "SELECT ROUND(COUNT(DISTINCT r.order_id) * 100.0 / COUNT(DISTINCT o.order_id), 2) AS return_rate_pct "
                "FROM orders o LEFT JOIN returns r ON o.order_id = r.order_id;"
            ),
            "tables_involved": ["orders", "returns"],
        },
        "repeat customer rate": {
            "metric_name": "Repeat Customer Rate",
            "aliases": ["repeat rate", "customer retention", "repeat buyers"],
            "definition": "The proportion of customers who placed 2 or more orders.",
            "formula": "COUNT(customers with >= 2 orders) * 100.0 / COUNT(total distinct customers)",
            "sql_example": (
                "WITH cust_counts AS (SELECT customer_id, COUNT(DISTINCT order_id) as cnt FROM orders GROUP BY customer_id) "
                "SELECT ROUND(COUNT(CASE WHEN cnt >= 2 THEN 1 END) * 100.0 / COUNT(*), 2) AS repeat_rate FROM cust_counts;"
            ),
            "tables_involved": ["orders"],
        },
        "rating": {
            "metric_name": "Customer Review Rating (CSAT)",
            "aliases": ["average rating", "stars", "review rating", "csat"],
            "definition": "Arithmetic mean star rating (1 to 5) given by verified purchasers.",
            "formula": "AVG(rating)",
            "sql_example": "SELECT p.name, ROUND(AVG(r.rating), 2) AS avg_stars FROM products p JOIN reviews r ON p.sku = r.sku GROUP BY p.name;",
            "tables_involved": ["products", "reviews"],
        },
    }

    # Match exact or alias
    for key, item in METRICS_REGISTRY.items():
        if key in clean_term or any(a in clean_term for a in item["aliases"]):
            return {"status": "found", "metric": item}

    # Fallback keyword match in data dictionary markdown
    if DOCS_DATA_DICT.exists():
        with open(DOCS_DATA_DICT, "r", encoding="utf-8") as f:
            content = f.read()
        sections = content.split("### ")
        for sec in sections[1:]:
            header = sec.split("\n")[0].lower()
            if any(word in header for word in clean_term.split()):
                return {
                    "status": "found",
                    "metric": {
                        "metric_name": sec.split("\n")[0],
                        "definition": sec[:400].strip(),
                        "tables_involved": ["orders"],
                    },
                }

    return {
        "status": "not_found",
        "message": f"No official metric definition found for '{term}'. Available metrics: {list(METRICS_REGISTRY.keys())}",
    }


def run_sql(query: str, db_path: Path | str | None = None) -> dict[str, Any]:
    """Strictly validates SQL query with sqlglot, executes on read-only DuckDB, and returns structured results."""
    t0 = time.perf_counter()

    # 1. AST Validation
    is_valid, validated_or_err = validate_sql_query(query)
    if not is_valid:
        return {
            "status": "error",
            "error_type": "security_validation_error",
            "message": validated_or_err,
            "original_query": query,
            "execution_ms": round((time.perf_counter() - t0) * 1000, 2),
        }

    validated_sql = validated_or_err

    # 2. Database Execution
    try:
        con = get_duckdb_connection(db_path=db_path, read_only=True)
        cursor = con.execute(validated_sql)
        description = cursor.description
        columns = [d[0] for d in description] if description else []
        tuples = cursor.fetchall()
        con.close()

        # Convert to list of dicts
        rows = [dict(zip(columns, row)) for row in tuples]
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        return {
            "status": "success",
            "executed_sql": validated_sql,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "execution_ms": elapsed_ms,
        }
    except Exception as e:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "status": "error",
            "error_type": "sql_execution_error",
            "message": str(e),
            "executed_sql": validated_sql,
            "execution_ms": elapsed_ms,
        }
