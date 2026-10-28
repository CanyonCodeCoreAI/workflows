# SPDX-FileCopyrightText: 2026 Canyon Code, Inc.
# SPDX-License-Identifier: AGPL-3.0-only

# Research Manager Agent
#
# Stage 3, between the debate and the trader. Judges the bull/bear argument
# and turns it into a rating the trader can act on, on the five-point scale
# upstream uses: Buy / Overweight / Hold / Underweight / Sell.
#
# Its standing instruction, in config/prompts.yaml, is the one that matters
# most here: a debate always contains conflicting arguments, so conflict alone
# is not a reason to sit on the fence. Hold is for evidence that is genuinely
# balanced or genuinely thin -- not for avoiding a call.
#
# Resource profile: cheap CPU, one model call, a barrier between the debate
# and everything downstream.

from agents import llm

# Ordered from most bullish to most bearish; the position each implies is
# read off this order rather than hard-coded per rating.
RATINGS = ("buy", "overweight", "hold", "underweight", "sell")


class ResearchManagerAgent(object):
    def __init__(self):
        self.tools = [self.judge]

    def judge(self, ticker: str, reports: list, debate: list) -> dict:
        """Weigh the debate and commit to a rating for the trader."""
        verdict = llm.ask(
            f"You are the research manager, judging the desk's debate on {ticker}.\n\n"
            "The analysts reported:\n\n"
            + "\n\n".join(f"[{r['lens']}] {r['report']}" for r in reports)
            + "\n\nThe debate ran as follows:\n\n"
            + "\n\n".join(f"[{t['stance']}] {t['argument']}" for t in debate)
            + "\n\nWrite exactly these sections, in this order:\n"
            "Recommendation: one of Buy / Overweight / Hold / Underweight / Sell\n"
            "Rationale: which arguments decided it, in two sentences\n"
            "Strategic Actions: what the trader should do, in two sentences",
        )
        return {"rating": _rating(verdict), "plan": verdict}


def _rating(verdict: str) -> str:
    """The rating the manager committed to.

    Read from the Recommendation line where it was asked for, and matched
    longest-first so "underweight" is never read as the "weight" inside
    "overweight". A verdict with no readable rating becomes a hold, which is
    the reading that proposes no position.
    """
    for line in verdict.splitlines():
        if "recommendation" not in line.lower():
            continue
        lowered = line.lower()
        for rating in sorted(RATINGS, key=len, reverse=True):
            if rating in lowered:
                return rating
    return "hold"


def implied_direction(rating: str) -> str:
    """The side a rating argues for, as the trader reads it."""
    if rating in ("buy", "overweight"):
        return "buy"
    if rating in ("sell", "underweight"):
        return "sell"
    return "hold"


if __name__ == "__main__":
    print(_rating("Recommendation: Underweight\nRationale: ..."))
    print(implied_direction("overweight"))
