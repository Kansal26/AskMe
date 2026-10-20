"""Ground-truth Corruption Injector for Synthetic Data.

Injects known, cell-level corruptions into clean dataframes with full auditability:
1. Duplicate rows (tracked with original_row_id alignment)
2. Mixed and ambiguous date formats (flags ambiguous DD/MM vs MM/DD)
3. Dirty whitespace (leading, trailing, internal repeated spaces)
4. Inconsistent casing (UPPERCASE, lowercase, mixed)
5. Dirty numeric values (currency symbols '$' and '₹', thousand commas, string formatting)
6. Category spelling variants / fuzzy clusters (e.g., 'Skin care', 'Skin-care')
7. Missing values (MCAR pattern with original values tracked)
8. Outliers (anomalous quantities and amounts)

Produces:
- data/raw_messy/*.csv (with stable hidden _row_id)
- data/ground_truth/manifest.json (cell-level ground truth entries)
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, TypedDict

import pandas as pd


class ManifestEntry(TypedDict):
    _row_id: int
    table: str
    column: str
    issue_type: str
    original_value: Any
    corrupted_value: Any
    details: dict[str, Any] | str | None


CATEGORY_VARIANTS: dict[str, list[str]] = {
    "Skincare": ["Skin care", "Skin-care", "skincare", "SkinCare"],
    "Haircare": ["Hair care", "Hair-care", "haircare", "HairCare"],
    "Bath & Body": ["Bath and Body", "Bath & body", "Bath &Body", "Bath&Body"],
    "Fragrance": ["Fragrances", "Perfume & Fragrance", "fragrance"],
    "Color Cosmetics": ["Colour Cosmetics", "Color-Cosmetics", "Cosmetics", "Color cosmetics"],
}


def inject_corruptions(
    clean_datasets: dict[str, pd.DataFrame],
    seed: int = 42,
    corruption_rate: float = 0.05,
) -> tuple[dict[str, pd.DataFrame], list[ManifestEntry]]:
    """Injects known errors into clean dataframes and records cell-level manifest.

    Each dataframe receives a stable `_row_id` column starting from 1.
    Each cell has at most one corruption for clean evaluation attribution.
    """
    rng = random.Random(seed)

    manifest: list[ManifestEntry] = []
    messy_datasets: dict[str, pd.DataFrame] = {}

    for table_name, df_orig in clean_datasets.items():
        df = df_orig.copy()

        # Ensure 1-indexed stable _row_id
        if "_row_id" not in df.columns:
            df.insert(0, "_row_id", range(1, len(df) + 1))

        # In a messy raw CSV, all non-row_id columns are effectively string/object
        for col in df.columns:
            if col != "_row_id":
                df[col] = df[col].astype(object)

        num_rows = len(df)
        # Track corrupted cells as (row_id, column) to ensure cell-level uniqueness
        corrupted_cells: set[tuple[int, str]] = set()

        # -------------------------------------------------------------
        # 1. Duplicate Rows
        # -------------------------------------------------------------
        # Inject ~2% duplicate rows
        num_dupes = max(3, int(num_rows * 0.02))
        dupe_source_indices = rng.sample(range(num_rows), k=num_dupes)

        dupe_rows: list[dict[str, Any]] = []
        next_row_id = num_rows + 1

        for src_idx in dupe_source_indices:
            orig_row = df.iloc[src_idx].to_dict()
            orig_row_id = orig_row["_row_id"]
            new_row = dict(orig_row)
            new_row["_row_id"] = next_row_id

            manifest.append(
                {
                    "_row_id": next_row_id,
                    "table": table_name,
                    "column": "_row",
                    "issue_type": "duplicate_row",
                    "original_value": None,
                    "corrupted_value": f"duplicate_of_row_{orig_row_id}",
                    "details": {"original_row_id": orig_row_id},
                }
            )

            dupe_rows.append(new_row)
            next_row_id += 1

        if dupe_rows:
            df_dupes = pd.DataFrame(dupe_rows)
            df = pd.concat([df, df_dupes], ignore_index=True)

        # -------------------------------------------------------------
        # 2. Inconsistent Casing & Dirty Whitespace (Categorical columns)
        # -------------------------------------------------------------
        excluded = (
            "_row_id",
            "order_id",
            "sku",
            "return_id",
            "review_id",
            "customer_id",
            "review_text",
        )
        text_cols = [c for c in df.columns if c not in excluded and df[c].dtype == object]

        for col in text_cols:
            # 2a. Whitespace corruption (~3%)
            available_ws = [
                i for i in range(len(df)) if (int(df.at[i, "_row_id"]), col) not in corrupted_cells
            ]
            k_ws = min(len(available_ws), max(2, int(len(df) * 0.03)))
            ws_indices = rng.sample(available_ws, k=k_ws)

            for idx in ws_indices:
                row_id = int(df.at[idx, "_row_id"])
                val = str(df.at[idx, col])
                ws_style = rng.choice(["leading", "trailing", "both", "multiple_spaces"])
                if ws_style == "leading":
                    corrupted = f"   {val}"
                elif ws_style == "trailing":
                    corrupted = f"{val}  "
                elif ws_style == "both":
                    corrupted = f"  {val}   "
                else:
                    parts = val.split(" ")
                    corrupted = "   ".join(parts) if len(parts) > 1 else f"  {val}  "

                corrupted_cells.add((row_id, col))
                manifest.append(
                    {
                        "_row_id": row_id,
                        "table": table_name,
                        "column": col,
                        "issue_type": "dirty_whitespace",
                        "original_value": val,
                        "corrupted_value": corrupted,
                        "details": {"style": ws_style},
                    }
                )
                df.at[idx, col] = corrupted

            # 2b. Inconsistent Casing (~3%)
            available_case = [
                i for i in range(len(df)) if (int(df.at[i, "_row_id"]), col) not in corrupted_cells
            ]
            k_case = min(len(available_case), max(2, int(len(df) * 0.03)))
            case_indices = rng.sample(available_case, k=k_case)

            for idx in case_indices:
                row_id = int(df.at[idx, "_row_id"])
                val = str(df.at[idx, col])
                casing_style = rng.choice(["upper", "lower"])
                corrupted = val.upper() if casing_style == "upper" else val.lower()

                corrupted_cells.add((row_id, col))
                manifest.append(
                    {
                        "_row_id": row_id,
                        "table": table_name,
                        "column": col,
                        "issue_type": "inconsistent_casing",
                        "original_value": val,
                        "corrupted_value": corrupted,
                        "details": {"style": casing_style},
                    }
                )
                df.at[idx, col] = corrupted

        # -------------------------------------------------------------
        # 3. Category Spelling Variants / Typos (products table)
        # -------------------------------------------------------------
        if table_name == "products" and "category" in df.columns:
            available_cat = [
                i
                for i in range(len(df))
                if (int(df.at[i, "_row_id"]), "category") not in corrupted_cells
            ]
            k_cat = min(len(available_cat), max(5, int(len(df) * 0.10)))
            variant_indices = rng.sample(available_cat, k=k_cat)

            for idx in variant_indices:
                row_id = int(df.at[idx, "_row_id"])
                orig_cat = str(df.at[idx, "category"])
                if orig_cat in CATEGORY_VARIANTS:
                    corrupted = rng.choice(CATEGORY_VARIANTS[orig_cat])
                    corrupted_cells.add((row_id, "category"))
                    manifest.append(
                        {
                            "_row_id": row_id,
                            "table": table_name,
                            "column": "category",
                            "issue_type": "category_typo",
                            "original_value": orig_cat,
                            "corrupted_value": corrupted,
                            "details": {"target_canonical": orig_cat},
                        }
                    )
                    df.at[idx, "category"] = corrupted

        # -------------------------------------------------------------
        # 4. Mixed & Ambiguous Dates (date columns)
        # -------------------------------------------------------------
        date_cols = [c for c in df.columns if "date" in c]
        for col in date_cols:
            available_dates = [
                i for i in range(len(df)) if (int(df.at[i, "_row_id"]), col) not in corrupted_cells
            ]
            k_date = min(len(available_dates), max(5, int(len(df) * 0.05)))
            date_indices = rng.sample(available_dates, k=k_date)

            for idx in date_indices:
                row_id = int(df.at[idx, "_row_id"])
                orig_date_str = str(df.at[idx, col])
                try:
                    parts = orig_date_str.split("-")
                    year, month, day = parts[0], parts[1], parts[2]
                except Exception:
                    continue

                m_int, d_int = int(month), int(day)
                is_ambiguous = m_int <= 12 and d_int <= 12 and m_int != d_int

                if is_ambiguous:
                    # Ambiguous: 03/04/2024 (could be March 4 or April 3)
                    corrupted = f"{day}/{month}/{year}"
                    details = "ambiguous_date_format_dd_mm_or_mm_dd"
                else:
                    date_style = rng.choice(["slash_dmy", "dash_mdy", "slash_ymd", "timestamp"])
                    if date_style == "slash_dmy":
                        corrupted = f"{day}/{month}/{year}"
                        details = "DD/MM/YYYY"
                    elif date_style == "dash_mdy":
                        corrupted = f"{month}-{day}-{year}"
                        details = "MM-DD-YYYY"
                    elif date_style == "slash_ymd":
                        corrupted = f"{year}/{month}/{day}"
                        details = "YYYY/MM/DD"
                    else:
                        corrupted = f"{year}-{month}-{day} 08:30:00"
                        details = "timestamp"

                corrupted_cells.add((row_id, col))
                manifest.append(
                    {
                        "_row_id": row_id,
                        "table": table_name,
                        "column": col,
                        "issue_type": "mixed_date_format",
                        "original_value": orig_date_str,
                        "corrupted_value": corrupted,
                        "details": {"is_ambiguous": is_ambiguous, "format_style": details},
                    }
                )
                df.at[idx, col] = corrupted

        # -------------------------------------------------------------
        # 5. Dirty Numeric Formats (currency symbols, commas, strings)
        # -------------------------------------------------------------
        numeric_cols = [
            c
            for c in df.columns
            if c in ("mrp", "gross_amount", "discount_amount", "net_amount", "refund_amount")
        ]
        for col in numeric_cols:
            available_num = [
                i for i in range(len(df)) if (int(df.at[i, "_row_id"]), col) not in corrupted_cells
            ]
            k_num = min(len(available_num), max(5, int(len(df) * 0.04)))
            num_indices = rng.sample(available_num, k=k_num)

            for idx in num_indices:
                row_id = int(df.at[idx, "_row_id"])
                orig_val = float(df.at[idx, col])
                style = rng.choice(["usd_symbol", "inr_symbol", "comma_formatted", "padded_string"])
                if style == "usd_symbol":
                    corrupted = f"${orig_val:,.2f}"
                elif style == "inr_symbol":
                    corrupted = f"₹{orig_val:,.2f}"
                elif style == "comma_formatted":
                    corrupted = f"{orig_val:,.2f}"
                else:
                    corrupted = f"  {orig_val}  "

                corrupted_cells.add((row_id, col))
                manifest.append(
                    {
                        "_row_id": row_id,
                        "table": table_name,
                        "column": col,
                        "issue_type": "dirty_numeric",
                        "original_value": orig_val,
                        "corrupted_value": corrupted,
                        "details": {"style": style},
                    }
                )
                df.at[idx, col] = corrupted

        # -------------------------------------------------------------
        # 6. Missing Values (MCAR)
        # -------------------------------------------------------------
        nullable_cols = [
            c
            for c in df.columns
            if c not in ("_row_id", "order_id", "sku", "return_id", "review_id", "customer_id")
        ]
        for col in nullable_cols:
            available_miss = [
                i for i in range(len(df)) if (int(df.at[i, "_row_id"]), col) not in corrupted_cells
            ]
            k_miss = min(len(available_miss), max(2, int(len(df) * 0.02)))
            miss_indices = rng.sample(available_miss, k=k_miss)

            for idx in miss_indices:
                row_id = int(df.at[idx, "_row_id"])
                orig_val = df.at[idx, col]
                corrupted = None if rng.random() > 0.3 else ""

                corrupted_cells.add((row_id, col))
                manifest.append(
                    {
                        "_row_id": row_id,
                        "table": table_name,
                        "column": col,
                        "issue_type": "missing_value",
                        "original_value": orig_val,
                        "corrupted_value": corrupted,
                        "details": {"is_empty_string": corrupted == ""},
                    }
                )
                df.at[idx, col] = corrupted

        # -------------------------------------------------------------
        # 7. Outliers (quantity in orders)
        # -------------------------------------------------------------
        if table_name == "orders" and "quantity" in df.columns:
            available_out = [
                i
                for i in range(len(df))
                if (int(df.at[i, "_row_id"]), "quantity") not in corrupted_cells
                and df.at[i, "quantity"] not in (None, "")
            ]
            k_out = min(len(available_out), max(3, int(len(df) * 0.002)))
            outlier_indices = rng.sample(available_out, k=k_out)

            for idx in outlier_indices:
                row_id = int(df.at[idx, "_row_id"])
                orig_q = int(df.at[idx, "quantity"])
                corrupted_q = rng.choice([99, 500, 999])

                corrupted_cells.add((row_id, "quantity"))
                manifest.append(
                    {
                        "_row_id": row_id,
                        "table": table_name,
                        "column": "quantity",
                        "issue_type": "outlier",
                        "original_value": orig_q,
                        "corrupted_value": corrupted_q,
                        "details": {"metric": "extreme_quantity"},
                    }
                )
                df.at[idx, "quantity"] = corrupted_q

        messy_datasets[table_name] = df

    return messy_datasets, manifest


def save_messy_and_manifest(
    clean_datasets: dict[str, pd.DataFrame],
    messy_dir: str | Path = "data/raw_messy",
    ground_truth_dir: str | Path = "data/ground_truth",
    seed: int = 42,
) -> tuple[dict[str, Path], Path]:
    """Generates messy dataframes, saves CSVs and cell-level ground-truth manifest."""
    m_dir = Path(messy_dir)
    g_dir = Path(ground_truth_dir)
    m_dir.mkdir(parents=True, exist_ok=True)
    g_dir.mkdir(parents=True, exist_ok=True)

    messy_dfs, manifest = inject_corruptions(clean_datasets, seed=seed)

    saved_csvs: dict[str, Path] = {}
    for table_name, df in messy_dfs.items():
        out_file = m_dir / f"{table_name}.csv"
        df.to_csv(out_file, index=False)
        saved_csvs[table_name] = out_file

    manifest_file = g_dir / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)

    return saved_csvs, manifest_file
