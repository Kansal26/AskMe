"""Pure Pandas Dataset Profiler for Health and Anomaly Detection.

Extracts column-level metrics:
- Inferred semantic types
- Null rate and empty string counts
- Duplicate rows count (excluding _row_id)
- Mixed date format detection and ambiguous DD/MM vs MM/DD flags
- Whitespace anomalies (leading, trailing, multiple internal spaces)
- Inconsistent casing (same word with different casing)
- Numeric-in-string detection (currency symbols, commas)
- Category spelling variants (fuzzy/case-insensitive clusters)
- Statistical IQR outliers
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

# Regex patterns
RE_CURRENCY_OR_COMMAS = re.compile(r"[$₹€£,]|^\s*\d+(\.\d+)?\s*$")
RE_DATE_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}")
RE_DATE_SLASH_DMY_OR_MDY = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}")
RE_DATE_DASH_MDY = re.compile(r"^\d{1,2}-\d{1,2}-\d{4}")


# Standard null tokens across tabular CSV sources
STANDARD_NULL_TOKENS = {
    "",
    "nan",
    "null",
    "none",
    "n/a",
    "na",
    "-",
    "--",
    "?",
    r"\n",
    r"\N",
}


def _infer_semantic_type(series: pd.Series) -> str:
    """Infers high-level semantic type: 'numeric', 'date', 'categorical', or 'text'."""
    non_nulls = series.dropna().astype(str).str.strip()
    non_nulls = non_nulls[~non_nulls.str.lower().isin(STANDARD_NULL_TOKENS)]
    if len(non_nulls) == 0:
        return "empty"

    # Sample up to 100 values for fast inference
    sample = non_nulls.head(100)

    # Check numeric (either native numeric or strings with numbers/currencies)
    num_numeric = sum(
        1 for v in sample if re.match(r"^[$₹€£]?\s*[\d,]+(\.\d+)?\s*$", v.replace(" ", ""))
    )
    if num_numeric / len(sample) > 0.8:
        return "numeric"

    # Check date
    num_dates = sum(
        1
        for v in sample
        if RE_DATE_ISO.match(v) or RE_DATE_SLASH_DMY_OR_MDY.match(v) or RE_DATE_DASH_MDY.match(v)
    )
    if num_dates / len(sample) > 0.7:
        return "date"

    # Check categorical vs free text
    unique_count = non_nulls.nunique()
    if unique_count <= 50 or (unique_count / len(non_nulls)) < 0.2:
        return "categorical"

    return "text"


def profile_column(col_name: str, series: pd.Series) -> dict[str, Any]:
    """Profiles a single column for quality issues, distributions, and outliers."""
    total_count = len(series)

    # Missing / empty string / standard null token count
    is_null_mask = series.isna() | series.astype(str).str.strip().str.lower().isin(STANDARD_NULL_TOKENS)
    null_count = int(is_null_mask.sum())
    null_rate = round(null_count / total_count, 4) if total_count > 0 else 0.0

    non_null_series = series[~is_null_mask]
    non_null_str = non_null_series.astype(str)

    inferred_type = _infer_semantic_type(series)
    profile: dict[str, Any] = {
        "column": col_name,
        "inferred_type": inferred_type,
        "total_rows": total_count,
        "null_count": null_count,
        "null_rate": null_rate,
        "sample_values": non_null_str.head(5).tolist(),
    }

    if len(non_null_str) == 0:
        return profile

    # 1. Whitespace Anomalies
    has_leading = non_null_str.str.startswith(" ").sum()
    has_trailing = non_null_str.str.endswith(" ").sum()
    has_multi_space = non_null_str.str.contains(r" {2,}", regex=True).sum()
    total_ws_issues = int(has_leading + has_trailing + has_multi_space)
    profile["whitespace_issues"] = {
        "count": total_ws_issues,
        "leading": int(has_leading),
        "trailing": int(has_trailing),
        "multi_space": int(has_multi_space),
    }

    # 2. Inconsistent Casing (for text/categorical)
    if inferred_type in ("categorical", "text"):
        uniques = non_null_str.str.strip().unique()
        lower_map: dict[str, list[str]] = {}
        for val in uniques:
            low = val.lower()
            lower_map.setdefault(low, []).append(val)

        casing_variants = {
            low: vars_list for low, vars_list in lower_map.items() if len(vars_list) > 1
        }
        profile["casing_variants"] = casing_variants

        # Find dominant canonical variant to prevent damaging properly cased data
        casing_fix_map: dict[str, str] = {}
        for low, vars_list in casing_variants.items():
            subset = non_null_str[non_null_str.str.lower() == low]
            if len(subset) > 0:
                counts = subset.value_counts()
                canonical = counts.index[0]
                for v in vars_list:
                    if v != canonical:
                        casing_fix_map[v] = canonical
        profile["casing_fix_mapping"] = casing_fix_map

    # 3. Numeric in String (currency symbols, commas)
    if inferred_type == "numeric" or series.dtype == object:
        dirty_num_count = sum(
            1 for v in non_null_str if ("$" in v or "₹" in v or "€" in v or "," in v)
        )
        profile["dirty_numeric_count"] = int(dirty_num_count)

    # 4. Mixed & Ambiguous Dates
    if inferred_type == "date" or "date" in col_name.lower():
        non_iso_count = 0
        ambiguous_count = 0
        formats_found = set()

        for v in non_null_str:
            clean_v = v.strip().split(" ")[0]
            if RE_DATE_ISO.match(clean_v):
                formats_found.add("YYYY-MM-DD")
            elif "/" in clean_v:
                formats_found.add("slash_format")
                non_iso_count += 1
                parts = clean_v.split("/")
                if len(parts) == 3:
                    try:
                        p1, p2 = int(parts[0]), int(parts[1])
                        if p1 <= 12 and p2 <= 12 and p1 != p2:
                            ambiguous_count += 1
                    except ValueError:
                        pass
            elif "-" in clean_v and not RE_DATE_ISO.match(clean_v):
                formats_found.add("dash_non_iso")
                non_iso_count += 1

        profile["mixed_date_info"] = {
            "non_iso_count": non_iso_count,
            "ambiguous_count": ambiguous_count,
            "formats_detected": sorted(formats_found),
        }

    # 5. Category Typos / Fuzzy Variants (for categorical)
    if inferred_type == "categorical":
        clean_uniques = [v.strip() for v in non_null_str.unique()]
        clusters: dict[str, list[str]] = {}
        for v in clean_uniques:
            norm_key = re.sub(r"[\s\-_&]+", "", v).lower()
            clusters.setdefault(norm_key, []).append(v)

        typo_clusters = {k: v for k, v in clusters.items() if len(v) > 1}
        profile["category_variant_clusters"] = typo_clusters

        typo_fix_map: dict[str, str] = {}
        for norm_key, variants in typo_clusters.items():
            subset = non_null_str[
                non_null_str.str.replace(r"[\s\-_&]+", "", regex=True).str.lower() == norm_key
            ]
            if len(subset) > 0:
                counts = subset.value_counts()
                canonical = counts.index[0]
                for v in variants:
                    if v != canonical:
                        typo_fix_map[v] = canonical
        profile["category_typo_fix_mapping"] = typo_fix_map

    # 6. IQR Outliers (for numeric columns)
    if inferred_type == "numeric":
        # Extract numeric series
        clean_nums = (
            non_null_str.str.replace("$", "", regex=False)
            .str.replace("₹", "", regex=False)
            .str.replace("€", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.strip()
        )
        numeric_series = pd.to_numeric(clean_nums, errors="coerce").dropna()
        if len(numeric_series) >= 4:
            q25 = float(numeric_series.quantile(0.25))
            q75 = float(numeric_series.quantile(0.75))
            iqr = q75 - q25
            lower_bound = q25 - (1.5 * iqr)
            upper_bound = q75 + (1.5 * iqr)
            outliers = numeric_series[
                (numeric_series < lower_bound) | (numeric_series > upper_bound)
            ]
            profile["iqr_outliers"] = {
                "q25": round(q25, 2),
                "q75": round(q75, 2),
                "iqr": round(iqr, 2),
                "lower_bound": round(lower_bound, 2),
                "upper_bound": round(upper_bound, 2),
                "outlier_count": int(len(outliers)),
                "samples": [float(x) for x in outliers.head(5).tolist()],
            }

    return profile


def profile_dataset(df: pd.DataFrame, table_name: str = "") -> dict[str, Any]:
    """Computes comprehensive table-level and column-level quality profile."""
    # Count duplicate rows excluding _row_id if present
    cols_to_check = [c for c in df.columns if c != "_row_id"]
    duplicate_rows_count = int(df.duplicated(subset=cols_to_check).sum())

    column_profiles = {}
    for col in df.columns:
        if col == "_row_id":
            continue
        column_profiles[col] = profile_column(col, df[col])

    return {
        "table_name": table_name,
        "total_rows": len(df),
        "total_columns": len(cols_to_check),
        "duplicate_rows_count": duplicate_rows_count,
        "columns": column_profiles,
    }
