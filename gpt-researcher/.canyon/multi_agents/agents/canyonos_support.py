"""Shared wiring for the CanyonOS adapters of the multi-agent research team.

The server runs the team through ``run_multi_agent_task`` with a
``CustomLogsHandler`` as the websocket and ``stream_output`` as the streamer;
each adapter builds the same pair so the agents log and behave as they do
there. Adapters construct their agent per call because ``tone`` and
``headers`` arrive with each request.
"""

import asyncio

from backend.server.server_utils import CustomLogsHandler
from gpt_researcher.actions import stream_output
from gpt_researcher.utils.enum import Tone


def server_wiring(state: dict):
    return CustomLogsHandler(None, state["task"]["query"]), stream_output


def tone_from_name(name: str):
    return Tone[name]


def run(coroutine):
    """Run an agent coroutine, letting log tasks it spawned finish first."""

    async def _run():
        result = await coroutine
        pending = asyncio.all_tasks() - {asyncio.current_task()}
        if pending:
            await asyncio.gather(*pending)
        return result

    return asyncio.run(_run())
