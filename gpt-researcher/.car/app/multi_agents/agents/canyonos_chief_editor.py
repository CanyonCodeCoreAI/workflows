"""CanyonOS service adapter for the multi-agent ChiefEditorAgent.

The chief editor's graph now runs in the CanyonOS workflow. This service keeps
what the chief editor does before the graph starts: load the task from
``task.json``, create the run's output directory and log the start.
"""

import asyncio

from multi_agents.agents.canyonos_support import server_wiring, tone_from_name
from multi_agents.agents.orchestrator import ChiefEditorAgent as _ChiefEditorAgent
from multi_agents.main import open_task


class ChiefEditorAgent:
    def prepare(self, query: str, tone: str, headers: dict) -> dict:
        task = open_task()
        task["query"] = query
        websocket, stream = server_wiring({"task": task})
        chief_editor = _ChiefEditorAgent(
            task, websocket, stream, tone_from_name(tone), headers
        )
        asyncio.run(chief_editor._log_research_start())
        return {"task": chief_editor.task, "output_dir": chief_editor.output_dir}
