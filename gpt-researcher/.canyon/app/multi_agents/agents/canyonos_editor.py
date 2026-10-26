"""CanyonOS service adapter for the multi-agent EditorAgent.

``run_parallel_research`` builds a researcher/reviewer/reviser graph per
section; the CanyonOS workflow now runs that graph across the three agents'
services. ``research_tasks`` is the editor's part of it: log the parallel
research and build each section's input.
"""

from multi_agents.agents import editor
from multi_agents.agents.canyonos_support import run, server_wiring, tone_from_name


class EditorAgent:
    def plan_research(self, research_state: dict, tone: str, headers: dict) -> dict:
        websocket, stream = server_wiring(research_state)
        agent = editor.EditorAgent(websocket, stream, tone_from_name(tone), headers)
        return run(agent.plan_research(research_state))

    def research_tasks(self, research_state: dict, tone: str, headers: dict) -> list:
        websocket, stream = server_wiring(research_state)
        agent = editor.EditorAgent(websocket, stream, tone_from_name(tone), headers)
        queries = research_state.get("sections")
        title = research_state.get("title")

        async def _tasks():
            agent._log_parallel_research(queries)
            return [
                agent._create_task_input(research_state, query, title, queries)
                for query in queries
            ]

        return run(_tasks())
