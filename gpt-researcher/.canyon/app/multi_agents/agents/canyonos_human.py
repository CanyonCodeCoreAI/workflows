"""CanyonOS service adapter for the multi-agent HumanAgent."""

from multi_agents.agents import human
from multi_agents.agents.canyonos_support import run, server_wiring


class HumanAgent:
    def review_plan(self, research_state: dict, headers: dict) -> dict:
        websocket, stream = server_wiring(research_state)
        agent = human.HumanAgent(websocket, stream, headers)
        return run(agent.review_plan(research_state))
