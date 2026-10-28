# SPDX-FileCopyrightText: 2026 Canyon Code, Inc.
# SPDX-License-Identifier: AGPL-3.0-only

# Risk Agent
#
# Stage 4: the second fan-out. Three risk officers review the trader's plan at
# once -- one pushing for more, one for less, one for neither -- and each
# returns a verdict and a size they would accept.
#
# Three stances rather than three agents, for the same reason the analysts and
# researchers are one agent each: identical job, different seat.
#
# The instruction is the RiskAgent.review prompt in config/prompts.yaml.
#
# Resource profile: cheap CPU, three concurrent calls per request.

import json
import re

from agents import llm

SEATS = {
    "aggressive": (
        "You hold the aggressive seat. Your concern is opportunity missed. "
        "Argue for taking the position, or for taking more of it, where the "
        "evidence supports it."
    ),
    "conservative": (
        "You hold the conservative seat. Your concern is capital lost. Argue "
        "for taking less, or none, wherever the evidence is thin."
    ),
    "neutral": (
        "You hold the neutral seat. You are neither drawn to the upside nor "
        "frightened of the downside. Weigh both and say which the figures "
        "actually support."
    ),
}

VALID_VERDICTS = ("approve", "reduce", "reject")


class RiskAgent(object):
    def __init__(self):
        self.tools = [self.review]

    def review(self, stance: str, plan: dict, snapshot: dict) -> dict:
        """Review the trader's plan from one risk seat."""
        seat = SEATS.get(stance)
        if seat is None:
            raise ValueError(
                f"RiskAgent: unknown stance {stance!r}; expected one of "
                f"{', '.join(sorted(SEATS))}."
            )

        answer = llm.ask(
            f"{seat}\n\nThe trader proposes:\n"
            f"  action: {plan['action']}\n"
            f"  size: {plan['size_pct']}% of the book\n"
            f"  rationale: {plan['rationale']}\n"
            f"  invalidated by: {plan['invalidated_by']}\n\n"
            f"{llm.describe(snapshot)}\n\n"
            "Return ONLY a JSON object with exactly these keys:\n"
            '  "verdict": "approve" | "reduce" | "reject"\n'
            '  "max_size_pct": the largest size you would accept, 0 to 10\n'
            '  "reason": one sentence',
        )
        return _verdict(stance, answer, plan)


def _verdict(stance: str, answer: str, plan: dict) -> dict:
    """One seat's answer, with every field checked.

    An unreadable answer becomes a reject rather than an exception. Two seats
    have already been paid for by the time one of them garbles its JSON, and a
    risk officer whose opinion could not be read is not an approval.
    """
    match = re.search(r"\{.*\}", answer, re.DOTALL)
    parsed = {}
    if match:
        try:
            parsed = json.loads(match.group(0))
        except ValueError:
            parsed = {}

    verdict = str(parsed.get("verdict", "")).strip().lower()
    if verdict not in VALID_VERDICTS:
        return {
            "stance": stance,
            "verdict": "reject",
            "max_size_pct": 0.0,
            "reason": "This seat's answer could not be read, so it does not approve.",
        }

    return {
        "stance": stance,
        "verdict": verdict,
        "max_size_pct": _cap(parsed.get("max_size_pct"), verdict, plan),
        "reason": str(parsed.get("reason") or "").strip(),
    }


def _cap(raw, verdict: str, plan: dict) -> float:
    """The size this seat would accept, clamped to 0-10.

    A reject is always 0 whatever the model wrote, and an approve that names
    no size is read as accepting the size it was shown -- which is what
    approving a specific plan means.
    """
    if verdict == "reject":
        return 0.0
    try:
        return round(max(0.0, min(10.0, float(raw))), 2)
    except (TypeError, ValueError):
        return float(plan["size_pct"]) if verdict == "approve" else 0.0


if __name__ == "__main__":
    plan = {
        "action": "buy",
        "size_pct": 4.0,
        "rationale": "worked example",
        "invalidated_by": "n/a",
    }
    print(_verdict("conservative", "not json", plan))
