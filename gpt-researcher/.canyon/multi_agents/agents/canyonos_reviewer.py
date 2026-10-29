"""CanyonOS service adapter for the multi-agent ReviewerAgent."""

from multi_agents.agents import reviewer
from multi_agents.agents.canyonos_support import run, server_wiring


class ReviewerAgent:
    def run(self, draft_state: dict, headers: dict) -> dict:
        websocket, stream = server_wiring(draft_state)
        agent = reviewer.ReviewerAgent(websocket, stream, headers)
        return run(agent.run(draft_state))
