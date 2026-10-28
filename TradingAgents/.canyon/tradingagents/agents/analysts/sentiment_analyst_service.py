"""CanyonOS service for the Sentiment Analyst graph node."""

from tradingagents.graph.canyonos_service import GraphNodeService


class SentimentAnalyst:
    def __init__(self):
        self._service = GraphNodeService("Sentiment Analyst")

    def run(self, state: dict) -> dict:
        return self._service.run(state)
