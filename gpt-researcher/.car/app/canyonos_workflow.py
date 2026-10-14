"""CanyonOS workflow for GPT Researcher, served by the endpoint at ``POST /main``.

Serves the report generation behind the backend server's ``/report/`` and
``/ws`` endpoints. ``query`` is either the research task as plain text or a
JSON object with the fields the server's ``start`` command carries (``task``,
``report_type``, ``report_source``, ``tone``, ``source_urls``, ...).

Every report type except ``multi_agents`` runs in the GPTResearcher service,
as ``run_agent`` runs it. ``multi_agents`` runs the chief editor's research
team with each agent in its own service: the LangGraph graphs built by
``ChiefEditorAgent`` and ``EditorAgent.run_parallel_research`` are walked
here, edge for edge, with their own routing functions.
"""

import importlib.util
import json
import os

from canyonos_gpt_researcher import GPTResearcher
from canyonos_chief_editor import ChiefEditorAgent
from canyonos_researcher import ResearchAgent
from canyonos_editor import EditorAgent
from canyonos_human import HumanAgent
from canyonos_writer import WriterAgent
from canyonos_fact_checker import FactCheckerAgent
from canyonos_visualizer import VisualizerAgent
from canyonos_publisher import PublisherAgent
from canyonos_reviewer import ReviewerAgent
from canyonos_reviser import ReviserAgent


def _load(*path):
    """Load a dependency-free source module by path.

    Importing it as ``multi_agents.agents.<name>`` would first run the
    package ``__init__``, which imports the whole team and its dependencies.
    """
    name = "canyonos_source_" + os.path.splitext(path[-1])[0]
    spec = importlib.util.spec_from_file_location(name, os.path.join(*path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plan_review = _load("multi_agents", "agents", "plan_review.py")
fact_review = _load("multi_agents", "agents", "fact_review.py")
draft_review = _load("multi_agents", "agents", "draft_review.py")
# LangGraph keeps only the keys a graph's state schema declares.
RESEARCH_STATE_KEYS = set(_load("multi_agents", "memory", "research.py").ResearchState.__annotations__)
DRAFT_STATE_KEYS = set(_load("multi_agents", "memory", "draft.py").DraftState.__annotations__)

gpt_researcher = GPTResearcher()
chief_editor = ChiefEditorAgent()
research = ResearchAgent()
editor = EditorAgent()
human = HumanAgent()
writer = WriterAgent()
fact_checker = FactCheckerAgent()
visualizer = VisualizerAgent()
publisher = PublisherAgent()
reviewer = ReviewerAgent()
reviser = ReviserAgent()


def _parse_request(query):
    try:
        request = json.loads(query)
    except ValueError:
        request = None
    if not isinstance(request, dict):
        request = {"task": query}
    # Defaults of WebSocketManager.start_streaming and run_agent.
    return {
        "task": request["task"],
        "report_type": request.get("report_type", "research_report"),
        "report_source": request.get("report_source", "web"),
        "tone": request.get("tone", "Objective"),
        "source_urls": request.get("source_urls", []),
        "document_urls": request.get("document_urls", []),
        "query_domains": request.get("query_domains", []),
        "headers": request.get("headers") or {},
        "mcp_enabled": request.get("mcp_enabled", False),
        "mcp_strategy": request.get("mcp_strategy", "fast"),
        "mcp_configs": request.get("mcp_configs", []),
        "max_search_results": request.get("max_search_results"),
    }


def _merge(state, future, keys):
    update = json.loads(future.value())
    state.update({key: value for key, value in update.items() if key in keys})


def _route(route, ceiling_error, state, limit):
    """Graph edge: the source's router, force-accepting past the ceiling."""
    try:
        return route(state, limit)
    except ceiling_error:
        return "accept"


def _parallel_research(state, tone, headers):
    """EditorAgent.run_parallel_research: one draft graph per section.

    The per-section graphs run side by side, advanced one node at a time:
    researcher -> reviewer -> (revise: reviser -> reviewer) -> END.
    """
    inputs = json.loads(editor.research_tasks(research_state=state, tone=tone, headers=headers).value())
    drafts = [{key: value for key, value in item.items() if key in DRAFT_STATE_KEYS} for item in inputs]

    futures = [research.run_depth_research(draft_state=draft, tone=tone, headers=headers) for draft in drafts]
    for draft, future in zip(drafts, futures):
        _merge(draft, future, DRAFT_STATE_KEYS)

    active = drafts
    while active:
        futures = [reviewer.run(draft_state=draft, headers=headers) for draft in active]
        for draft, future in zip(active, futures):
            _merge(draft, future, DRAFT_STATE_KEYS)
        active = [
            draft for draft in active
            if _route(
                draft_review.route_draft_review,
                draft_review.MaxDraftRevisionsExceededError,
                draft,
                (draft.get("task") or {}).get("max_draft_revisions", draft_review.DEFAULT_MAX_DRAFT_REVISIONS),
            ) == "revise"
        ]
        futures = [reviser.run(draft_state=draft, headers=headers) for draft in active]
        for draft, future in zip(active, futures):
            _merge(draft, future, DRAFT_STATE_KEYS)

    return [draft.get("draft") for draft in drafts]


def _multi_agents(request):
    """ChiefEditorAgent.run_research_task, as run_multi_agent_task calls it."""
    tone, headers = request["tone"], request["headers"]
    prepared = json.loads(chief_editor.prepare(query=request["task"], tone=tone, headers=headers).value())
    task, output_dir = prepared["task"], prepared["output_dir"]
    state = {"task": task}

    _merge(state, research.run_initial_research(research_state=state, tone=tone, headers=headers), RESEARCH_STATE_KEYS)
    while True:
        _merge(state, editor.plan_research(research_state=state, tone=tone, headers=headers), RESEARCH_STATE_KEYS)
        _merge(state, human.review_plan(research_state=state, headers=headers), RESEARCH_STATE_KEYS)
        limit = task.get("max_plan_revisions", plan_review.DEFAULT_MAX_PLAN_REVISIONS)
        if _route(plan_review.route_human_feedback, plan_review.MaxPlanRevisionsExceededError, state, limit) == "accept":
            break

    state["research_data"] = _parallel_research(state, tone, headers)

    while True:
        _merge(state, writer.run(research_state=state, headers=headers), RESEARCH_STATE_KEYS)
        _merge(state, fact_checker.run(research_state=state, headers=headers), RESEARCH_STATE_KEYS)
        limit = task.get("max_fact_check_revisions", fact_review.DEFAULT_MAX_FACT_CHECK_REVISIONS)
        if _route(fact_review.route_fact_check, fact_review.MaxFactCheckRevisionsExceededError, state, limit) == "accept":
            break

    _merge(state, visualizer.run(research_state=state, headers=headers), RESEARCH_STATE_KEYS)
    _merge(state, publisher.run(research_state=state, output_dir=output_dir, headers=headers), RESEARCH_STATE_KEYS)
    return {"report": state.get("report", "")}


class Workflow:
    def main(self, query: str) -> dict:
        request = _parse_request(query)
        if request["report_type"] == "multi_agents":
            return _multi_agents(request)
        return json.loads(gpt_researcher.run(**request).value())
