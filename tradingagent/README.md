# Trading Agents

Ask about one stock and a whole desk answers: four analysts, a bull/bear
debate, a trader, a three-seat risk committee, and a portfolio manager with the
last word.

The agent topology follows
[TradingAgents](https://github.com/TauricResearch/TradingAgents) — analysts,
researchers, trader, risk debate, portfolio manager. The implementation is
CanyonOS-native Python: no upstream code is vendored here.

It needs one credential, `OPENAI_API_KEY`. Market data comes from Yahoo Finance
through `yfinance`, which needs no key, and falls back to a deterministic
synthetic series when the fetch fails — so the workflow runs offline, and says
so when it does.

## How it works

```
POST /main  {"query": "NVDA 2026-09-01"}

  0. MarketDataAgent        prices, indicators, fundamentals — one snapshot
         │
  1. AnalystAgent           ── FAN-OUT ×4 ──────────────────────┐
     technical · fundamental · sentiment · macro                │
         └────────────────── barrier ─────────────────────────┘
  2. ResearcherAgent        bull ⟷ bear, both at once, ×MAX_DEBATE_ROUNDS
         │
  3. ResearchManagerAgent   judges the debate: Buy/Overweight/Hold/
         │                  Underweight/Sell, with the reasoning
  4. TraderAgent            one proposal: action, size, what would disprove it
         │
  5. RiskAgent              ── FAN-OUT ×3 ──────────────────────┐
     aggressive · conservative · neutral                        │
         └────────────────── barrier ─────────────────────────┘
  6. PortfolioManagerAgent  the decision, capped by the most cautious seat
```

## The input

A ticker and an optional trade date, which is what upstream takes as
`propagate("NVDA", "2026-09-01")`. Both ride in one `query` string:

```
"NVDA 2026-09-01"     analyse NVDA as it stood on that date
"NVDA"                analyse it as of today
"Should I buy NVDA?"  the same — capitalisation is how the ticker is found
```

One argument rather than two, because `canyonos test` sends the same text for
every argument an endpoint declares — so a two-argument endpoint would receive
the whole sentence twice. The date bounds the price window; the fundamentals
Yahoo returns are always current, and the snapshot says so rather than
pretending otherwise.

Two fan-outs, two barriers and a debate loop. That shape is the point of the
example.

**Every agent ships with `replicas: 1`**, so eight agent files become eight
containers plus the endpoint — nine in all. The four analyst calls are still
_dispatched_ together, they just queue on one replica. Raise `AnalystAgent`'s
`replicas` to 4 in the manifest and the same request does the same work in
roughly a quarter of the time, with no code change. That one number is the
shortest demonstration in this repo of what the scheduler is for.

## What's in it

| File                                | What it does                                                       |
| ----------------------------------- | ------------------------------------------------------------------ |
| `agents/workflow.py`                | `Workflow.main(query)` — the orchestration, served at `POST /main` |
| `agents/market_data_agent.py`       | Yahoo Finance prices, RSI, moving averages, volatility, drawdown   |
| `agents/analyst_agent.py`           | One lens per call; the four lenses are in `LENSES`                 |
| `agents/researcher_agent.py`        | One side per call; each round sees the whole debate so far         |
| `agents/trader_agent.py`            | Research → one proposal, validated into a plan                     |
| `agents/risk_agent.py`              | One seat per call; returns a verdict and a size it would accept    |
| `agents/portfolio_manager_agent.py` | The final call — size is arithmetic, not opinion                   |
| `llm.py`                            | The one model call every reasoning agent makes                     |
| `config/global_controller.yaml`     | The agents, their replicas, and the endpoint on `8085`             |
| `config/llms.yaml`                  | Which agents may call the model, and the per-call cost cap         |
| `config/prompts.yaml`               | One versioned system prompt per agent method                       |
| `config/policy.yaml`                | Which callers may reach which agents                               |

## Before you start

- Docker is running, and `canyonos doctor` passes.
- This example is already in CanyonOS format, so skip `canyonos build`.
- Copy `.env.example` to `.env` and put in your `OPENAI_API_KEY`.
- Work on a copy. Deploying writes into the project folder.

```bash
cd tradingagents
cp .env.example .env     # then fill in OPENAI_API_KEY
canyonos deploy
```

## Asking it something

```bash
curl -X POST http://localhost:8085/main \
  -H 'Content-Type: application/json' \
  -d '{"query": "NVDA 2026-09-01"}'

curl http://localhost:8085/status/<request_id>
```

The reply has three parts, and the endpoint serves them in that order:

| Key            | What's in it                                                                                                         |
| -------------- | -------------------------------------------------------------------------------------------------------------------- |
| `decision`     | the answer — action, size, which risk seat set the size, and why                                                     |
| `deliberation` | the working — every analyst report, every turn of the debate, the rating, the trader's plan, all three risk verdicts |
| `market`       | what it was all based on — ticker, date, data source, indicators                                                     |

The order is in the names, not the code: the endpoint serves JSON through
Flask's `jsonify`, which sorts keys alphabetically. `decision` sorts before
`deliberation` sorts before `market`. Renaming any of the three re-sorts the
response.

```bash
curl -s http://localhost:8085/status/<request_id> | jq .result.decision
```

## Things worth changing

- **`replicas` on `AnalystAgent`** (manifest). One by default, so the four
  lenses queue. Four is one per lens, and the request gets roughly four times
  faster for the same work. `RiskAgent` (3 seats) and `ResearcherAgent`
  (2 sides) have the same knob.
- **`MAX_DEBATE_ROUNDS`** (manifest, on `Workflow`). Two model calls per round.
  Clamped to 1-4 by the workflow, because nothing in an argument makes it stop.
- **The per-agent caps in `config/llms.yaml`.** One request is at least 13
  model calls; the caps bound the worst single call.
- **The lenses and seats**, in `LENSES` and `SEATS`. Adding a fifth analyst is
  one entry and one more parallel branch.

## What it is not

It is not financial advice, and it is not a backtest. No agent here can place
an order, and the fundamentals are whatever Yahoo will give up for a symbol.
Treat the output as a worked example of a multi-agent pipeline that happens to
argue about stocks.
