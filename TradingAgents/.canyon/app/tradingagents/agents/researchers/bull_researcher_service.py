"""CanyonOS service for the Bull Researcher graph node."""

from tradingagents.graph.canyonos_service import GraphNodeService


class BullResearcher:
    def __init__(self):
        self._service = GraphNodeService("Bull Researcher")

    def run(self, state: dict) -> dict:
        return self._service.run(state)
