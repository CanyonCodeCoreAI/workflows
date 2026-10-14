"""CanyonOS workflow for RCA-agent, served by the endpoint at ``POST /main``.

``query`` is either the raw instruction (run against the source's default
dataset) or a JSON object with ``instruction`` and optionally ``dataset``,
``controller_max_step`` and ``controller_max_turn``.
"""
import json

from rca.baseline.rca_agent.rca_agent_adapter import RCAAgent

# Defaults of rca.run_agent_standard's command-line arguments.
DEFAULT_DATASET = "Market/cloudbed-1"
DEFAULT_MAX_STEP = 25
DEFAULT_MAX_TURN = 5


class RCAWorkflow:
    def main(self, query: str) -> dict:
        try:
            payload = json.loads(query)
        except ValueError:
            payload = None
        if not isinstance(payload, dict):
            payload = {"instruction": query}

        result = RCAAgent().run(
            instruction=payload["instruction"],
            dataset=payload.get("dataset", DEFAULT_DATASET),
            max_step=int(payload.get("controller_max_step", DEFAULT_MAX_STEP)),
            max_turn=int(payload.get("controller_max_turn", DEFAULT_MAX_TURN)),
        )
        return json.loads(result.value())
