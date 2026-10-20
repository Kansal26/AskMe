"""Plain Tool-Calling SQL Agent with Self-Correction and Refusal Capabilities.

Design highlights:
- Pure Python tool-calling loop (no LangChain / heavy frameworks)
- In-process execution of core MCP tools
- Automatic self-correction on SQL errors (up to 3 retries)
- Explicit refusal mechanism for out-of-scope or unanswerable queries
- Generates chart specifications for Plotly visualization
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from src.agent.prompts import (
    PROMPT_V1_SCHEMA_ONLY,
    PROMPT_V2_GOVERNED,
    PROMPT_V3_FEWSHOT_AND_CORRECTION,
)
from src.common.llm import LLMClient
from src.mcp_server import tools


class ChartSpec(BaseModel):
    """Specification for Plotly interactive visualization."""

    chart_type: Literal["bar", "line", "scatter", "pie", "none"] = Field(
        default="none", description="Type of visual chart"
    )
    x_col: str | None = Field(default=None, description="Column name for X axis")
    y_col: str | None = Field(default=None, description="Column name for Y axis")
    title: str | None = Field(default=None, description="Chart title")


class AgentPlanProposal(BaseModel):
    """Pydantic model for LLM query plan and SQL proposal."""

    can_answer: bool = Field(
        ..., description="True if query is answerable from available schema; False if impossible"
    )
    refusal_reason: str | None = Field(
        default=None, description="Reason if question cannot be answered from data"
    )
    thought_process: str = Field(..., description="Step-by-step reasoning and metric alignment")
    metric_citations: list[str] = Field(
        default_factory=list, description="Official business metrics referenced in answering"
    )
    sql_query: str | None = Field(default=None, description="Generated read-only DuckDB SQL query")
    chart_spec: ChartSpec | None = Field(
        default=None, description="Recommended chart specification"
    )


class AgentResponse(BaseModel):
    """Final response returned to UI or evaluation benchmark."""

    can_answer: bool
    refusal_reason: str | None = None
    thought_process: str
    metric_citations: list[str] = Field(default_factory=list)
    sql_query: str | None = None
    answer: str
    chart_spec: ChartSpec | None = None
    sql_results: list[dict[str, Any]] | None = None
    sql_error: str | None = None
    attempts_taken: int = 1


class AskBusinessAgent:
    """Natural Language SQL Agent for D2C E-Commerce Analytics."""

    def __init__(
        self,
        prompt_version: Literal["v1", "v2", "v3"] = "v3",
        client: LLMClient | None = None,
        max_retries: int = 3,
    ) -> None:
        self.prompt_version = prompt_version
        if prompt_version == "v1":
            self.system_prompt = PROMPT_V1_SCHEMA_ONLY
            self.max_retries = 1  # Baseline is single-pass without self-correction
        elif prompt_version == "v2":
            self.system_prompt = PROMPT_V2_GOVERNED
            self.max_retries = 1  # Governed ablation without self-correction
        else:
            self.system_prompt = PROMPT_V3_FEWSHOT_AND_CORRECTION
            self.max_retries = max_retries  # Governed + worked examples + self-correction retry loop

        self.client = client or LLMClient()

    def answer_question(self, question: str) -> AgentResponse:
        """Executes the agent tool-calling and self-correction loop to answer a question."""
        # 1. Metric Definition Lookup (in-process MCP tool for governed arms v2 and v3)
        metric_context = ""
        if self.prompt_version in ("v2", "v3"):
            for term in ["aov", "net revenue", "gross revenue", "return rate", "repeat customer", "rating"]:
                if term in question.lower():
                    metric_def = tools.get_metric_definition(term)
                    if metric_def.get("status") == "found":
                        m = metric_def["metric"]
                        metric_context += (
                            f"\n[Cited Metric Rule: {m.get('metric_name')}] Formula: {m.get('formula')}"
                        )

        user_prompt = f"User Question: {question}\n{metric_context}".strip()

        attempts = 0
        error_context = ""
        current_sql = None
        sql_results = None
        proposal: AgentPlanProposal | None = None

        while attempts < self.max_retries:
            attempts += 1
            prompt_with_history = user_prompt
            if error_context:
                prompt_with_history += f"\n\nPREVIOUS ERROR TO FIX:\n{error_context}"

            try:
                response = self.client.generate_structured(
                    prompt=prompt_with_history,
                    system_instruction=self.system_prompt,
                    schema=AgentPlanProposal,
                    temperature=0.0,
                )
                proposal = response.parsed

                # If model politely refused:
                if not proposal.can_answer:
                    return AgentResponse(
                        can_answer=False,
                        refusal_reason=proposal.refusal_reason,
                        thought_process=proposal.thought_process,
                        metric_citations=proposal.metric_citations,
                        sql_query=None,
                        answer=(
                            proposal.refusal_reason
                            or "This question cannot be answered from the available database schema."
                        ),
                        chart_spec=None,
                        sql_results=None,
                        attempts_taken=attempts,
                    )

                current_sql = proposal.sql_query
                if not current_sql:
                    error_context = "Proposal marked can_answer=True but provided no sql_query."
                    continue

                # Execute SQL via shared in-process tool
                res = tools.run_sql(current_sql)

                if res.get("status") == "success":
                    sql_results = res.get("rows", [])
                    # Synthesize final answer based on execution results
                    answer_text = self._synthesize_answer(question, sql_results, proposal)
                    return AgentResponse(
                        can_answer=True,
                        refusal_reason=None,
                        thought_process=proposal.thought_process,
                        metric_citations=proposal.metric_citations,
                        sql_query=res.get("executed_sql", current_sql),
                        answer=answer_text,
                        chart_spec=proposal.chart_spec,
                        sql_results=sql_results,
                        attempts_taken=attempts,
                    )
                else:
                    # SQL error (syntax or validation) -> trigger self-correction
                    err_msg = res.get("message", "Unknown SQL error")
                    error_context = f"SQL '{current_sql}' failed with error: {err_msg}. Please correct the query."

            except Exception as e:
                error_context = f"Proposal parsing failed: {e}. Please return valid schema."

        # If retries exhausted
        return AgentResponse(
            can_answer=True if current_sql else False,
            refusal_reason=(
                None
                if current_sql
                else (
                    proposal.refusal_reason
                    if proposal
                    else f"Failed to produce a valid SQL query after {self.max_retries} self-correction attempts."
                )
            ),
            thought_process=proposal.thought_process if proposal else "Self-correction exhausted.",
            metric_citations=proposal.metric_citations if proposal else [],
            sql_query=current_sql,
            answer="I encountered an error executing the query for this question.",
            sql_error=error_context,
            attempts_taken=attempts,
        )

    def _synthesize_answer(
        self, question: str, results: list[dict[str, Any]], proposal: AgentPlanProposal
    ) -> str:
        """Formats query results into an executive-ready text answer."""
        if not results:
            return "No matching records found for this query in the database."

        if len(results) == 1:
            row = results[0]
            # If single scalar aggregation
            if len(row) == 1:
                key, val = list(row.items())[0]
                formatted_val = f"{val:,.2f}" if isinstance(val, (int, float)) else str(val)
                return f"**{key.replace('_', ' ').title()}**: {formatted_val}"
            else:
                items = [f"**{k.replace('_', ' ').title()}**: {v}" for k, v in row.items()]
                return ", ".join(items)

        # For tabular list, summarize top entries
        top_entries = []
        for r in results[:5]:
            top_entries.append(", ".join(f"{k}: {v}" for k, v in r.items()))
        summary = f"Found {len(results)} records. Top results:\n- " + "\n- ".join(top_entries)
        return summary
