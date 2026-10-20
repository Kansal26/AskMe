"""Streamlit Tab 2: Natural Language SQL Agent & Interactive Analytics."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.agent.agent import AskBusinessAgent

SAMPLE_QUESTIONS = [
    "What is our total net revenue?",
    "What is our overall Average Order Value (AOV)?",
    "What is the total net revenue broken down by sales channel?",
    "Show me monthly net revenue for 2024.",
    "What is the return rate percentage for each product category?",
    "What is our overall repeat customer rate percentage?",
    "Who are the top 3 brands by net revenue?",
    "What was our customer acquisition cost (CAC) for Instagram marketing campaigns in 2024?",
]


def render_tab_ask(llm_provider: str) -> None:
    """Renders natural language question-answering tab with SQL citations and Plotly charts."""
    st.subheader("💬 Ask the Business")
    st.caption(
        "Ask questions in plain English. The agent retrieves governance metric rules, "
        "generates verified read-only DuckDB SQL, cites its definitions, and visualizes the results."
    )

    # 1. Quick Example Buttons
    st.write("**Quick Start Examples:**")
    q_cols = st.columns(4)
    selected_example = None

    for i, q_text in enumerate(SAMPLE_QUESTIONS[:4]):
        with q_cols[i]:
            if st.button(q_text, key=f"btn_ex_{i}"):
                selected_example = q_text

    q_cols2 = st.columns(4)
    for i, q_text in enumerate(SAMPLE_QUESTIONS[4:]):
        with q_cols2[i]:
            if st.button(q_text, key=f"btn_ex2_{i}"):
                selected_example = q_text

    # 2. Query Input Box
    query_input = st.text_input(
        "Enter your business question:",
        value=selected_example or "",
        placeholder="e.g. What is the return rate percentage by sales channel?",
    )

    ask_btn = st.button("Ask Question", type="primary")

    if ask_btn and query_input:
        agent = AskBusinessAgent(prompt_version="v2")

        with st.spinner("Analyzing question, retrieving metrics, and executing SQL..."):
            response = agent.answer_question(query_input)

        st.write("---")

        # 3. Handling Refusals & Unanswerable Questions
        if not response.can_answer:
            st.warning("⚠️ **Cannot Answer from Available Data**")
            st.markdown(
                f"<div style='background:#451a03; border-left:4px solid #f59e0b; padding:16px; border-radius:6px; color:#fef3c7;'>"
                f"<strong>Data Governance Refusal:</strong> {response.answer}</div>",
                unsafe_allow_html=True,
            )
            with st.expander("View Agent Thought Process"):
                st.write(response.thought_process)
            return

        # 4. Success Response
        st.success("✅ **Answer Generated**")

        # Cited Metric Pills
        if response.metric_citations:
            st.write("**Cited Metric Definitions:**")
            citations_html = ""
            for citation in response.metric_citations:
                citations_html += (
                    f"<span style='background:#1e293b; border:1px solid #334155; color:#38bdf8; "
                    f"padding:4px 10px; border-radius:6px; font-size:0.85rem; margin-right:8px;'>"
                    f"📐 {citation}</span>"
                )
            st.markdown(citations_html, unsafe_allow_html=True)
            st.write("")

        # Natural Language Answer
        st.markdown(f"### {response.answer}")

        # Collapsible SQL Expander
        with st.expander("🔍 View Validated DuckDB SQL Query", expanded=False):
            st.code(response.sql_query, language="sql")
            st.caption(
                "Execution Mode: Read-Only sandbox (`enable_external_access=false`, `lock_configuration=true`, `LIMIT 100`)."
            )

        # Tabular Results
        if response.sql_results:
            df_res = pd.DataFrame(response.sql_results)
            with st.expander(f"📊 Result Table ({len(df_res)} rows)", expanded=True):
                st.dataframe(df_res, use_container_width=True)

            # 5. Interactive Plotly Visualization
            if len(df_res) > 1 and len(df_res.columns) >= 2:
                st.write("#### 📈 Interactive Visualization")
                chart_spec = response.chart_spec
                c_type = chart_spec.chart_type if chart_spec else "bar"
                x_col = chart_spec.x_col if (chart_spec and chart_spec.x_col in df_res.columns) else df_res.columns[0]

                # Pick numeric column for y
                numeric_cols = df_res.select_dtypes(include=["number"]).columns.tolist()
                y_col = (
                    chart_spec.y_col
                    if (chart_spec and chart_spec.y_col in df_res.columns)
                    else (numeric_cols[0] if numeric_cols else df_res.columns[1])
                )

                title = (
                    chart_spec.title
                    if (chart_spec and chart_spec.title)
                    else f"{y_col.replace('_', ' ').title()} by {x_col.replace('_', ' ').title()}"
                )

                fig = None
                if c_type == "line" or "month" in str(x_col).lower() or "date" in str(x_col).lower():
                    fig = px.line(df_res, x=x_col, y=y_col, title=title, markers=True, template="plotly_dark")
                elif c_type == "scatter":
                    fig = px.scatter(df_res, x=x_col, y=y_col, title=title, template="plotly_dark")
                else:
                    fig = px.bar(df_res, x=x_col, y=y_col, title=title, template="plotly_dark")

                if fig:
                    fig.update_layout(
                        margin=dict(l=20, r=20, t=40, b=20),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig, use_container_width=True)
