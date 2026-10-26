"""CanyonOS service for the Neutral Analyst graph node."""

from tradingagents.graph.canyonos_service import GraphNodeService


class NeutralAnalyst:
    def __init__(self):
        self._service = GraphNodeService("Neutral Analyst")

    def run(self, state: dict) -> dict:
        return self._service.run(state)
