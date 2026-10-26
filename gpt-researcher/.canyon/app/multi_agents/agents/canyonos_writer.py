"""CanyonOS service adapter for the multi-agent WriterAgent."""

from multi_agents.agents import writer
from multi_agents.agents.canyonos_support import run, server_wiring


class WriterAgent:
    def run(self, research_state: dict, headers: dict) -> dict:
        websocket, stream = server_wiring(research_state)
        agent = writer.WriterAgent(websocket, stream, headers)
        return run(agent.run(research_state))
