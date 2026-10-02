"""CanyonOS service adapter for the multi-agent FactCheckerAgent."""

from multi_agents.agents import fact_checker
from multi_agents.agents.canyonos_support import run, server_wiring


class FactCheckerAgent:
    def run(self, research_state: dict, headers: dict) -> dict:
        websocket, stream = server_wiring(research_state)
        agent = fact_checker.FactCheckerAgent(websocket, stream, headers)
        return run(agent.run(research_state))
