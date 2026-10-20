"""Custom CSS styling and design system tokens for Streamlit."""

CUSTOM_CSS = """
<style>
/* Modern typography and container sizing */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Metric card styling */
.metric-container {
    background: linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.01) 100%);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 12px;
}

.metric-title {
    font-size: 0.85rem;
    font-weight: 500;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 4px;
}

.metric-value {
    font-size: 1.6rem;
    font-weight: 700;
    color: #f8fafc;
}

/* Badges */
.badge-clean {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    background-color: #065f46;
    color: #34d399;
}

.badge-warning {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    background-color: #78350f;
    color: #fbbf24;
}

.badge-citation {
    display: inline-block;
    background: #1e293b;
    border: 1px solid #334155;
    color: #38bdf8;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 500;
    margin-right: 6px;
    margin-bottom: 6px;
}

/* Synthetic data disclaimer header */
.synthetic-banner {
    background-color: #1e1b4b;
    border: 1px solid #4338ca;
    color: #c7d2fe;
    padding: 10px 16px;
    border-radius: 8px;
    font-size: 0.85rem;
    margin-bottom: 20px;
}

/* Refusal card styling */
.refusal-box {
    background-color: #451a03;
    border-left: 4px solid #f59e0b;
    padding: 16px;
    border-radius: 6px;
    color: #fef3c7;
    margin-top: 12px;
    margin-bottom: 12px;
}

/* Table styling polish */
div[data-testid="stDataFrame"] {
    border-radius: 8px;
    overflow: hidden;
}
</style>
"""
