"""Whitelist validation and parameter verification for cleaning operations.

Only 8 deterministic operations are allowed:
1. drop_duplicates
2. strip_whitespace
3. normalize_case (mode: 'lower' | 'upper' | 'title')
4. parse_dates (formats: list[str], flag_ambiguous: bool)
5. to_numeric (strip currency/commas)
6. fill_missing (strategy: 'median' | 'mode' | 'constant' | 'leave_and_flag')
7. map_categories (mapping: dict[str, str])
8. flag_outliers (flag, never delete)
"""

from __future__ import annotations

from src.cleaning.schemas import CleaningStep

ALLOWED_OPERATIONS = {
    "drop_duplicates",
    "strip_whitespace",
    "normalize_case",
    "parse_dates",
    "to_numeric",
    "fill_missing",
    "map_categories",
    "flag_outliers",
}

# Columns where imputation was historically considered; now all missing values are flag-only
HIGH_STAKES_COLUMNS = {
    "order_id",
    "customer_id",
    "sku",
    "return_id",
    "review_id",
    "order_date",
    "return_date",
    "review_date",
    "gross_amount",
    "discount_amount",
    "net_amount",
    "mrp",
    "refund_amount",
}


def levenshtein_distance(s1: str, s2: str) -> int:
    """Computes Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def are_variants(val1: str, val2: str) -> bool:
    """Checks whether two distinct values differ only by case, whitespace, or small edit-distance."""
    if val1 == val2:
        return False
    s1, s2 = str(val1).strip(), str(val2).strip()
    if not s1 or not s2:
        return False
    # 1. Differ only by case
    if s1.lower() == s2.lower():
        return True
    # 2. Differ only by whitespace (or case + whitespace)
    w1 = "".join(s1.split()).lower()
    w2 = "".join(s2.split()).lower()
    if w1 == w2:
        return True
    # 3. Differ only by small edit-distance (typos)
    if len(w1) >= 4 and len(w2) >= 4 and levenshtein_distance(w1, w2) <= 2:
        return True
    return False


def get_variant_cluster_values(series: Any) -> set[str]:
    """Returns the set of unique values in the series that belong to an actual variant cluster.

    A value belongs to a variant cluster if and only if another distinct value in the same
    series differs from it only by case, whitespace, or small edit-distance.
    """
    import pandas as pd

    if not isinstance(series, pd.Series):
        series = pd.Series(series)

    unique_vals = [str(v) for v in series.dropna().unique() if str(v).strip()]
    variant_values: set[str] = set()

    for i in range(len(unique_vals)):
        for j in range(i + 1, len(unique_vals)):
            v1, v2 = unique_vals[i], unique_vals[j]
            if are_variants(v1, v2):
                variant_values.add(v1)
                variant_values.add(v2)

    return variant_values


def validate_variant_evidence(df: Any, step: CleaningStep) -> tuple[bool, str]:
    """Validates that normalize_case or map_categories has empirical variant cluster evidence in the data.

    Returns (is_valid, rejection_reason).
    """
    op = step.operation
    col = step.column
    if op not in ("normalize_case", "map_categories"):
        return True, ""

    if col not in df.columns:
        return False, f"Column '{col}' does not exist in dataset."

    variant_values = get_variant_cluster_values(df[col])

    if not variant_values:
        return (
            False,
            f"Variant-evidence gate rejected '{op}' on '{col}': no variant cluster evidence exists in the column "
            f"(all values are distinct and uncontested).",
        )

    if op == "map_categories":
        mapping = step.params.get("mapping", {})
        # Check that at least one mapped source key exists in the column AND belongs to a variant cluster
        valid_mapped_sources = [k for k in mapping.keys() if str(k) in variant_values and k != mapping[k]]
        if not valid_mapped_sources:
            return (
                False,
                f"Variant-evidence gate rejected 'map_categories' on '{col}': none of the mapping sources {list(mapping.keys())} "
                f"belong to an actual variant cluster in the column.",
            )

    return True, ""


def validate_step(step: CleaningStep) -> tuple[bool, str]:
    """Validates that a proposed step strictly conforms to whitelist specifications.

    Returns (is_valid, error_message).
    """
    op = step.operation
    col = step.column
    params = step.params or {}

    if op not in ALLOWED_OPERATIONS:
        return (
            False,
            f"Operation '{op}' is not in the approved whitelist: {sorted(ALLOWED_OPERATIONS)}",
        )

    if op == "drop_duplicates":
        # Can be whole table or specific subset
        return True, ""

    if op == "strip_whitespace":
        # Target column required
        if not col or col == "_row":
            return False, "strip_whitespace requires a valid column name"
        return True, ""

    if op == "normalize_case":
        mode = params.get("mode", "lower")
        if mode not in ("lower", "upper", "title"):
            return False, f"normalize_case mode must be 'lower', 'upper', or 'title', got '{mode}'"
        return True, ""

    if op == "parse_dates":
        if not col or col == "_row":
            return False, "parse_dates requires a target column name"
        return True, ""

    if op == "to_numeric":
        if not col or col == "_row":
            return False, "to_numeric requires a target column name"
        return True, ""

    if op == "fill_missing":
        strategy = params.get("strategy", "leave_and_flag")
        # Governed Policy: All missing values are strictly left and flagged.
        # Mode and constant imputation are completely disabled across all columns to eliminate guesswork.
        if strategy != "leave_and_flag":
            return (
                False,
                f"Safety violation: fill_missing strategy '{strategy}' is prohibited. "
                f"All missing values must strictly use 'leave_and_flag' across all columns.",
            )
        return True, ""

    if op == "map_categories":
        mapping = params.get("mapping")
        if not isinstance(mapping, dict) or not mapping:
            return False, "map_categories requires a non-empty dictionary 'mapping' in params"
        return True, ""

    if op == "flag_outliers":
        if not col or col == "_row":
            return False, "flag_outliers requires a target column name"
        method = params.get("method", "iqr")
        if method not in ("iqr", "zscore", "threshold"):
            return (
                False,
                f"flag_outliers method must be 'iqr', 'zscore', or 'threshold', got '{method}'",
            )
        return True, ""

    return False, f"Unknown validation path for operation '{op}'"


def filter_valid_steps(
    steps: list[CleaningStep], df: Any = None
) -> tuple[list[CleaningStep], list[str]]:
    """Filters a list of steps, returning approved steps and a list of rejection reasons.

    If df is provided, applies the Variant-Evidence Gate to guard against harmful mutations.
    """
    valid_steps: list[CleaningStep] = []
    rejected_reasons: list[str] = []

    for step in steps:
        ok, msg = validate_step(step)
        if not ok:
            rejected_reasons.append(
                f"Step {step.step_id} ({step.operation} on {step.column}): {msg}"
            )
            continue

        if df is not None:
            v_ok, v_msg = validate_variant_evidence(df, step)
            if not v_ok:
                rejected_reasons.append(
                    f"Step {step.step_id} ({step.operation} on {step.column}): {v_msg}"
                )
                continue

        valid_steps.append(step)

    return valid_steps, rejected_reasons
