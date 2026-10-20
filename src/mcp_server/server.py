"""FastMCP Server exposing Read-Only DuckDB Analytics and Metric Governance Tools.

Can be run directly via CLI:
    python -m src.mcp_server.server
and verified with the MCP Inspector:
    npx @modelcontextprotocol/inspector python -m src.mcp_server.server
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from src.mcp_server import tools

mcp = FastMCP(name="Ask-the-Business-MCP")


@mcp.tool()
def get_schema() -> str:
    """Returns database schema information including tables, column types, and sample rows."""
    return tools.get_schema()


@mcp.tool()
def get_metric_definition(term: str) -> str:
    """Retrieves business metric definition, official formula, and governance rules."""
    result = tools.get_metric_definition(term)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def run_sql(query: str) -> str:
    """Validates and executes a read-only SELECT query against DuckDB.

    Security sandbox enforces:
    - Exactly one SELECT statement
    - Table allowlist (products, orders, returns, reviews)
    - Row limit of 100
    - File system and DDL/DML operations blocked
    """
    result = tools.run_sql(query)
    return json.dumps(result, indent=2, default=str)


if __name__ == "__main__":
    mcp.run()
