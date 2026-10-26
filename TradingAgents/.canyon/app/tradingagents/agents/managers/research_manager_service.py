"""CanyonOS service for the Research Manager graph node."""

from tradingagents.graph.canyonos_service import GraphNodeService


class ResearchManager:
    def __init__(self):
        self._service = GraphNodeService("Research Manager")

    def run(self, state: dict) -> dict:
        return self._service.run(state)
