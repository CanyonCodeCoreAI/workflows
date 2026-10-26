"""CanyonOS service for the Aggressive Analyst graph node."""

from tradingagents.graph.canyonos_service import GraphNodeService


class AggressiveAnalyst:
    def __init__(self):
        self._service = GraphNodeService("Aggressive Analyst")

    def run(self, state: dict) -> dict:
        return self._service.run(state)
