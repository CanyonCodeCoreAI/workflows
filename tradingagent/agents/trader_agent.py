# SPDX-FileCopyrightText: 2026 Canyon Code, Inc.
# SPDX-License-Identifier: AGPL-3.0-only

# Trader Agent
#
# Stage 3. Reads the analyst reports and the whole bull/bear debate and turns
# them into one concrete proposal: a side, a size and a reason. This is the
# first point in the workflow where something has to be decided rather than
# discussed.
#
# It proposes; it does not approve. The risk desk and the portfolio manager
# still have to agree, which is why the output is a plan rather than an order.
#
# The instruction is the TraderAgent.propose prompt in config/prompts.yaml.
#
# Resource profile: cheap CPU, one model call, on the critical path between
# the two fan-outs.

import json
import re

from agents import llm

VALID_ACTIONS = ("buy", "sell", "hold")


class TraderAgent(object):
    def __init__(self):
        self.tools = [self.propose]

    def propose(self, ticker: str, reports: list, debate: list, research: dict) -> dict:
        """Turn the research manager's rating into one proposed position."""
        answer = llm.ask(
            f"You are the trader. The desk has researched {ticker}.\n\n"
            "Analyst reports:\n\n"
            + "\n\n".join(f"[{r['lens']}] {r['report']}" for r in reports)
            + "\n\nThe bull/bear debate:\n\n"
            + "\n\n".join(f"[{t['stance']}] {t['argument']}" for t in debate)
            + f"\n\nThe research manager rated it {research['rating'].upper()} "
            "and wrote:\n\n"
            + research["plan"]
            + "\n\nThat rating is the desk's view; size to it rather than "
            "re-arguing it. Return ONLY a JSON object with exactly these keys:\n"
            '  "action": "buy" | "sell" | "hold"\n'
            '  "size_pct": a number from 0 to 10, the share of the book to put at risk\n'
            '  "rationale": one sentence, naming the figure that decided it\n'
            '  "invalidated_by": one sentence, what would prove this wrong',
        )
        return _plan(answer)


def _plan(answer: str) -> dict:
    """The model's answer as a plan, with every field checked.

    A malformed answer becomes a hold with the reason recorded, rather than an
    exception: by this point the request has already paid for the analysts and
    the debate, and losing all of it to a stray code fence would be a poor
    trade. A hold is also the safe reading of "we could not tell".
    """
    match = re.search(r"\{.*\}", answer, re.DOTALL)
    if not match:
        return _hold("the trader's answer contained no JSON object")

    try:
        parsed = json.loads(match.group(0))
    except ValueError:
        return _hold("the trader's answer was not valid JSON")

    action = str(parsed.get("action", "")).strip().lower()
    if action not in VALID_ACTIONS:
        return _hold(f"the trader proposed an unknown action {action!r}")

    return {
        "action": action,
        "size_pct": _size(parsed.get("size_pct"), action),
        "rationale": str(parsed.get("rationale") or "").strip(),
        "invalidated_by": str(parsed.get("invalidated_by") or "").strip(),
    }


def _size(raw, action: str) -> float:
    """A size between 0 and 10, and always 0 for a hold.

    A hold that carries a size is a contradiction the risk desk would have to
    resolve by guessing, so it is resolved here instead.
    """
    if action == "hold":
        return 0.0
    try:
        return round(max(0.0, min(10.0, float(raw))), 2)
    except (TypeError, ValueError):
        return 0.0


def _hold(reason: str) -> dict:
    return {
        "action": "hold",
        "size_pct": 0.0,
        "rationale": f"Defaulted to hold: {reason}.",
        "invalidated_by": "A readable proposal from the trader.",
    }


if __name__ == "__main__":
    print(_hold("a worked example"))
