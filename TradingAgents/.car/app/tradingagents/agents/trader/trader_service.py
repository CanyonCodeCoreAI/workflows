"""CanyonOS service for the Trader graph node."""

from tradingagents.graph.canyonos_service import GraphNodeService


class Trader:
    def __init__(self):
        self._service = GraphNodeService("Trader")

    def run(self, state: dict) -> dict:
        return self._service.run(state)
