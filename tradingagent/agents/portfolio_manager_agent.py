# SPDX-FileCopyrightText: 2026 Canyon Code, Inc.
# SPDX-License-Identifier: AGPL-3.0-only

# Portfolio Manager Agent
#
# Stage 5, and the last word. Reads the trader's plan and all three risk
# verdicts and issues the decision the workflow returns.
#
# The final size is arithmetic, not opinion: no seat is overruled, so the
# position can never exceed what the most cautious of them would accept. The
# model writes the reasoning; it does not get to pick the number. That split
# matters -- it is the difference between a committee and a model that has
# been told a committee met.
#
# The instruction is the PortfolioManagerAgent.decide prompt in
# config/prompts.yaml.
#
# Resource profile: cheap CPU, one model call, the final barrier.

from agents import llm


class PortfolioManagerAgent(object):
    def __init__(self):
        self.tools = [self.decide]

    def decide(self, ticker: str, plan: dict, verdicts: list) -> dict:
        """Issue the final decision, bounded by the risk desk."""
        rejected = [v for v in verdicts if v["verdict"] == "reject"]
        # The binding constraint, and the only thing that sets the size: the
        # lowest ceiling any seat was willing to live with.
        approved_size = min([v["max_size_pct"] for v in verdicts] + [plan["size_pct"]])

        if rejected or approved_size <= 0:
            action, size = "hold", 0.0
        else:
            action, size = plan["action"], round(approved_size, 2)

        reasoning = llm.ask(
            f"You are the portfolio manager, deciding on {ticker}.\n\n"
            f"The trader proposed: {plan['action']} at {plan['size_pct']}% "
            f"-- {plan['rationale']}\n\n"
            "The risk desk said:\n"
            + "\n".join(
                f"  [{v['stance']}] {v['verdict']} up to {v['max_size_pct']}% "
                f"-- {v['reason']}"
                for v in verdicts
            )
            + f"\n\nThe decision is: {action} at {size}% of the book.\n\n"
            "In under 100 words, explain that decision to the desk. Name which "
            "seat set the size and why. Do not change the decision.",
        )

        # Key order here is not preserved -- the endpoint's jsonify sorts
        # alphabetically -- which happens to put "action" first anyway.
        return {
            "action": action,
            "size_pct": size,
            "ticker": ticker,
            "reasoning": reasoning,
            "bound_by": _bound_by(verdicts, size, rejected),
            "proposed_size_pct": plan["size_pct"],
            "invalidated_by": plan["invalidated_by"],
        }


def _bound_by(verdicts: list, size: float, rejected: list) -> str:
    """Which seat decided the outcome, so the number is traceable to a reason."""
    if rejected:
        return ", ".join(sorted(v["stance"] for v in rejected)) + " rejected"
    binding = [v["stance"] for v in verdicts if v["max_size_pct"] == size]
    return ", ".join(sorted(binding)) if binding else "the trader's own size"


if __name__ == "__main__":
    verdicts = [
        {
            "stance": "aggressive",
            "verdict": "approve",
            "max_size_pct": 8.0,
            "reason": "",
        },
        {
            "stance": "conservative",
            "verdict": "reduce",
            "max_size_pct": 2.0,
            "reason": "",
        },
        {"stance": "neutral", "verdict": "approve", "max_size_pct": 5.0, "reason": ""},
    ]
    print(_bound_by(verdicts, 2.0, []))
