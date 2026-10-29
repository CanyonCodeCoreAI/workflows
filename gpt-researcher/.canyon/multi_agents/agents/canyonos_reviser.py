"""CanyonOS service adapter for the multi-agent ReviserAgent."""

from multi_agents.agents import reviser
from multi_agents.agents.canyonos_support import run, server_wiring


class ReviserAgent:
    def run(self, draft_state: dict, headers: dict) -> dict:
        websocket, stream = server_wiring(draft_state)
        agent = reviser.ReviserAgent(websocket, stream, headers)
        return run(agent.run(draft_state))
