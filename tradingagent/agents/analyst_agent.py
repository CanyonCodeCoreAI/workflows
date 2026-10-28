# SPDX-FileCopyrightText: 2026 Canyon Code, Inc.
# SPDX-License-Identifier: AGPL-3.0-only

# Analyst Agent
#
# Stage 1, and the workflow's widest fan-out. One call per lens -- technical,
# fundamental, sentiment, macro -- all four dispatched at once and all four
# reading the same market snapshot. Give it more replicas and the four land in
# parallel; give it one and they queue. That difference is the whole reason
# this pipeline is worth distributing.
#
# One agent with a `lens` argument rather than four near-identical agents: the
# job is the same, only the question changes. The lens-specific framing is in
# LENSES below; the shared instruction is the AnalystAgent.analyze prompt in
# config/prompts.yaml, which the gateway prepends to every call.
#
# Resource profile: cheap CPU, one model call, four concurrent per request.

from agents import llm

# What each analyst is asked to look at. Keeping them here, next to each other,
# is what stops the four reports collapsing into four paraphrases of one view.
LENSES = {
    "technical": (
        "You are the technical analyst. Read only the price action: trend "
        "against the moving averages, RSI, volatility and drawdown. Say what "
        "the chart alone argues for, and at what level you would be proved "
        "wrong."
    ),
    "fundamental": (
        "You are the fundamental analyst. Read only the business: valuation "
        "multiples, margins, growth and leverage. Say whether the price is "
        "justified by the figures, and which figure matters most here."
    ),
    "sentiment": (
        "You are the sentiment analyst. You have no social feed, so infer "
        "positioning from the price itself: momentum, how far it sits from "
        "its range, and what that implies about crowding. Be explicit that "
        "this is inferred, not measured."
    ),
    "macro": (
        "You are the macro analyst. Place this name in its sector and cycle. "
        "Say which macro conditions would help or hurt it, and how exposed it "
        "is compared with the broad market."
    ),
}


class AnalystAgent(object):
    def __init__(self):
        self.tools = [self.analyze]

    def analyze(self, lens: str, snapshot: dict) -> dict:
        """Report on one ticker through one analytical lens."""
        instruction = LENSES.get(lens)
        if instruction is None:
            raise ValueError(
                f"AnalystAgent: unknown lens {lens!r}; expected one of "
                f"{', '.join(sorted(LENSES))}."
            )

        report = llm.ask(
            f"{instruction}\n\n{llm.describe(snapshot)}\n\n"
            "Answer in under 120 words. End with a single line "
            "'Stance: bullish|bearish|neutral'.",
        )
        return {"lens": lens, "report": report, "stance": _stance(report)}


def _stance(report: str) -> str:
    """The stance the analyst signed off with.

    Read from the last line first, since that is where it was asked for; a
    model that buried it elsewhere still gets read, and one that gave none at
    all is recorded as neutral rather than guessed at.
    """
    for line in reversed(report.strip().splitlines()):
        lowered = line.lower()
        if "stance:" in lowered:
            for stance in ("bullish", "bearish", "neutral"):
                if stance in lowered:
                    return stance
    return "neutral"


if __name__ == "__main__":
    from agents.market_data_agent import MarketDataAgent

    snapshot = MarketDataAgent().snapshot("NVDA", 180)
    print(AnalystAgent().analyze("technical", snapshot)["report"])
