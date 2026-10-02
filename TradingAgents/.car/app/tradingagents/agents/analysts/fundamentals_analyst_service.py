"""CanyonOS service for the Fundamentals Analyst graph node."""

from tradingagents.graph.canyonos_service import GraphNodeService


class FundamentalsAnalyst:
    def __init__(self):
        self._service = GraphNodeService("Fundamentals Analyst")

    def run(self, state: dict) -> dict:
        return self._service.run(state)
