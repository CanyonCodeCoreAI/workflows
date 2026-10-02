"""One TradingAgents graph node served as a CanyonOS agent.

Each service builds the graph the way ``TradingAgentsGraph`` does and runs one
of its nodes, so the node keeps its own model, prompt and (for an analyst) its
tool loop. The run's state travels as JSON between the workflow and the nodes.
"""

from langchain_core.messages import convert_to_messages, messages_from_dict, messages_to_dict

from tradingagents.dataflows.config import run_config
from tradingagents.default_config import DEFAULT_CONFIG

from .trading_graph import TradingAgentsGraph


def encode_state(state: dict) -> dict:
    """A graph state or node update as JSON-ready data."""
    encoded = dict(state)
    if "messages" in encoded:
        encoded["messages"] = messages_to_dict(convert_to_messages(encoded["messages"]))
    return encoded


def decode_state(state: dict) -> dict:
    """The inverse of ``encode_state``."""
    decoded = dict(state)
    if "messages" in decoded:
        decoded["messages"] = messages_from_dict(decoded["messages"])
    return decoded


def build_graph() -> TradingAgentsGraph:
    """The graph main.py builds: DEFAULT_CONFIG with the TRADINGAGENTS_* environment."""
    return TradingAgentsGraph(config=DEFAULT_CONFIG.copy())


class GraphNodeService:
    """Runs the graph node named ``node`` on a state sent by the workflow."""

    def __init__(self, node: str):
        self._graph = build_graph()
        self._runnable = self._graph.workflow.nodes[node].runnable

    def run(self, state: dict) -> dict:
        # The node reads the run's config (vendors, language) as it does inside
        # propagate(), and an analyst's own graph gets the run's recursion limit.
        with run_config(self._graph.config):
            update = self._runnable.invoke(
                decode_state(state), self._graph.propagator.get_graph_args()["config"]
            )
        return encode_state(update)
