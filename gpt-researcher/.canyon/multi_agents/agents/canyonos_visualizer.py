"""CanyonOS service adapter for the multi-agent VisualizerAgent."""

from multi_agents.agents import visualizer
from multi_agents.agents.canyonos_support import run, server_wiring


class VisualizerAgent:
    def run(self, research_state: dict, headers: dict) -> dict:
        websocket, stream = server_wiring(research_state)
        agent = visualizer.VisualizerAgent(websocket, stream, headers)
        return run(agent.run(research_state))
