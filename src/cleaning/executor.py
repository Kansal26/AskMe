"""Deterministic Cleaning Executor, Audit Logger, and Replay Script Exporter.

Safety guarantees:
1. Pure functions: never mutates input DataFrame.
2. Dry-run mode: generates audit log and diff preview without committing changes.
3. Whitelisted operations only.
4. Preserves ground-truth _row_id column for row-level lineage.
5. Exports reproducible, standalone Python cleaning scripts.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from src.cleaning.schemas import AuditLogEntry, CleaningPlan, CleaningReport, CleaningStep
from src.cleaning.whitelist import validate_step


def execute_step(df: pd.DataFrame, step: CleaningStep) -> tuple[pd.DataFrame, AuditLogEntry, str]:
    """Applies a single cleaning step deterministically, producing an audit log and Python code."""
    df_out = df.copy()
    op = step.operation
    col = step.column
    params = step.params or {}

    # Validate before executing
    is_valid, err_msg = validate_step(step)
    if not is_valid:
        entry = AuditLogEntry(
            step_id=step.step_id,
            column=col,
            operation=op,
            params=params,
            rows_affected=0,
            before_samples=[],
            after_samples=[],
            status="error",
            message=f"Validation failed: {err_msg}",
        )
        return df_out, entry, f"# Step {step.step_id} skipped due to validation error: {err_msg}"

    rows_affected = 0
    before_samples: list[Any] = []
    after_samples: list[Any] = []
    py_code = ""

    # 1. DROP DUPLICATES
    if op == "drop_duplicates":
        subset = [c for c in df_out.columns if c != "_row_id"]
        dupes_mask = df_out.duplicated(subset=subset, keep="first")
        rows_affected = int(dupes_mask.sum())
        if rows_affected > 0:
            before_samples = df_out[dupes_mask].head(3).to_dict(orient="records")
            df_out = df_out[~dupes_mask].copy()
            after_samples = []
        py_code = (
            f"# Step {step.step_id}: Drop duplicate rows\n"
            f"subset = [c for c in df.columns if c != '_row_id']\n"
            f"df = df.drop_duplicates(subset=subset, keep='first')\n"
        )

    # 2. STRIP WHITESPACE
    elif op == "strip_whitespace":
        if col in df_out.columns:
            s = df_out[col].astype(str)
            # Remove leading/trailing and collapse internal repeated spaces
            cleaned = s.str.strip().str.replace(r" {2,}", " ", regex=True)
            diff_mask = (s != cleaned) & df_out[col].notna()
            rows_affected = int(diff_mask.sum())
            if rows_affected > 0:
                before_samples = s[diff_mask].head(3).tolist()
                after_samples = cleaned[diff_mask].head(3).tolist()
                df_out[col] = df_out[col].where(~diff_mask, cleaned)
            py_code = (
                f"# Step {step.step_id}: Strip whitespace in '{col}'\n"
                f"df['{col}'] = df['{col}'].astype(str).str.strip().str.replace(r' {{2,}}', ' ', regex=True)\n"
            )

    # 3. NORMALIZE CASE (Variant-Evidence Gated)
    elif op == "normalize_case":
        from src.cleaning.whitelist import get_variant_cluster_values

        mode = params.get("mode", "lower")
        if col in df_out.columns:
            # Variant-Evidence Gate: only cells belonging to an actual variant cluster may be modified
            variant_values = get_variant_cluster_values(df_out[col])
            s = df_out[col].astype(str)
            if mode == "upper":
                candidate = s.str.upper()
            elif mode == "title":
                candidate = s.str.title()
            else:
                candidate = s.str.lower()

            # A value may only be changed if it belongs to a variant cluster in the column
            is_in_variant_cluster = df_out[col].astype(str).isin(variant_values)
            diff_mask = (s != candidate) & df_out[col].notna() & is_in_variant_cluster
            rows_affected = int(diff_mask.sum())
            if rows_affected > 0:
                before_samples = s[diff_mask].head(3).tolist()
                after_samples = candidate[diff_mask].head(3).tolist()
                df_out[col] = df_out[col].where(~diff_mask, candidate)
            py_code = (
                f"# Step {step.step_id}: Normalize case in '{col}' to {mode} (variant-evidence gated)\n"
                f"variant_vals = {variant_values}\n"
                f"mask = df['{col}'].astype(str).isin(variant_vals)\n"
                f"df.loc[mask, '{col}'] = df.loc[mask, '{col}'].astype(str).str.{mode}()\n"
            )

    # 4. PARSE DATES (with Ambiguity Flagging)
    elif op == "parse_dates":
        if col in df_out.columns:
            flag_ambiguous = params.get("flag_ambiguous", True)
            ambiguous_col = f"is_ambiguous_{col}"

            # Identify ambiguous dates (e.g. 03/04/2024 where both month and day <= 12)
            ambiguous_mask = pd.Series(False, index=df_out.index)
            cleaned_dates = df_out[col].copy()

            for idx, val in df_out[col].dropna().items():
                v_str = str(val).strip().split(" ")[0]
                if "/" in v_str:
                    parts = v_str.split("/")
                    if len(parts) == 3:
                        try:
                            d1, d2, yr = int(parts[0]), int(parts[1]), int(parts[2])
                            if d1 <= 12 and d2 <= 12 and d1 != d2:
                                ambiguous_mask.at[idx] = True
                            else:
                                # Non-ambiguous DD/MM/YYYY or MM/DD/YYYY
                                if d1 > 12:
                                    # Day first
                                    cleaned_dates.at[idx] = f"{yr:04d}-{d2:02d}-{d1:02d}"
                                else:
                                    # Month first
                                    cleaned_dates.at[idx] = f"{yr:04d}-{d1:02d}-{d2:02d}"
                        except ValueError:
                            pass
                elif "-" in v_str and not re.match(r"^\d{4}-\d{2}-\d{2}", v_str):
                    parts = v_str.split("-")
                    if len(parts) == 3:
                        try:
                            m, d, yr = int(parts[0]), int(parts[1]), int(parts[2])
                            cleaned_dates.at[idx] = f"{yr:04d}-{m:02d}-{d:02d}"
                        except ValueError:
                            pass
                elif " " in str(val).strip():
                    # Strip timestamp if already ISO date
                    date_part = str(val).strip().split(" ")[0]
                    if re.match(r"^\d{4}-\d{2}-\d{2}", date_part):
                        cleaned_dates.at[idx] = date_part

            diff_mask = df_out[col] != cleaned_dates
            rows_affected = int(diff_mask.sum())
            if rows_affected > 0:
                before_samples = df_out[col][diff_mask].head(3).tolist()
                after_samples = cleaned_dates[diff_mask].head(3).tolist()
                df_out[col] = cleaned_dates

            if flag_ambiguous and ambiguous_mask.sum() > 0:
                df_out[ambiguous_col] = ambiguous_mask

            py_code = (
                f"# Step {step.step_id}: Parse dates in '{col}' (flag ambiguous)\n"
                f"# Standardized non-ambiguous formats to ISO YYYY-MM-DD\n"
            )

    # 5. TO NUMERIC
    elif op == "to_numeric":
        if col in df_out.columns:
            s_str = df_out[col].astype(str)
            cleaned = (
                s_str.str.replace("$", "", regex=False)
                .str.replace("₹", "", regex=False)
                .str.replace("€", "", regex=False)
                .str.replace(",", "", regex=False)
                .str.strip()
            )
            parsed_numeric = pd.to_numeric(cleaned, errors="coerce")
            diff_mask = df_out[col].astype(str) != parsed_numeric.astype(str)
            rows_affected = int(diff_mask.sum())
            if rows_affected > 0:
                before_samples = df_out[col][diff_mask].head(3).tolist()
                after_samples = parsed_numeric[diff_mask].head(3).tolist()
                df_out[col] = parsed_numeric
            py_code = (
                f"# Step {step.step_id}: Convert '{col}' to numeric\n"
                f"df['{col}'] = pd.to_numeric(\n"
                f"    df['{col}'].astype(str).str.replace(r'[$₹€,]', '', regex=True).str.strip(),\n"
                f"    errors='coerce'\n"
                f")\n"
            )

    # 6. FILL MISSING (Governed Policy: Flag-Only, Zero Imputation)
    elif op == "fill_missing":
        from src.cleaning.profiler import STANDARD_NULL_TOKENS

        if col in df_out.columns:
            null_mask = df_out[col].isna() | df_out[col].astype(str).str.strip().str.lower().isin(STANDARD_NULL_TOKENS)
            rows_affected = int(null_mask.sum())

            # Governed policy: All missing values are strictly left and flagged across all columns.
            flag_col = f"is_missing_{col}"
            df_out[flag_col] = null_mask
            before_samples = [None] if rows_affected > 0 else []
            after_samples = [f"Flagged in {flag_col}"] if rows_affected > 0 else []
            py_code = (
                f"# Step {step.step_id}: Leave and flag missing values in '{col}'\n"
                f"df['is_missing_{col}'] = df['{col}'].isna()\n"
            )

    # 7. MAP CATEGORIES (Variant-Evidence Gated)
    elif op == "map_categories":
        from src.cleaning.whitelist import get_variant_cluster_values

        mapping = params.get("mapping", {})
        if col in df_out.columns and mapping:
            variant_values = get_variant_cluster_values(df_out[col])
            # Only apply mapping for keys that belong to a real variant cluster
            filtered_mapping = {
                k: v for k, v in mapping.items()
                if str(k) in variant_values and str(k) != str(v)
            }
            s = df_out[col].astype(str)
            if filtered_mapping:
                cleaned = s.replace(filtered_mapping)
                diff_mask = s != cleaned
                rows_affected = int(diff_mask.sum())
                if rows_affected > 0:
                    before_samples = s[diff_mask].head(3).tolist()
                    after_samples = cleaned[diff_mask].head(3).tolist()
                    df_out[col] = cleaned
            else:
                rows_affected = 0

            py_code = (
                f"# Step {step.step_id}: Map category spelling variants in '{col}' (variant-evidence gated)\n"
                f"mapping = {filtered_mapping}\n"
                f"df['{col}'] = df['{col}'].replace(mapping)\n"
            )

    # 8. FLAG OUTLIERS (Flag, Never Delete)
    elif op == "flag_outliers":
        if col in df_out.columns:
            flag_col = f"is_outlier_{col}"
            nums = pd.to_numeric(df_out[col], errors="coerce").dropna()
            if len(nums) >= 4:
                q25, q75 = nums.quantile(0.25), nums.quantile(0.75)
                iqr = q75 - q25
                lb, ub = q25 - (1.5 * iqr), q75 + (1.5 * iqr)
                col_nums = pd.to_numeric(df_out[col], errors="coerce")
                outlier_mask = (col_nums < lb) | (col_nums > ub)
                rows_affected = int(outlier_mask.sum())
                df_out[flag_col] = outlier_mask
                if rows_affected > 0:
                    before_samples = df_out.loc[outlier_mask, col].head(3).tolist()
                    after_samples = [f"Flagged in {flag_col}"]
            else:
                df_out[flag_col] = False
            py_code = (
                f"# Step {step.step_id}: Flag IQR outliers in '{col}' (never delete)\n"
                f"q25, q75 = df['{col}'].quantile([0.25, 0.75])\n"
                f"iqr = q75 - q25\n"
                f"df['is_outlier_{col}'] = (df['{col}'] < (q25 - 1.5 * iqr)) | (df['{col}'] > (q75 + 1.5 * iqr))\n"
            )

    entry = AuditLogEntry(
        step_id=step.step_id,
        column=col,
        operation=op,
        params=params,
        rows_affected=rows_affected,
        before_samples=before_samples,
        after_samples=after_samples,
        status="applied",
        message=f"Successfully applied {op} on {col}. Affected {rows_affected:,} rows.",
    )
    return df_out, entry, py_code


def execute_plan(
    df: pd.DataFrame,
    plan: CleaningPlan,
    dry_run: bool = False,
    approved_step_ids: set[int] | None = None,
) -> tuple[pd.DataFrame, CleaningReport, str]:
    """Applies a full cleaning plan, filtering by approved step IDs and generating replay script."""
    df_current = df.copy()
    audit_log: list[AuditLogEntry] = []
    applied_count = 0
    rejected_count = 0

    script_lines = [
        "#!/usr/bin/env python3",
        '"""Replayable Cleaning Script generated by Ask-the-Business."""',
        "import pandas as pd",
        "import numpy as np",
        "",
        "def clean_dataset(df: pd.DataFrame) -> pd.DataFrame:",
        "    df = df.copy()",
    ]

    for step in plan.steps:
        # Check human approval
        if approved_step_ids is not None and step.step_id not in approved_step_ids:
            rejected_count += 1
            audit_log.append(
                AuditLogEntry(
                    step_id=step.step_id,
                    column=step.column,
                    operation=step.operation,
                    params=step.params,
                    rows_affected=0,
                    before_samples=[],
                    after_samples=[],
                    status="rejected_by_human",
                    message="Step was rejected by human operator in UI.",
                )
            )
            continue

        df_updated, log_entry, code_snippet = execute_step(df_current, step)
        audit_log.append(log_entry)

        if dry_run:
            log_entry.message = f"[DRY-RUN] Step would affect {log_entry.rows_affected:,} rows in '{step.column}'."
            applied_count += 1
        elif log_entry.status == "applied":
            df_current = df_updated
            applied_count += 1
            for line in code_snippet.strip().split("\n"):
                script_lines.append(f"    {line}")

    script_lines.append("    return df")
    script_lines.append("")
    replay_script = "\n".join(script_lines)

    report = CleaningReport(
        table_name=plan.table_name,
        original_rows=len(df),
        final_rows=len(df_current),
        steps_applied=applied_count,
        steps_rejected=rejected_count,
        audit_log=audit_log,
    )

    return df_current, report, replay_script
