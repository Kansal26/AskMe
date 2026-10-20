"""Data Cleaning Planners: Deterministic Rule-Based Planner and LLM Proposal Planner.

Features:
- Arm A: Pure deterministic rule-based planner (used as baseline and fallback)
- Arm B: LLM proposal planner with compact profile payload and Pydantic validation
- Automatic retry on LLM failure, falling back to rule-based planner
- Whitelist validation on all proposed steps
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from src.cleaning.schemas import CleaningPlan, CleaningStep
from src.cleaning.whitelist import HIGH_STAKES_COLUMNS, filter_valid_steps
from src.common.llm import LLMClient

CLEANING_SYSTEM_PROMPT = """You are an expert Data Engineer assisting in preparing a messy tabular dataset for analytics.
Your role is strictly to PROPOSE cleaning steps. Deterministic code will execute the approved steps.

WHITELIST OF APPROVED OPERATIONS (You MUST choose ONLY from this list):
1. drop_duplicates: params: {}
2. strip_whitespace: params: {} (removes leading/trailing/multiple internal spaces)
3. normalize_case: params: {"mode": "lower" | "upper" | "title"}
4. parse_dates: params: {"flag_ambiguous": true} (converts to ISO YYYY-MM-DD and flags ambiguous formats like 03/04/2024 for human confirmation)
5. to_numeric: params: {} (strips currency symbols $, ₹, €, and thousand commas)
6. fill_missing: params: {"strategy": "median" | "mode" | "constant" | "leave_and_flag", "value": ...}
   CRITICAL SAFETY RULE: For monetary amounts, IDs, and dates, you MUST use "leave_and_flag". Never impute high-stakes columns!
7. map_categories: params: {"mapping": {"typo_or_variant": "CanonicalName"}}
8. flag_outliers: params: {"method": "iqr"} (flags anomalous rows; NEVER deletes them)

Respond strictly with a JSON object conforming to the CleaningPlan schema.
"""


def generate_rule_based_plan(profile: dict[str, Any]) -> CleaningPlan:
    """Generates a deterministic cleaning plan using pure heuristic rules."""
    table_name = profile.get("table_name", "dataset")
    steps: list[CleaningStep] = []
    step_id = 1

    # 1. Duplicates
    if profile.get("duplicate_rows_count", 0) > 0:
        steps.append(
            CleaningStep(
                step_id=step_id,
                column="_row",
                issue=f"{profile['duplicate_rows_count']} duplicate rows detected",
                operation="drop_duplicates",
                params={},
                confidence=1.0,
                rationale="Eliminate redundant duplicate records keeping the first authentic occurrence.",
            )
        )
        step_id += 1

    # Per-column rules
    for col_name, c_prof in profile.get("columns", {}).items():
        # 2. Whitespace
        ws = c_prof.get("whitespace_issues", {})
        if ws.get("count", 0) > 0:
            steps.append(
                CleaningStep(
                    step_id=step_id,
                    column=col_name,
                    issue=f"{ws['count']} values with dirty whitespace",
                    operation="strip_whitespace",
                    params={},
                    confidence=0.98,
                    rationale=f"Trim leading/trailing and excess internal spaces in {col_name}.",
                )
            )
            step_id += 1

        # 3. Numeric in String / Dirty Numeric
        if c_prof.get("dirty_numeric_count", 0) > 0:
            steps.append(
                CleaningStep(
                    step_id=step_id,
                    column=col_name,
                    issue=f"{c_prof['dirty_numeric_count']} numbers contain currency symbols or commas",
                    operation="to_numeric",
                    params={},
                    confidence=0.99,
                    rationale=f"Convert string representation of {col_name} to clean numerical float.",
                )
            )
            step_id += 1

        # 4. Mixed Dates
        date_info = c_prof.get("mixed_date_info", {})
        if date_info.get("non_iso_count", 0) > 0:
            ambig = date_info.get("ambiguous_count", 0)
            steps.append(
                CleaningStep(
                    step_id=step_id,
                    column=col_name,
                    issue=f"{date_info['non_iso_count']} non-ISO dates found ({ambig} ambiguous)",
                    operation="parse_dates",
                    params={"flag_ambiguous": True},
                    confidence=0.95,
                    rationale=(
                        f"Standardize {col_name} to YYYY-MM-DD, flagging ambiguous DD/MM vs MM/DD formats."
                    ),
                )
            )
            step_id += 1

        # 5. Casing Variants (Targeted mapping to dominant casing to preserve clean rows)
        casing_map = c_prof.get("casing_fix_mapping", {})
        if casing_map:
            steps.append(
                CleaningStep(
                    step_id=step_id,
                    column=col_name,
                    issue=f"{len(casing_map)} anomalous casing variants detected",
                    operation="map_categories",
                    params={"mapping": casing_map},
                    confidence=0.95,
                    rationale=(
                        f"Align minority casing variants in {col_name} to dominant canonical form "
                        f"without altering properly cased entries."
                    ),
                )
            )
            step_id += 1

        # 6. Category Typo Clusters (Targeted mapping to dominant category)
        typo_map = c_prof.get("category_typo_fix_mapping", {})
        if typo_map:
            steps.append(
                CleaningStep(
                    step_id=step_id,
                    column=col_name,
                    issue=f"{len(typo_map)} category spelling variants detected",
                    operation="map_categories",
                    params={"mapping": typo_map},
                    confidence=0.92,
                    rationale=f"Map spelling variants in {col_name} to dominant canonical categories.",
                )
            )
            step_id += 1

        # 7. Outliers
        outliers = c_prof.get("iqr_outliers", {})
        if outliers.get("outlier_count", 0) > 0:
            steps.append(
                CleaningStep(
                    step_id=step_id,
                    column=col_name,
                    issue=f"{outliers['outlier_count']} statistical IQR outliers detected",
                    operation="flag_outliers",
                    params={"method": "iqr"},
                    confidence=0.85,
                    rationale=f"Flag extreme values in {col_name} for analytical segmentation.",
                )
            )
            step_id += 1

        # 8. Missing Values
        if c_prof.get("null_count", 0) > 0:
            strategy = "leave_and_flag" if col_name.lower() in HIGH_STAKES_COLUMNS else "mode"
            steps.append(
                CleaningStep(
                    step_id=step_id,
                    column=col_name,
                    issue=f"{c_prof['null_count']} null or empty values ({c_prof['null_rate'] * 100:.1f}%)",
                    operation="fill_missing",
                    params={"strategy": strategy},
                    confidence=0.90,
                    rationale=(
                        f"Handle missing values in {col_name} via {strategy} "
                        f"(high-stakes columns are never imputed)."
                    ),
                )
            )
            step_id += 1

    return CleaningPlan(
        table_name=table_name,
        summary=f"Rule-based plan: identified {len(steps)} deterministic cleaning steps.",
        steps=steps,
    )


def generate_llm_plan(
    profile: dict[str, Any],
    sample_df: pd.DataFrame,
    client: LLMClient | None = None,
    max_retries: int = 1,
) -> tuple[CleaningPlan, list[str]]:
    """Sends dataset profile and sanitized row samples to LLM to produce a validated cleaning plan.

    Falls back to rule-based planner if LLM fails after retries.
    """
    if client is None:
        client = LLMClient()

    table_name = profile.get("table_name", "dataset")

    # Sanitize sample rows (take up to 5 rows, drop _row_id to prevent leaking synthetic IDs)
    clean_sample_df = sample_df.drop(columns=["_row_id"], errors="ignore").head(5)
    sample_rows = clean_sample_df.fillna("").to_dict(orient="records")

    prompt_payload = {
        "dataset_name": table_name,
        "total_rows": profile.get("total_rows"),
        "duplicate_rows": profile.get("duplicate_rows_count"),
        "column_profiles": profile.get("columns"),
        "sample_rows": sample_rows,
    }

    user_prompt = (
        f"Analyze this dataset profile and sample rows, and propose an optimal, "
        f"safe cleaning plan:\n\n{json.dumps(prompt_payload, indent=2, default=str)}"
    )

    attempts = 0
    last_error = ""

    while attempts <= max_retries:
        try:
            response = client.generate_structured(
                prompt=user_prompt,
                system_instruction=CLEANING_SYSTEM_PROMPT,
                schema=CleaningPlan,
                temperature=0.0,
            )
            raw_plan: CleaningPlan = response.parsed
            valid_steps, rejected_reasons = filter_valid_steps(raw_plan.steps)
            valid_plan = CleaningPlan(
                table_name=table_name,
                summary=raw_plan.summary,
                steps=valid_steps,
            )
            return valid_plan, rejected_reasons
        except Exception as e:
            attempts += 1
            last_error = str(e)

    # Fallback to rule-based planner
    fallback = generate_rule_based_plan(profile)
    fallback.summary = (
        f"[Fallback to Rule-Based Planner after LLM error: {last_error[:100]}] {fallback.summary}"
    )
    return fallback, [f"LLM generation failed ({last_error[:80]}), applied rule-based fallback"]
