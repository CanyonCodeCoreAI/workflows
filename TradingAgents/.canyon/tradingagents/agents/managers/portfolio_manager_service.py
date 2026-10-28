"""CanyonOS service for the Portfolio Manager graph node."""

from tradingagents.graph.canyonos_service import GraphNodeService


class PortfolioManager:
    def __init__(self):
        self._service = GraphNodeService("Portfolio Manager")

    def run(self, state: dict) -> dict:
        return self._service.run(state)
