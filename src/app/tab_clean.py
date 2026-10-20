"""Streamlit Tab 1: Human-in-the-Loop Data Cleaning & Governance."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.cleaning.executor import execute_plan
from src.cleaning.planner import generate_llm_plan, generate_rule_based_plan
from src.cleaning.profiler import profile_dataset
from src.db.loader import load_cleaned_data_to_duckdb


def render_tab_clean(llm_provider: str) -> None:
    """Renders interactive data cleaning interface."""
    st.subheader("🧹 Human-in-the-Loop Data Cleaning Pipeline")
    st.caption(
        "Design Rule: The AI **Proposes**, Deterministic Code **Executes**, and You **Approve**. "
        "The LLM never directly mutates or rewrites your data."
    )

    # 1. Dataset Selection / Upload
    st.write("#### 1. Select or Upload Dataset")
    col1, col2 = st.columns([1, 1])

    with col1:
        source_mode = st.radio(
            "Data Source:",
            ["Use Injected Messy Synthetic Dataset", "Upload Custom Messy CSV"],
            horizontal=True,
        )

    df_raw: pd.DataFrame | None = None
    table_name = "dataset"

    if source_mode == "Use Injected Messy Synthetic Dataset":
        with col2:
            messy_dir = Path("data/raw_messy")
            available_files = (
                [f.stem for f in sorted(messy_dir.glob("*.csv"))]
                if messy_dir.exists()
                else ["orders", "products", "returns", "reviews"]
            )
            selected_table = st.selectbox(
                "Choose a table with known injected corruptions:",
                available_files,
                index=0 if "orders" in available_files else 0,
            )
            table_name = selected_table
            file_path = messy_dir / f"{selected_table}.csv"
            if file_path.exists():
                df_raw = pd.read_csv(file_path)
            else:
                st.warning(f"File {file_path} not found. Please run Phase 0 data generation.")
    else:
        with col2:
            uploaded_file = st.file_uploader("Upload raw CSV file", type=["csv"])
            if uploaded_file is not None:
                table_name = uploaded_file.name.replace(".csv", "")
                df_raw = pd.read_csv(uploaded_file)

    if df_raw is None:
        st.info("Please select or upload a dataset to begin the profiling and cleaning process.")
        return

    # Raw Data Preview
    with st.expander(f"Raw Dataset Preview: `{table_name}` ({len(df_raw):,} rows, {len(df_raw.columns)} columns)", expanded=False):
        st.dataframe(df_raw.head(20), use_container_width=True)

    # 2. Statistical Profile & Quality Health Check
    st.write("---")
    st.write("#### 2. Dataset Health Profile")

    profile = profile_dataset(df_raw, table_name=table_name)
    total_rows = profile["total_rows"]
    dupe_count = profile["duplicate_rows_count"]

    # Calculate aggregate quality stats
    total_dirty_num = sum(c.get("dirty_numeric_count", 0) for c in profile["columns"].values())
    total_ambig_dates = sum(
        c.get("mixed_date_info", {}).get("ambiguous_count", 0)
        for c in profile["columns"].values()
    )
    total_whitespace = sum(
        c.get("whitespace_issues", {}).get("count", 0) for c in profile["columns"].values()
    )

    # Display KPI metrics cards
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Total Records", f"{total_rows:,}")
    with m2:
        st.metric("Duplicate Clones", f"{dupe_count:,}", delta_color="inverse")
    with m3:
        st.metric("Dirty Numerics ($, ₹)", f"{total_dirty_num:,}")
    with m4:
        st.metric("Ambiguous Dates", f"{total_ambig_dates:,}")
    with m5:
        st.metric("Whitespace Issues", f"{total_whitespace:,}")

    # Ambiguous Date Guard Warning
    if total_ambig_dates > 0:
        st.warning(
            f"⚠️ **Ambiguous Date Format Guard Active**: Found **{total_ambig_dates} dates** "
            rf"with ambiguous format (e.g., `03/04/2024` where month & day $\le 12$). "
            f"The system will **flag** them for explicit confirmation rather than guessing."
        )

    # Detailed Column Breakdown Expander
    with st.expander("View Column-by-Column Anomaly Breakdown"):
        col_summary_data = []
        for c_name, c_prof in profile["columns"].items():
            col_summary_data.append({
                "Column": c_name,
                "Inferred Type": c_prof["inferred_type"],
                "Missing Rate": f"{c_prof['null_rate']*100:.1f}% ({c_prof['null_count']})",
                "Whitespace Anomalies": c_prof.get("whitespace_issues", {}).get("count", 0),
                "Dirty Numbers": c_prof.get("dirty_numeric_count", 0),
                "Non-ISO Dates": c_prof.get("mixed_date_info", {}).get("non_iso_count", 0),
                "IQR Outliers": c_prof.get("iqr_outliers", {}).get("outlier_count", 0),
            })
        st.dataframe(pd.DataFrame(col_summary_data), use_container_width=True)

    # 3. Interactive Cleaning Proposal
    st.write("---")
    st.write("#### 3. AI-Assisted Cleaning Plan (Human Review)")

    plan_col1, plan_col2 = st.columns([1, 2])
    with plan_col1:
        planner_mode = st.radio(
            "Planner Mode:",
            ["Heuristic Rule-Based Planner (Instant)", "LLM Proposal Planner"],
            horizontal=True,
        )

    # Session state for plan
    plan_key = f"cleaning_plan_{table_name}"
    if plan_key not in st.session_state or st.button("Generate / Regenerate Cleaning Plan", type="primary"):
        with st.spinner("Analyzing profile and generating safe cleaning steps..."):
            if planner_mode == "LLM Proposal Planner":
                plan, notes = generate_llm_plan(profile, sample_df=df_raw)
            else:
                plan = generate_rule_based_plan(profile)
            st.session_state[plan_key] = plan

    current_plan = st.session_state.get(plan_key)
    if not current_plan or not current_plan.steps:
        st.success("No data quality issues found! Dataset is completely clean.")
        return

    st.info(f"**Plan Summary**: {current_plan.summary}")

    # Interactive Step Selection
    st.write("**Review & Approve Proposed Steps** (Uncheck to reject any step):")
    approved_step_ids: set[int] = set()

    for step in current_plan.steps:
        s_col1, s_col2, s_col3 = st.columns([1, 3, 2])
        with s_col1:
            is_approved = st.checkbox(
                f"Step {step.step_id}",
                value=True,
                key=f"step_toggle_{table_name}_{step.step_id}",
            )
            if is_approved:
                approved_step_ids.add(step.step_id)
        with s_col2:
            op_label = f"`{step.operation}` on `{step.column}`"
            st.markdown(f"**{op_label}** — {step.issue}")
            st.caption(f"*Rationale*: {step.rationale}")
        with s_col3:
            params_str = ", ".join(f"{k}={v}" for k, v in step.params.items()) if step.params else "Default"
            st.caption(f"Confidence: {step.confidence*100:.0f}% | Params: `{params_str}`")

    # 4. Execution & Export
    st.write("---")
    st.write("#### 4. Execute & Export Cleaned Data")

    exec_col1, exec_col2 = st.columns([1, 1])
    with exec_col1:
        dry_run_btn = st.button("Preview Dry Run")
    with exec_col2:
        apply_btn = st.button("Apply Approved Steps & Finalize", type="primary")

    if dry_run_btn or apply_btn:
        is_dry = bool(dry_run_btn and not apply_btn)
        with st.spinner("Executing approved cleaning steps deterministically..."):
            df_cleaned, report, replay_script = execute_plan(
                df=df_raw,
                plan=current_plan,
                dry_run=is_dry,
                approved_step_ids=approved_step_ids,
            )

        if is_dry:
            st.warning("🔎 **Dry Run Mode**: Showing execution preview without saving changes.")
        else:
            st.success(
                f"✅ **Execution Complete**: Applied {report.steps_applied} steps "
                f"({report.steps_rejected} rejected by operator)."
            )

        # Show audit log
        st.write("**Execution Audit Log:**")
        audit_rows = []
        for a in report.audit_log:
            audit_rows.append({
                "Step ID": a.step_id,
                "Target Column": a.column,
                "Operation": a.operation,
                "Status": a.status,
                "Rows Affected": a.rows_affected,
                "Message": a.message,
            })
        st.dataframe(pd.DataFrame(audit_rows), use_container_width=True)

        # Cleaned Data Preview
        st.write(f"**Cleaned Dataset Preview** ({len(df_cleaned):,} rows):")
        st.dataframe(df_cleaned.head(15), use_container_width=True)

        # Download Buttons
        d_col1, d_col2, d_col3 = st.columns(3)
        with d_col1:
            csv_data = df_cleaned.to_csv(index=False)
            st.download_button(
                label="📥 Download Cleaned CSV",
                data=csv_data,
                file_name=f"{table_name}_cleaned.csv",
                mime="text/csv",
            )
        with d_col2:
            st.download_button(
                label="📜 Download Replay Script (.py)",
                data=replay_script,
                file_name=f"clean_{table_name}_script.py",
                mime="text/x-python",
            )
        with d_col3:
            if st.button("⚡ Load to DuckDB Analytics DB"):
                with st.spinner("Updating DuckDB analytics tables..."):
                    try:
                        # Save cleaned CSV to data/clean/
                        out_dir = Path("data/clean")
                        out_dir.mkdir(parents=True, exist_ok=True)
                        save_p = out_dir / f"{table_name}.csv"
                        df_cleaned.to_csv(save_p, index=False)
                        load_cleaned_data_to_duckdb()
                        st.success(
                            f"Successfully refreshed DuckDB! Table '{table_name}' has {len(df_cleaned):,} rows."
                        )
                    except Exception as e:
                        st.error(f"Failed to load into DuckDB: {e}")
