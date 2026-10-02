"""CanyonOS service adapter for the multi-agent PublisherAgent.

The chief editor creates the run's output directory in its own container, so
this service creates the same directory before publishing into it.
"""

import os

from multi_agents.agents import publisher
from multi_agents.agents.canyonos_support import run, server_wiring


class PublisherAgent:
    def run(self, research_state: dict, output_dir: str, headers: dict) -> dict:
        os.makedirs(output_dir, exist_ok=True)
        websocket, stream = server_wiring(research_state)
        agent = publisher.PublisherAgent(output_dir, websocket, stream, headers)
        return run(agent.run(research_state))
