# SPDX-FileCopyrightText: 2026 Canyon Code, Inc.
# SPDX-License-Identifier: AGPL-3.0-only

# Trading desk workflow: the agent the endpoint serves at POST /main.
#
# A question about one stock goes through the desk the way it would through a
# real one -- four analysts, a bull/bear debate, a trader, a risk committee,
# and a portfolio manager with the last word:
#
#   0. MarketDataAgent  one snapshot: prices, indicators, fundamentals
#   1. AnalystAgent     FAN-OUT x4 -- technical, fundamental, sentiment, macro
#      ------------------------------------------------ barrier
#   2. ResearcherAgent  bull vs bear, both at once, for MAX_DEBATE_ROUNDS rounds
#   3. ResearchManagerAgent  judges the debate: Buy/Overweight/Hold/Underweight/Sell
#   4. TraderAgent      one proposal: action, size, rationale
#   5. RiskAgent        FAN-OUT x3 -- aggressive, conservative, neutral
#      ------------------------------------------------ barrier
#   6. PortfolioManagerAgent  the decision, bounded by the most cautious seat
#
# The input is a ticker and an optional trade date, the two arguments upstream
# takes as `propagate("NVDA", "2026-09-01")`. They arrive in one `query`
# string -- "NVDA 2026-09-01" -- because `canyonos test` sends the same text
# for every argument an endpoint declares, so a two-argument endpoint would
# receive the whole sentence twice.
#
# Every agent call returns a Future immediately. Dispatching all four analysts
# before calling .value() on any of them is what makes them run at once; call
# .value() inside the loop instead and the same code runs them one after
# another. The two fan-outs and the two barriers are the shape worth copying.
#
# A Future's .value() always returns the raw string CanyonOS stored in Redis,
# so anything that is not a str has to be parsed back out -- see json.loads
# below, same as the portfolio example.
#
# After `canyonos deploy`:
#   curl -X POST http://localhost:8085/main \
#        -H 'Content-Type: application/json' \
#        -d '{"query": "Should I buy NVDA right now?"}'
#   curl http://localhost:8085/status/<request_id>

import json
import os
import re

from agents.analyst_agent import AnalystAgent
from agents.market_data_agent import MarketDataAgent
from agents.portfolio_manager_agent import PortfolioManagerAgent
from agents.research_manager_agent import ResearchManagerAgent
from agents.researcher_agent import ResearcherAgent
from agents.risk_agent import RiskAgent
from agents.trader_agent import TraderAgent

LENSES = ("technical", "fundamental", "sentiment", "macro")
SEATS = ("aggressive", "conservative", "neutral")

# Capped in the manifest, not here: two model calls per round, and nothing in
# the argument itself makes it stop. One round is a case each; two is a reply.
DEFAULT_DEBATE_ROUNDS = 2
LOOKBACK_DAYS = 180


class Workflow(object):
    def main(self, query: str = "NVDA 2026-09-01"):
        ticker = _ticker(query)
        as_of = _trade_date(query)
        rounds = _rounds()

        market_data = MarketDataAgent()
        analyst = AnalystAgent()
        researcher = ResearcherAgent()
        research_manager = ResearchManagerAgent()
        trader = TraderAgent()
        risk = RiskAgent()
        manager = PortfolioManagerAgent()

        # Stage 0. Everything downstream argues over this one snapshot, so it
        # is fetched once rather than four times with four different answers.
        snapshot = json.loads(
            market_data.snapshot(
                ticker=ticker, lookback_days=LOOKBACK_DAYS, as_of=as_of
            ).value()
        )

        # Stage 1: fan out. All four dispatched before any is awaited -- this
        # loop is the difference between four seconds and sixteen.
        pending = [analyst.analyze(lens=lens, snapshot=snapshot) for lens in LENSES]
        reports = [json.loads(f.value()) for f in pending]

        # Stage 2: the debate. Both sides of a round go at once; the rounds
        # themselves are sequential, because round two is a reply to round one.
        debate = []
        for _ in range(rounds):
            turns = [
                researcher.argue(stance=stance, reports=reports, history=debate)
                for stance in ("bull", "bear")
            ]
            debate += [json.loads(f.value()) for f in turns]

        # Stage 3: the debate has to be judged before anyone acts on it.
        # A rating on the five-point scale, plus the reasoning behind it.
        research = json.loads(
            research_manager.judge(
                ticker=ticker, reports=reports, debate=debate
            ).value()
        )

        # Stage 4: the rating becomes a position to propose.
        plan = json.loads(
            trader.propose(
                ticker=ticker, reports=reports, debate=debate, research=research
            ).value()
        )

        # Stage 5: fan out again, three seats on the same plan.
        reviews = [
            risk.review(stance=stance, plan=plan, snapshot=snapshot) for stance in SEATS
        ]
        verdicts = [json.loads(f.value()) for f in reviews]

        # Stage 6: the last word, bounded by the most cautious seat.
        decision = json.loads(
            manager.decide(ticker=ticker, plan=plan, verdicts=verdicts).value()
        )

        # The answer first, then the working, then what both were based on.
        #
        # The endpoint serves this through Flask's jsonify, which sorts keys
        # alphabetically and throws away whatever order they are written in
        # here. So the order is in the names: "decision" sorts before
        # "deliberation" sorts before "market". Renaming any of these three
        # re-sorts the response, which is the one thing to know before doing
        # it -- there is no key order to preserve, only key names.
        #
        # Grouping also keeps the top level to three entries instead of
        # eleven, so the decision is not one line among many.
        return {
            "decision": decision,
            "deliberation": {
                "analysts": reports,
                "debate": debate,
                "research": research,
                "trader_plan": plan,
                "risk_verdicts": verdicts,
            },
            "market": {
                "query": query,
                "ticker": ticker,
                "as_of": snapshot["as_of"],
                "data_source": snapshot["source"],
                "indicators": snapshot["indicators"],
            },
        }


def _trade_date(query: str) -> str:
    """The ISO date to analyse the market as of, or "" for today.

    Upstream takes this as its second argument, `propagate(ticker, date)`.
    Here it rides in the same string, because `canyonos test` sends one query
    for every argument an endpoint declares -- so a second argument would
    arrive holding the whole sentence rather than a date.
    """
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", query)
    return match.group(1) if match else ""


def _rounds() -> int:
    """How many debate rounds to run, from the manifest.

    Clamped to 1-4: zero rounds would hand the trader nothing to read, and the
    bill grows by two model calls per round with no natural stopping point.
    """
    try:
        rounds = int(os.environ.get("MAX_DEBATE_ROUNDS", DEFAULT_DEBATE_ROUNDS))
    except ValueError:
        rounds = DEFAULT_DEBATE_ROUNDS
    return max(1, min(4, rounds))


def _ticker(query: str) -> str:
    """The ticker the question is about.

    Deliberately not a model call: it would be a round trip before any real
    work starts, and the only input this workflow takes is a sentence with a
    symbol in it.

    Capitalisation is the signal. People write tickers in caps -- "buy NVDA",
    not "buy nvda" -- so a word already in caps wins outright. Only when the
    whole question is lower case does it fall back to guessing, and then a
    stop list keeps "what about aapl" from answering about ABOUT.
    """
    words = [word.strip(".,!?'\";:()$") for word in query.split()]
    candidates = [w for w in words if 1 <= len(w) <= 5 and w.isalpha()]

    for word in candidates:
        if word.isupper() and word not in _SKIP:
            return word
    for word in candidates:
        if word.upper() not in _SKIP:
            return word.upper()

    raise ValueError(
        f"No ticker symbol found in {query!r}. Name one, as in "
        '"Should I buy NVDA right now?".'
    )


# Words of five letters or fewer that would otherwise be read as symbols.
# Only short words can collide, which is what keeps this list short.
_SKIP = {
    "A",
    "ABOUT",
    "AM",
    "AN",
    "AND",
    "ANY",
    "ARE",
    "AT",
    "BE",
    "BUY",
    "CAN",
    "DO",
    "DOES",
    "FOR",
    "GET",
    "GOOD",
    "HOLD",
    "HOW",
    "I",
    "IF",
    "IN",
    "IS",
    "IT",
    "LONG",
    "ME",
    "MY",
    "NOW",
    "OF",
    "ON",
    "OR",
    "OUT",
    "OWN",
    "SELL",
    "SHORT",
    "SO",
    "THE",
    "THIS",
    "TO",
    "TODAY",
    "UP",
    "US",
    "WE",
    "WHAT",
    "WHEN",
    "WHY",
    "WITH",
    "WOULD",
    "YOU",
    "YOUR",
}


if __name__ == "__main__":
    print(_ticker("Should I buy NVDA right now?"))
