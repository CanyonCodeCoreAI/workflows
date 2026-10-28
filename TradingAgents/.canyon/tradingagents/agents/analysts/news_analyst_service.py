"""CanyonOS service for the News Analyst graph node."""

from tradingagents.graph.canyonos_service import GraphNodeService


class NewsAnalyst:
    def __init__(self):
        self._service = GraphNodeService("News Analyst")

    def run(self, state: dict) -> dict:
        return self._service.run(state)
