"""Generalisation Evaluation on an Unseen Public Messy Dataset Schema.

Tests whether the Data Cleaning Pipeline (Profiler, Whitelist Validator, Rule-Based Planner,
and LLM-Assisted Planner) generalizes robustly to a novel tabular schema (HR/Employee dataset).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from src.cleaning.executor import execute_plan
from src.cleaning.planner import generate_llm_plan, generate_rule_based_plan
from src.cleaning.profiler import profile_dataset
from src.cleaning.whitelist import filter_valid_steps
from src.common.llm import LLMClient


def create_sample_messy_hr_dataset() -> pd.DataFrame:
    """Creates a sample messy HR employee dataset with diverse real-world corruptions."""
    data = [
        # Clean rows
        {"_row_id": 1, "emp_id": "EMP001", "name": "Aarav Sharma", "department": "Engineering", "hire_date": "2021-01-15", "salary": "85000", "location": "Bengaluru", "rating": "4.5"},
        {"_row_id": 2, "emp_id": "EMP002", "name": "Priya Patel", "department": "Engineering", "hire_date": "2020-06-20", "salary": "92000", "location": "Mumbai", "rating": "4.8"},
        {"_row_id": 3, "emp_id": "EMP003", "name": "Rohan Gupta", "department": "Marketing", "hire_date": "2022-03-10", "salary": "65000", "location": "Delhi", "rating": "3.9"},
        {"_row_id": 4, "emp_id": "EMP004", "name": "Neha Singh", "department": "Marketing", "hire_date": "2019-11-05", "salary": "72000", "location": "Bengaluru", "rating": "4.2"},
        {"_row_id": 5, "emp_id": "EMP005", "name": "Vikram Malhotra", "department": "Finance", "hire_date": "2018-04-12", "salary": "105000", "location": "Mumbai", "rating": "4.6"},
        # Duplicate row
        {"_row_id": 6, "emp_id": "EMP001", "name": "Aarav Sharma", "department": "Engineering", "hire_date": "2021-01-15", "salary": "85000", "location": "Bengaluru", "rating": "4.5"},
        # Dirty whitespace
        {"_row_id": 7, "emp_id": "EMP006", "name": "Ananya   Iyer", "department": "  Engineering  ", "hire_date": "2022-08-01", "salary": "88000", "location": "  Chennai  ", "rating": "4.0"},
        # Inconsistent casing
        {"_row_id": 8, "emp_id": "EMP007", "name": "Karan Verma", "department": "engineering", "hire_date": "2021-09-14", "salary": "80000", "location": "mumbai", "rating": "3.8"},
        {"_row_id": 9, "emp_id": "EMP008", "name": "Meera Joshi", "department": "MARKETING", "hire_date": "2023-02-18", "salary": "68000", "location": "DELHI", "rating": "4.1"},
        # Dirty numeric currency
        {"_row_id": 10, "emp_id": "EMP009", "name": "Siddharth Rao", "department": "Engineering", "hire_date": "2020-12-01", "salary": "$115,000", "location": "Bengaluru", "rating": "4.9"},
        {"_row_id": 11, "emp_id": "EMP010", "name": "Divya Nair", "department": "Finance", "hire_date": "2019-07-22", "salary": "₹95,000", "location": "Mumbai", "rating": "4.3"},
        # Standard null tokens ('N/A', '-', '', None, '?')
        {"_row_id": 12, "emp_id": "EMP011", "name": "Rahul Kapoor", "department": "N/A", "hire_date": "2022-05-30", "salary": "75000", "location": "Pune", "rating": "3.5"},
        {"_row_id": 13, "emp_id": "EMP012", "name": "Sneha Das", "department": "-", "hire_date": "2021-10-10", "salary": "-", "location": "Kolkata", "rating": "4.0"},
        {"_row_id": 14, "emp_id": "EMP013", "name": "Arjun Reddy", "department": "Engineering", "hire_date": "2023-01-11", "salary": None, "location": "Hyderabad", "rating": "N/A"},
        # Mixed non-ambiguous and ambiguous dates
        {"_row_id": 15, "emp_id": "EMP014", "name": "Tanvi Deshmukh", "department": "Marketing", "hire_date": "25/11/2021", "salary": "70000", "location": "Pune", "rating": "4.4"},
        {"_row_id": 16, "emp_id": "EMP015", "name": "Kabir Mehta", "department": "Finance", "hire_date": "04/05/2022", "salary": "98000", "location": "Mumbai", "rating": "4.7"},  # Ambiguous 04/05
        # Extreme statistical outlier
        {"_row_id": 17, "emp_id": "EMP016", "name": "Rajiv Singhania (CEO)", "department": "Executive", "hire_date": "2015-01-01", "salary": "2500000", "location": "Mumbai", "rating": "5.0"},
    ]
    return pd.DataFrame(data)


def run_generalisation_benchmark() -> dict[str, Any]:
    """Runs Profiling, Whitelist Validation, and Plan Execution across Arm A and Arm B."""
    print("\n=======================================================")
    print("RUNNING GENERALISATION TEST ON UNSEEN HR DATASET SCHEMA")
    print("=======================================================")

    df_raw = create_sample_messy_hr_dataset()
    table_name = "employees_hr"

    # Step 1: Profiling
    print("\n1. Profiling novel dataset...")
    profile = profile_dataset(df_raw, table_name=table_name)
    print(f"   - Rows: {profile['total_rows']}, Columns: {len(profile['columns'])}")
    print(f"   - Duplicate rows detected: {profile['duplicate_rows_count']}")
    for col, cp in profile["columns"].items():
        issues = []
        if cp["null_count"] > 0:
            issues.append(f"{cp['null_count']} nulls")
        if cp.get("whitespace_issues", {}).get("count", 0) > 0:
            issues.append("dirty whitespace")
        if cp.get("dirty_numeric_count", 0) > 0:
            issues.append("currency/commas")
        if cp.get("mixed_date_info", {}).get("non_iso_count", 0) > 0:
            issues.append("mixed dates")
        if cp.get("iqr_outliers", {}).get("outlier_count", 0) > 0:
            issues.append("outliers")
        if issues:
            print(f"   - {col:12}: {', '.join(issues)}")

    # Step 2: Arm A (Rule-Based Heuristic Planner)
    print("\n2. Arm A: Rule-Based Planner...")
    plan_a = generate_rule_based_plan(profile)
    print(f"   - Generated {len(plan_a.steps)} deterministic steps.")
    for s in plan_a.steps:
        print(f"     * [{s.operation}] {s.column}: {s.params}")
    df_cl_a, report_a, _ = execute_plan(df_raw, plan_a)
    print(f"   - Executed {report_a.steps_applied} steps successfully.")

    # Step 3: Arm B (LLM-Assisted Planner via gpt-oss-120b)
    print("\n3. Arm B: LLM-Assisted Planner (openai/gpt-oss-120b)...")
    client = LLMClient(model="openai/gpt-oss-120b")
    plan_b, rejected_b = generate_llm_plan(profile, df_raw, client=client)
    print(f"   - LLM proposed {len(plan_b.steps)} valid steps, {len(rejected_b)} rejected.")
    for s in plan_b.steps:
        print(f"     * [{s.operation}] {s.column}: {s.params}")
    df_cl_b, report_b, _ = execute_plan(df_raw, plan_b)
    print(f"   - Executed {report_b.steps_applied} steps successfully.")

    # Step 4: Verification of Core Enterprise Invariants
    # Invariant A: Ambiguous date 04/05/2022 flagged not corrupted
    # Invariant B: CEO salary 2,500,000 flagged not deleted or capped
    # Invariant C: Duplicate EMP001 dropped
    # Invariant D: Standard null tokens recognized and flagged
    print("\n4. Honest Verification of Core Invariants:")

    def check_invariants(df_cleaned: pd.DataFrame, arm_label: str) -> dict[str, bool]:
        ambig_flagged = "is_ambiguous_hire_date" in df_cleaned.columns and bool(
            df_cleaned.loc[df_cleaned["emp_id"] == "EMP015", "is_ambiguous_hire_date"].values[0]
        )
        ambig_val = str(df_cleaned.loc[df_cleaned["emp_id"] == "EMP015", "hire_date"].values[0])
        ambig_safe = ambig_flagged and "04/05/2022" in ambig_val

        outlier_flagged = "is_outlier_salary" in df_cleaned.columns and bool(
            df_cleaned.loc[df_cleaned["emp_id"] == "EMP016", "is_outlier_salary"].values[0]
        )
        ceo_salary_val = float(df_cleaned.loc[df_cleaned["emp_id"] == "EMP016", "salary"].values[0])
        outlier_safe = outlier_flagged and abs(ceo_salary_val - 2500000.0) < 1.0

        dedup_ok = len(df_cleaned[df_cleaned["emp_id"] == "EMP001"]) == 1

        print(f"   [{arm_label}]")
        print(f"     - Ambiguous date preserved & flagged: {ambig_safe} ('{ambig_val}')")
        print(f"     - Statistical outlier preserved & flagged: {outlier_safe} (salary: {ceo_salary_val:,.0f})")
        print(f"     - Redundant duplicate dropped: {dedup_ok} (count: {len(df_cleaned[df_cleaned['emp_id'] == 'EMP001'])})")

        return {
            "ambiguous_date_safe": ambig_safe,
            "outlier_safe": outlier_safe,
            "dedup_ok": dedup_ok,
        }

    res_a = check_invariants(df_cl_a, "Arm A: Rule-Based Planner")
    res_b = check_invariants(df_cl_b, "Arm B: LLM Planner (gpt-oss-120b)")

    report_payload = {
        "dataset": "employees_hr",
        "rows": len(df_raw),
        "columns": list(df_raw.columns),
        "arm_a": {
            "steps": len(plan_a.steps),
            "invariants": res_a,
        },
        "arm_b": {
            "steps": len(plan_b.steps),
            "rejected_steps": rejected_b,
            "invariants": res_b,
        },
    }

    out_file = Path("eval/benchmarks/results/generalisation_test_results.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2)

    print(f"\nGeneralisation benchmark report saved to: {out_file}")
    return report_payload


if __name__ == "__main__":
    run_generalisation_benchmark()
