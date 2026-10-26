"""CanyonOS service for the Market Analyst graph node."""

from tradingagents.graph.canyonos_service import GraphNodeService


class MarketAnalyst:
    def __init__(self):
        self._service = GraphNodeService("Market Analyst")

    def run(self, state: dict) -> dict:
        return self._service.run(state)
