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


def test_agent_discloses_ambiguous_order_date_when_included():
    """Verify answer discloses ambiguous order date count and inclusion when order_date is touched."""
    mock_client = MagicMock(spec=LLMClient)
    mock_proposal = AgentPlanProposal(
        can_answer=True,
        thought_process="Compute monthly revenue in 2024",
        metric_citations=["Net Revenue"],
        sql_query="SELECT strftime(order_date, '%Y-%m') AS month, ROUND(SUM(net_amount), 2) AS rev FROM orders WHERE strftime(order_date, '%Y') = '2024' GROUP BY month ORDER BY month;",
    )
    mock_client.generate_structured.return_value = LLMResponse(
        raw_text=mock_proposal.model_dump_json(),
        parsed=mock_proposal,
        model_name="mock",
        provider="mock",
        temperature=0.0,
        prompt_hash="h3",
        cached=False,
    )

    agent = AskBusinessAgent(client=mock_client)
    res = agent.answer_question("What is our monthly revenue in 2024?")

    assert res.can_answer is True
    assert "is_ambiguous_order_date" in res.answer
    assert "197" in res.answer  # 197 in 2024
    assert "included in this calculation" in res.answer


def test_agent_discloses_ambiguous_order_date_when_excluded():
    """Verify answer discloses ambiguous order date count and exclusion when filtered out."""
    mock_client = MagicMock(spec=LLMClient)
    mock_proposal = AgentPlanProposal(
        can_answer=True,
        thought_process="Compute revenue excluding ambiguous dates",
        metric_citations=["Net Revenue"],
        sql_query="SELECT ROUND(SUM(net_amount), 2) AS clean_rev FROM orders WHERE is_ambiguous_order_date = FALSE;",
    )
    mock_client.generate_structured.return_value = LLMResponse(
        raw_text=mock_proposal.model_dump_json(),
        parsed=mock_proposal,
        model_name="mock",
        provider="mock",
        temperature=0.0,
        prompt_hash="h4",
        cached=False,
    )

    agent = AskBusinessAgent(client=mock_client)
    res = agent.answer_question("What is net revenue excluding ambiguous order dates?")

    assert res.can_answer is True
    assert "is_ambiguous_order_date" in res.answer
    assert "393" in res.answer
    assert "excluded from this calculation" in res.answer


def test_agent_omits_ambiguous_order_date_when_unrelated():
    """Verify answer does not include ambiguous date notes for queries not touching order dates."""
    mock_client = MagicMock(spec=LLMClient)
    mock_proposal = AgentPlanProposal(
        can_answer=True,
        thought_process="Count SKUs per category",
        metric_citations=[],
        sql_query="SELECT category, COUNT(sku) AS cnt FROM products GROUP BY category;",
    )
    mock_client.generate_structured.return_value = LLMResponse(
        raw_text=mock_proposal.model_dump_json(),
        parsed=mock_proposal,
        model_name="mock",
        provider="mock",
        temperature=0.0,
        prompt_hash="h5",
        cached=False,
    )

    agent = AskBusinessAgent(client=mock_client)
    res = agent.answer_question("How many products are in each category?")

    assert res.can_answer is True
    assert "is_ambiguous_order_date" not in res.answer


def test_agent_queries_ambiguous_order_date_flag_directly():
    """Verify agent can execute and answer questions directly querying the ambiguous order date column."""
    mock_client = MagicMock(spec=LLMClient)
    mock_proposal = AgentPlanProposal(
        can_answer=True,
        thought_process="Count ambiguous orders using the data quality flag",
        metric_citations=["Ambiguous Order Dates Governance"],
        sql_query="SELECT COUNT(*) AS ambiguous_order_count FROM orders WHERE is_ambiguous_order_date = TRUE;",
    )
    mock_client.generate_structured.return_value = LLMResponse(
        raw_text=mock_proposal.model_dump_json(),
        parsed=mock_proposal,
        model_name="mock",
        provider="mock",
        temperature=0.0,
        prompt_hash="h6",
        cached=False,
    )

    agent = AskBusinessAgent(client=mock_client)
    res = agent.answer_question("How many total orders carry the ambiguous order date flag?")

    assert res.can_answer is True
    assert "393" in res.answer

