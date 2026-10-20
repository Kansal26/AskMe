"""Database Loader: Ingests cleaned data into DuckDB with typed relational schema."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.common.config import settings
from src.db.connection import get_duckdb_connection

CREATE_TABLES_SQL = """
DROP TABLE IF EXISTS returns;
DROP TABLE IF EXISTS reviews;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;

CREATE OR REPLACE TABLE products (
    sku VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    brand VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    mrp DOUBLE NOT NULL
);

CREATE OR REPLACE TABLE orders (
    order_id VARCHAR PRIMARY KEY,
    customer_id VARCHAR NOT NULL,
    order_date DATE NOT NULL,
    sku VARCHAR NOT NULL REFERENCES products(sku),
    channel VARCHAR NOT NULL,
    quantity INTEGER NOT NULL,
    gross_amount DOUBLE NOT NULL,
    discount_amount DOUBLE NOT NULL,
    net_amount DOUBLE NOT NULL,
    city VARCHAR NOT NULL,
    is_ambiguous_order_date BOOLEAN DEFAULT FALSE
);

CREATE OR REPLACE TABLE returns (
    return_id VARCHAR PRIMARY KEY,
    order_id VARCHAR NOT NULL REFERENCES orders(order_id),
    return_date DATE NOT NULL,
    reason VARCHAR NOT NULL,
    refund_amount DOUBLE NOT NULL
);

CREATE OR REPLACE TABLE reviews (
    review_id VARCHAR PRIMARY KEY,
    sku VARCHAR NOT NULL REFERENCES products(sku),
    rating INTEGER NOT NULL,
    review_text VARCHAR,
    review_date DATE NOT NULL
);

-- Analytical indexes
CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_channel ON orders(channel);
CREATE INDEX IF NOT EXISTS idx_orders_sku ON orders(sku);
CREATE INDEX IF NOT EXISTS idx_orders_ambig_date ON orders(is_ambiguous_order_date);
CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
"""


def load_cleaned_data_to_duckdb(
    source_dir: Path | str = "data/clean",
    db_path: Path | str | None = None,
) -> dict[str, int]:
    """Loads cleaned CSV tables into DuckDB relational schema.

    Returns dict of table_name -> row_count.
    """
    s_dir = Path(source_dir)
    target_path = Path(db_path or settings.duckdb_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Connecting to DuckDB in setup mode: {target_path}")
    con = get_duckdb_connection(db_path=target_path, read_only=False)

    print("Creating tables and indexes...")
    con.execute(CREATE_TABLES_SQL)

    tables = ["products", "orders", "returns", "reviews"]
    row_counts: dict[str, int] = {}

    for tbl in tables:
        csv_file = s_dir / f"{tbl}.csv"
        if not csv_file.exists():
            con.close()
            raise FileNotFoundError(f"Clean CSV file not found: {csv_file}")

        df = pd.read_csv(csv_file)
        # Drop internal _row_id if present
        if "_row_id" in df.columns:
            df = df.drop(columns=["_row_id"])

        if tbl == "orders" and "is_ambiguous_order_date" not in df.columns:
            df["is_ambiguous_order_date"] = False

        con.register(f"df_{tbl}_temp", df)
        con.execute(f"INSERT INTO {tbl} BY NAME SELECT * FROM df_{tbl}_temp")
        con.unregister(f"df_{tbl}_temp")

        count = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        row_counts[tbl] = int(count)
        print(f"  Loaded table '{tbl}': {count:,} rows")

    con.close()
    print("Database build complete and connection closed successfully.")
    return row_counts


if __name__ == "__main__":
    load_cleaned_data_to_duckdb()
