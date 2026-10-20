"""Unit tests for AskBusinessAgent reasoning loop, self-correction, and refusal."""

from unittest.mock import MagicMock

from src.agent.agent import AgentPlanProposal, AskBusinessAgent, ChartSpec
from src.common.llm import LLMClient, LLMResponse


def test_agent_answers_valid_question():
    """Verify agent loop runs SQL and synthesizes answer when proposal is valid."""
    mock_client = MagicMock(spec=LLMClient)
    mock_proposal = AgentPlanProposal(
        can_answer=True,
        refusal_reason=None,
        thought_process="Calculate total orders",
        metric_citations=["Total Orders"],
        sql_query="SELECT COUNT(*) AS total_orders FROM orders;",
        chart_spec=ChartSpec(chart_type="none"),
    )
    mock_client.generate_structured.return_value = LLMResponse(
        raw_text=mock_proposal.model_dump_json(),
        parsed=mock_proposal,
        model_name="mock",
        provider="mock",
        temperature=0.0,
        prompt_hash="h1",
        cached=False,
    )

    agent = AskBusinessAgent(client=mock_client)
    res = agent.answer_question("How many orders were placed?")

    assert res.can_answer is True
    assert res.sql_query is not None
    assert "orders" in res.sql_query.lower()
    assert res.attempts_taken == 1


def test_agent_refuses_unanswerable_question():
    """Verify agent handles unanswerable questions gracefully with explicit refusal."""
    mock_client = MagicMock(spec=LLMClient)
    mock_proposal = AgentPlanProposal(
        can_answer=False,
        refusal_reason="Customer Acquisition Cost (CAC) is not tracked in the orders or products schema.",
        thought_process="Inspect schema for marketing ad spend -> absent -> refuse politely",
        metric_citations=[],
        sql_query=None,
        chart_spec=None,
    )
    mock_client.generate_structured.return_value = LLMResponse(
        raw_text=mock_proposal.model_dump_json(),
        parsed=mock_proposal,
        model_name="mock",
        provider="mock",
        temperature=0.0,
        prompt_hash="h2",
        cached=False,
    )

    agent = AskBusinessAgent(client=mock_client)
    res = agent.answer_question("What was our CAC on TikTok last month?")

    assert res.can_answer is False
    assert res.sql_query is None
    assert "Customer Acquisition Cost" in res.answer


def test_agent_self_correction_on_sql_error():
    """Verify agent self-corrects when initial SQL proposal fails execution."""
    mock_client = MagicMock(spec=LLMClient)

    # First call proposes a bad SQL query (non-existent column)
    bad_proposal = AgentPlanProposal(
        can_answer=True,
        thought_process="Try bad column",
        metric_citations=[],
        sql_query="SELECT nonexistent_col FROM orders;",
    )
    # Second call fixes it
    good_proposal = AgentPlanProposal(
        can_answer=True,
        thought_process="Correct to valid column",
        metric_citations=["Net Revenue"],
        sql_query="SELECT ROUND(SUM(net_amount), 2) AS net_revenue FROM orders;",
    )

    resp1 = LLMResponse("{}", bad_proposal, "mock", "mock", 0.0, "h1", False)
    resp2 = LLMResponse("{}", good_proposal, "mock", "mock", 0.0, "h2", False)

    mock_client.generate_structured.side_effect = [resp1, resp2]

    agent = AskBusinessAgent(client=mock_client)
    res = agent.answer_question("What is our net revenue?")

    assert res.can_answer is True
    assert res.attempts_taken == 2
    assert "net_amount" in res.sql_query
