"""CanyonOS workflow: TradingAgentsGraph.propagate() with each graph node as a service.

The endpoint serves ``Workflow.main`` at ``POST /main``.

The edges are the ones GraphSetup.setup_graph() wires: the selected analysts at
once, the bull/bear debate until ConditionalLogic ends it, the Research Manager,
the Trader, the risk debate, then the Portfolio Manager. The run's setup and
bookkeeping (memory log, settlement, state log) stay here, as in propagate().

The query is ``TICKER YYYY-MM-DD [asset_type]`` or a JSON object with
``ticker``, ``trade_date`` and optional ``asset_type`` and ``analysts``.
"""

import json
import logging

from langgraph.errors import GraphRecursionError
from langgraph.graph.message import add_messages

from tradingagents.agents.analysts.fundamentals_analyst_service import FundamentalsAnalyst
from tradingagents.agents.analysts.market_analyst_service import MarketAnalyst
from tradingagents.agents.analysts.news_analyst_service import NewsAnalyst
from tradingagents.agents.analysts.sentiment_analyst_service import SentimentAnalyst
from tradingagents.agents.managers.portfolio_manager_service import PortfolioManager
from tradingagents.agents.managers.research_manager_service import ResearchManager
from tradingagents.agents.rating import run_rating
from tradingagents.agents.researchers.bear_researcher_service import BearResearcher
from tradingagents.agents.researchers.bull_researcher_service import BullResearcher
from tradingagents.agents.risk_mgmt.aggressive_debator_service import AggressiveAnalyst
from tradingagents.agents.risk_mgmt.conservative_debator_service import ConservativeAnalyst
from tradingagents.agents.risk_mgmt.neutral_debator_service import NeutralAnalyst
from tradingagents.agents.trader.trader_service import Trader
from tradingagents.dataflows.config import run_config
from tradingagents.graph.analyst_execution import build_analyst_execution_plan
from tradingagents.graph.canyonos_service import build_graph, decode_state, encode_state
from tradingagents.graph.trading_graph import _validate_trade_date

logger = logging.getLogger(__name__)

DEFAULT_ANALYSTS = ("market", "social", "news", "fundamentals")

graph = build_graph()
if graph.config.get("checkpoint_enabled"):
    logger.warning("checkpoint_enabled is not supported across services; runs start fresh")

NODES = {
    "Market Analyst": MarketAnalyst(),
    "Sentiment Analyst": SentimentAnalyst(),
    "News Analyst": NewsAnalyst(),
    "Fundamentals Analyst": FundamentalsAnalyst(),
    "Bull Researcher": BullResearcher(),
    "Bear Researcher": BearResearcher(),
    "Research Manager": ResearchManager(),
    "Trader": Trader(),
    "Aggressive Analyst": AggressiveAnalyst(),
    "Conservative Analyst": ConservativeAnalyst(),
    "Neutral Analyst": NeutralAnalyst(),
    "Portfolio Manager": PortfolioManager(),
}


def _parse(query: str) -> dict:
    try:
        request = json.loads(query)
    except json.JSONDecodeError:
        request = None
    if not isinstance(request, dict):
        parts = query.split()
        if len(parts) < 2:
            raise ValueError("query must be 'TICKER YYYY-MM-DD [asset_type]' or a JSON object")
        request = {"ticker": parts[0], "trade_date": parts[1]}
        if len(parts) > 2:
            request["asset_type"] = parts[2]
    return {
        "ticker": request["ticker"],
        "trade_date": request["trade_date"],
        "asset_type": request.get("asset_type", "stock"),
        "analysts": tuple(request.get("analysts") or DEFAULT_ANALYSTS),
    }


class _Run:
    """The run's state, advanced one graph step (superstep) at a time."""

    def __init__(self, state: dict):
        self.state = state
        self.steps = 0
        self.limit = graph.propagator.max_recur_limit

    def step(self, *nodes: str) -> None:
        self.steps += 1
        if self.steps > self.limit:
            raise GraphRecursionError(f"Recursion limit of {self.limit} reached")
        # Dispatch every node of the step before reading any result.
        sent = encode_state(self.state)
        futures = [NODES[node].run(state=sent) for node in nodes]
        for future in futures:
            for key, value in decode_state(json.loads(future.value())).items():
                if key == "messages":
                    value = add_messages(self.state.get("messages", []), value)
                self.state[key] = value


def _run_graph(ticker: str, trade_date: str, asset_type: str, analysts: tuple) -> dict:
    plan = build_analyst_execution_plan(analysts)
    logic = graph.conditional_logic
    run = _Run(graph.create_run_state(ticker, trade_date, asset_type))

    run.step(*(spec.agent_node for spec in plan.specs))

    node = "Bull Researcher"
    while node != "Research Manager":
        run.step(node)
        node = logic.should_continue_debate(run.state)
    run.step("Research Manager")
    run.step("Trader")

    node = "Aggressive Analyst"
    while node != "Portfolio Manager":
        run.step(node)
        node = logic.should_continue_risk_analysis(run.state)
    run.step("Portfolio Manager")

    graph.record_decision(ticker, trade_date, run.state)
    return run.state


class Workflow:
    def main(self, query: str) -> dict:
        request = _parse(query)
        trade_date = _validate_trade_date(request["trade_date"])
        with run_config(graph.config):
            final_state = _run_graph(
                request["ticker"], trade_date, request["asset_type"], request["analysts"]
            )
        result = {key: value for key, value in final_state.items() if key != "messages"}
        result["signal"] = run_rating(final_state)
        return result
