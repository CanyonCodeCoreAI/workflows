"""CanyonOS service adapter for the GPT Researcher report agent.

Wraps ``run_agent`` the way ``backend.server.app.write_report`` calls it, so
every report type the server builds with ``BasicReport`` or ``DetailedReport``
runs unchanged in this container. ``multi_agents`` reports are orchestrated by
the CanyonOS workflow across the research team's own services instead.
"""

import asyncio
import time

from backend.server.server_utils import sanitize_filename
from backend.server.websocket_manager import run_agent
from gpt_researcher.utils.enum import Tone


class GPTResearcher:
    def run(
        self,
        task: str,
        report_type: str,
        report_source: str,
        tone: str,
        source_urls: list,
        document_urls: list,
        query_domains: list,
        headers: dict,
        mcp_enabled: bool,
        mcp_strategy: str,
        mcp_configs: list,
        max_search_results: int | None,
    ) -> dict:
        if report_type == "multi_agents":
            raise ValueError(
                "multi_agents reports run through the workflow's research team, "
                "not the GPTResearcher service"
            )
        research_id = sanitize_filename(f"task_{int(time.time())}_{task}")
        report, researcher = asyncio.run(
            run_agent(
                task=task,
                report_type=report_type,
                report_source=report_source,
                source_urls=source_urls,
                document_urls=document_urls,
                tone=Tone[tone],
                websocket=None,
                stream_output=None,
                headers=headers,
                query_domains=query_domains,
                config_path="",
                return_researcher=True,
                mcp_enabled=mcp_enabled,
                mcp_strategy=mcp_strategy,
                mcp_configs=mcp_configs,
                max_search_results=max_search_results,
            )
        )
        return {
            "research_id": research_id,
            "research_information": {
                "source_urls": researcher.get_source_urls(),
                "research_costs": researcher.get_costs(),
                "visited_urls": list(researcher.visited_urls),
                "research_images": researcher.get_research_images(),
            },
            "report": report,
        }
