"""CanyonOS service adapter for the multi-agent ResearchAgent."""

from multi_agents.agents import researcher
from multi_agents.agents.canyonos_support import run, server_wiring, tone_from_name


class ResearchAgent:
    def run_initial_research(self, research_state: dict, tone: str, headers: dict) -> dict:
        websocket, stream = server_wiring(research_state)
        agent = researcher.ResearchAgent(websocket, stream, tone_from_name(tone), headers)
        return run(agent.run_initial_research(research_state))

    def run_depth_research(self, draft_state: dict, tone: str, headers: dict) -> dict:
        websocket, stream = server_wiring(draft_state)
        agent = researcher.ResearchAgent(websocket, stream, tone_from_name(tone), headers)
        return run(agent.run_depth_research(draft_state))
