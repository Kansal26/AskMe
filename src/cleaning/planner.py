"""Data Cleaning Planners: Deterministic Rule-Based Planner and LLM Proposal Planner.

Features:
- Arm A: Pure deterministic rule-based planner (used as baseline and fallback)
- Arm B: LLM proposal planner with compact profile payload and Pydantic validation
- Automatic retry on LLM failure, falling back to rule-based planner
- Whitelist validation on all proposed steps
"""

from __future__ import annotations

import json
import time
from typing import Any

import pandas as pd

from src.cleaning.schemas import CleaningPlan, CleaningStep
from src.cleaning.whitelist import filter_valid_steps
from src.common.llm import LLMClient

CLEANING_SYSTEM_PROMPT = """You are an expert Data Engineer assisting in preparing a messy tabular dataset for analytics.
Your role is strictly to PROPOSE cleaning steps. Deterministic code will execute the approved steps.

WHITELIST OF APPROVED OPERATIONS (You MUST choose ONLY from this list, using EXACT names):
1. drop_duplicates: params: {}
2. strip_whitespace: params: {} (removes leading/trailing and collapses internal repeated spaces)
3. normalize_case: params: {"mode": "lower" | "upper" | "title"} (Only permitted if variant evidence exists in the column!)
4. parse_dates: params: {"flag_ambiguous": true} (converts non-ambiguous formats to ISO YYYY-MM-DD; flags ambiguous DD/MM vs MM/DD like 03/04/2024 without altering)
5. to_numeric: params: {} (strips currency symbols $, ₹, €, and commas)
6. fill_missing: params: {"strategy": "leave_and_flag"} (FLAGS missing rows in is_missing_<column>; IMPUTATION IS STRICTLY PROHIBITED)
7. map_categories: params: {"mapping": {"typo_or_variant": "CanonicalName"}} (Only permitted for real variant clusters!)
8. flag_outliers: params: {"method": "iqr"} (flags anomalous rows; NEVER deletes or caps values)

CRITICAL SAFETY POLICY:
- ALL missing values MUST use strategy "leave_and_flag". Mode and constant imputation are strictly prohibited across all columns!
- normalize_case and map_categories may ONLY be proposed if distinct values in the column differ only by case/whitespace/edit-distance. Never blindly title-case clean columns.
- Outliers MUST use "flag_outliers". Never delete, winsorize, or cap outlier rows.

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
            steps.append(
                CleaningStep(
                    step_id=step_id,
                    column=col_name,
                    issue=f"{c_prof['null_count']} null or empty values ({c_prof['null_rate'] * 100:.1f}%)",
                    operation="fill_missing",
                    params={"strategy": "leave_and_flag"},
                    confidence=0.95,
                    rationale=(
                        f"Flag missing values in {col_name} via boolean indicator without imputation to guarantee zero data hallucination."
                    ),
                )
            )
            step_id += 1

    return CleaningPlan(
        table_name=table_name,
        summary=f"Rule-based plan: identified {len(steps)} deterministic cleaning steps.",
        steps=steps,
        metadata={
            "planner_type": "rule_based",
            "was_fallback": False,
            "fallback_reason": None,
            "steps_proposed_by_llm": 0,
            "steps_accepted": len(steps),
            "steps_rejected": 0,
            "rejected_reasons": [],
        },
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
            valid_steps, rejected_reasons = filter_valid_steps(raw_plan.steps, df=sample_df)
            valid_plan = CleaningPlan(
                table_name=table_name,
                summary=raw_plan.summary,
                steps=valid_steps,
                metadata={
                    "planner_type": "llm",
                    "was_fallback": False,
                    "fallback_reason": None,
                    "steps_proposed_by_llm": len(raw_plan.steps),
                    "steps_accepted": len(valid_steps),
                    "steps_rejected": len(rejected_reasons),
                    "rejected_reasons": rejected_reasons,
                },
            )
            return valid_plan, rejected_reasons
        except Exception as e:
            attempts += 1
            last_error = str(e)
            if attempts <= max_retries:
                sleep_sec = 2.0 * (2 ** (attempts - 1))
                time.sleep(sleep_sec)

    # Fallback to rule-based planner
    fallback = generate_rule_based_plan(profile)
    fallback.summary = (
        f"[Fallback to Rule-Based Planner after LLM error: {last_error[:100]}] {fallback.summary}"
    )
    fallback.metadata = {
        "planner_type": "llm_fallback_to_rule_based",
        "was_fallback": True,
        "fallback_reason": last_error,
        "steps_proposed_by_llm": 0,
        "steps_accepted": len(fallback.steps),
        "steps_rejected": 0,
        "rejected_reasons": [
            f"LLM generation failed ({last_error[:80]}), applied rule-based fallback"
        ],
    }
    return fallback, [f"LLM generation failed ({last_error[:80]}), applied rule-based fallback"]
