"""CanyonOS service for the Conservative Analyst graph node."""

from tradingagents.graph.canyonos_service import GraphNodeService


class ConservativeAnalyst:
    def __init__(self):
        self._service = GraphNodeService("Conservative Analyst")

    def run(self, state: dict) -> dict:
        return self._service.run(state)
