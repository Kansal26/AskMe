"""Ask-the-Business Streamlit Application Entrypoint."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.app.styles import CUSTOM_CSS
from src.app.tab_ask import render_tab_ask
from src.app.tab_clean import render_tab_clean
from src.common.config import settings
from src.mcp_server.tools import run_sql

st.set_page_config(
    page_title="Ask-the-Business | Analytics & AI Engine",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject custom design CSS
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def main() -> None:
    """Main application layout and tab navigation."""
    # Top Synthetic Data Disclaimer Banner
    st.markdown(
        """
        <div class="synthetic-banner">
            🛡️ <strong>SYNTHETIC DATA DISCLAIMER:</strong> All e-commerce records (products, orders, returns, and reviews)
            are 100% synthetic, deterministically generated, and tracked via ground-truth manifest for portfolio evaluation.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Sidebar
    with st.sidebar:
        st.title("Ask-the-Business")
        st.caption("AI-Assisted Cleaning & Verifiable SQL Analytics")
        st.write("---")

        st.subheader("⚙️ Configuration")
        provider_choice = st.selectbox(
            "LLM Provider:",
            ["groq", "gemini"],
            index=0 if settings.llm_provider == "groq" else 1,
        )
        active_model = (
            settings.groq_model if provider_choice == "groq" else settings.gemini_model
        )
        st.caption(f"Active Model: `{active_model}`")

        st.write("---")
        st.subheader("📊 DuckDB Analytics Engine")
        db_path = Path(settings.duckdb_path)
        if db_path.exists():
            st.success("🟢 Connected (Read-Only)")
            # Show live record counts
            res = run_sql("SELECT COUNT(*) AS total_orders FROM orders")
            if res.get("status") == "success":
                cnt = res["rows"][0]["total_orders"]
                st.caption(f"Orders Ingested: **{cnt:,} records**")
        else:
            st.warning("🟠 Database not initialized. Please load data via the Clean tab.")

        st.write("---")
        st.subheader("🔗 Project Links")
        st.markdown(
            "- [GitHub Repository](https://github.com/Kansal26/AskMe)\n"
            "- [Architecture & Metrics Docs](file:///docs/architecture.md)\n"
            "- [Business Data Dictionary](file:///docs/data_dictionary.md)"
        )

    # Main Tabs
    tab1, tab2 = st.tabs([
        "🧹 1. Data Cleaning & Human Approval",
        "💬 2. Ask the Business (SQL Agent & Charts)",
    ])

    with tab1:
        render_tab_clean(llm_provider=provider_choice)

    with tab2:
        render_tab_ask(llm_provider=provider_choice)


if __name__ == "__main__":
    main()
