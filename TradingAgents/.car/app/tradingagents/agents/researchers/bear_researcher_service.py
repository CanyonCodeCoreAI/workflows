"""CanyonOS service for the Bear Researcher graph node."""

from tradingagents.graph.canyonos_service import GraphNodeService


class BearResearcher:
    def __init__(self):
        self._service = GraphNodeService("Bear Researcher")

    def run(self, state: dict) -> dict:
        return self._service.run(state)
