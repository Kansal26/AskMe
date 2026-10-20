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

# High-stakes columns where imputation is disallowed; defaults to 'leave_and_flag'
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


# Columns explicitly designated as low-stakes categorical where mode/constant imputation is permitted
LOW_STAKES_CATEGORICAL_COLUMNS = {
    "channel",
    "city",
    "category",
    "brand",
    "reason",
}


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
        allowed_strategies = ("mode", "constant", "leave_and_flag")
        if strategy not in allowed_strategies:
            return (
                False,
                f"fill_missing strategy must be one of {allowed_strategies}, got '{strategy}'",
            )
        col_lower = col.lower()
        # High-stakes guard: amounts, IDs, dates, and non-categorical fields must NEVER be imputed
        if strategy != "leave_and_flag":
            if col_lower in HIGH_STAKES_COLUMNS:
                return (
                    False,
                    f"Safety violation: High-stakes column '{col}' (amount, ID, or date) cannot be imputed with '{strategy}'. "
                    f"Must use 'leave_and_flag'.",
                )
            if col_lower not in LOW_STAKES_CATEGORICAL_COLUMNS:
                return (
                    False,
                    f"Safety violation: Column '{col}' is not an approved low-stakes categorical field. "
                    f"Imputation is only permitted for: {sorted(LOW_STAKES_CATEGORICAL_COLUMNS)}. "
                    f"Must use 'leave_and_flag'.",
                )
        if strategy == "constant" and "value" not in params:
            return False, "fill_missing with strategy='constant' requires 'value' parameter"
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


def filter_valid_steps(steps: list[CleaningStep]) -> tuple[list[CleaningStep], list[str]]:
    """Filters a list of steps, returning approved steps and a list of rejection reasons."""
    valid_steps: list[CleaningStep] = []
    rejected_reasons: list[str] = []

    for step in steps:
        ok, msg = validate_step(step)
        if ok:
            valid_steps.append(step)
        else:
            rejected_reasons.append(
                f"Step {step.step_id} ({step.operation} on {step.column}): {msg}"
            )

    return valid_steps, rejected_reasons
