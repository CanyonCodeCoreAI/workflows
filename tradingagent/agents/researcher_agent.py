# SPDX-FileCopyrightText: 2026 Canyon Code, Inc.
# SPDX-License-Identifier: AGPL-3.0-only

# Researcher Agent
#
# Stage 2: the debate. A bull and a bear argue over the four analyst reports,
# for a capped number of rounds. Each round both sides are dispatched at once
# and both see every argument made so far, so round two is a reply rather than
# a restatement.
#
# The round cap lives in the manifest as MAX_DEBATE_ROUNDS, because an
# uncapped debate is an uncapped bill -- two model calls per round, every
# round, and nothing in the argument itself to make it stop.
#
# One agent with a `stance` argument rather than a BullAgent and a BearAgent:
# the job is identical, and only the side differs.
#
# Resource profile: cheap CPU, two concurrent calls per round.

from agents import llm

SIDES = {
    "bull": "You argue the case for buying. ",
    "bear": "You argue the case against buying, including for selling. ",
}


class ResearcherAgent(object):
    def __init__(self):
        self.tools = [self.argue]

    def argue(self, stance: str, reports: list, history: list) -> dict:
        """Make one side's case, answering whatever has been argued so far."""
        side = SIDES.get(stance)
        if side is None:
            raise ValueError(
                f"ResearcherAgent: unknown stance {stance!r}; expected bull or bear."
            )

        argument = llm.ask(
            side
            + "You are reading four analyst reports on the same stock.\n\n"
            + _reports(reports)
            + _history(history)
            + "\nMake your strongest case in under 120 words. Argue from the "
            "figures, not from conviction. Where the other side has a point, "
            "concede it and say why it does not change your conclusion.",
        )
        return {"stance": stance, "argument": argument}


def _reports(reports: list) -> str:
    return "\n\n".join(f"[{r['lens']}] {r['report']}" for r in reports)


def _history(history: list) -> str:
    """Every argument so far, so each round answers the last one.

    The whole debate is replayed rather than summarised: it is short by
    construction, and summarising it would quietly drop the specific numbers
    the two sides are disagreeing about.
    """
    if not history:
        return "\n\nThis is the opening argument; nothing has been said yet."
    turns = "\n\n".join(f"[{turn['stance']}] {turn['argument']}" for turn in history)
    return f"\n\nThe debate so far:\n\n{turns}"


if __name__ == "__main__":
    reports = [{"lens": "technical", "report": "Trading above both averages."}]
    print(ResearcherAgent().argue("bear", reports, [])["argument"])
