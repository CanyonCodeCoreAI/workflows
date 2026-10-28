# SPDX-FileCopyrightText: 2026 Canyon Code, Inc.
# SPDX-License-Identifier: AGPL-3.0-only

# Market Data Agent
#
# The only agent that reaches outside the cluster. Fetches daily closing prices
# and headline fundamentals for one ticker from Yahoo Finance via `yfinance`,
# which needs no API key -- the workflow's only credential is OPENAI_API_KEY.
#
# If the fetch fails (offline, rate-limited, unknown ticker) it falls back to a
# deterministic synthetic series seeded by the ticker, so the pipeline always
# returns something to reason about and the example stays zero-setup. The
# `source` field says which happened, and every downstream agent is told, so a
# synthetic run is never passed off as real market data.
#
# Resource profile: network/IO-bound, cheap CPU. Every analyst calls it, so it
# computes the indicators once here rather than four times downstream.

import datetime
import math
import statistics

TRADING_DAYS = 252


def _window(lookback_days: int, as_of: str) -> dict:
    """The yfinance arguments for a lookback window ending at `as_of`.

    A relative `period` when the window ends today, which is what yfinance is
    happiest with, and an explicit start/end pair when it does not. An
    unparseable date falls back to today rather than failing the request: the
    analysis is still worth running, and the snapshot records which date it
    actually used.
    """
    if not as_of:
        return {"period": f"{lookback_days}d"}
    try:
        end = datetime.date.fromisoformat(as_of)
    except ValueError:
        print(f"MarketDataAgent: {as_of!r} is not an ISO date; using today.")
        return {"period": f"{lookback_days}d"}

    start = end - datetime.timedelta(days=lookback_days)
    # yfinance's `end` is exclusive, so the named day is included.
    return {
        "start": start.isoformat(),
        "end": (end + datetime.timedelta(days=1)).isoformat(),
    }


class MarketDataAgent(object):
    def __init__(self):
        self.tools = [self.snapshot]

    def snapshot(self, ticker: str, lookback_days: int = 180, as_of: str = "") -> dict:
        """Prices, derived indicators and fundamentals for one ticker.

        `as_of` is an ISO date to analyse the market as it stood on, matching
        upstream's second argument to `propagate(ticker, trade_date)`. Empty
        means today. It bounds the price window; the fundamentals Yahoo
        returns are always current, which the snapshot records rather than
        pretends otherwise.
        """
        prices = self._prices(ticker, lookback_days, as_of)
        return {
            "ticker": ticker,
            "as_of": as_of or "today",
            "source": prices["source"],
            "closes": prices["closes"],
            "indicators": self._indicators(prices["closes"]),
            "fundamentals": self._fundamentals(ticker),
            # Said plainly because every analyst is shown this snapshot and
            # none of them can tell from the numbers alone.
            "fundamentals_are_current": True,
        }

    def _prices(self, ticker: str, lookback_days: int, as_of: str) -> dict:
        try:
            import yfinance as yf

            history = yf.Ticker(ticker).history(**_window(lookback_days, as_of))
            # Yahoo sometimes appends today's row before its close has settled,
            # leaving Close as NaN -- drop it rather than let NaN poison every
            # indicator computed below.
            closes = [float(c) for c in history["Close"].tolist() if not math.isnan(c)]
            if closes:
                return {"closes": closes, "source": "yfinance"}
        except Exception as e:
            print(f"MarketDataAgent: yfinance failed for {ticker} ({e}); synthesising.")

        return {"closes": self._synthetic(ticker, lookback_days), "source": "synthetic"}

    def _fundamentals(self, ticker: str) -> dict:
        """Headline figures, as far as Yahoo will give them up.

        Every field is optional: Yahoo omits different ones per ticker, and an
        absent figure is reported as absent rather than guessed at, so the
        analyst reasoning over it knows what it does not have.
        """
        wanted = {
            "market_cap": "marketCap",
            "trailing_pe": "trailingPE",
            "forward_pe": "forwardPE",
            "profit_margin": "profitMargins",
            "revenue_growth": "revenueGrowth",
            "debt_to_equity": "debtToEquity",
            "sector": "sector",
        }
        try:
            import yfinance as yf

            info = yf.Ticker(ticker).info or {}
        except Exception as e:
            print(f"MarketDataAgent: fundamentals unavailable for {ticker} ({e}).")
            return {}

        return {
            name: info[key] for name, key in wanted.items() if info.get(key) is not None
        }

    def _indicators(self, closes: list) -> dict:
        """Momentum, trend and volatility, computed here so the four analysts
        argue over one set of numbers rather than four slightly different ones."""
        if len(closes) < 2:
            return {}

        latest = closes[-1]
        returns = [
            (closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(1, len(closes))
            if closes[i - 1]
        ]

        indicators = {
            "last_close": round(latest, 2),
            "change_pct": round((latest / closes[0] - 1) * 100, 2),
            "high": round(max(closes), 2),
            "low": round(min(closes), 2),
            "rsi_14": self._rsi(closes),
        }
        for window in (20, 50):
            if len(closes) >= window:
                average = statistics.fmean(closes[-window:])
                indicators[f"sma_{window}"] = round(average, 2)
                indicators[f"above_sma_{window}"] = latest > average
        if len(returns) >= 2:
            annualised = statistics.stdev(returns) * math.sqrt(TRADING_DAYS)
            indicators["annualised_volatility_pct"] = round(annualised * 100, 2)
            indicators["max_drawdown_pct"] = self._max_drawdown(closes)
        return indicators

    @staticmethod
    def _rsi(closes: list, period: int = 14) -> float | None:
        """Wilder's RSI. None when the window is shorter than the period, rather
        than a number computed from too little data."""
        if len(closes) <= period:
            return None
        gains, losses = [], []
        for i in range(1, period + 1):
            change = closes[-i] - closes[-i - 1]
            (gains if change >= 0 else losses).append(abs(change))
        average_gain = sum(gains) / period
        average_loss = sum(losses) / period
        if average_loss == 0:
            return 100.0
        strength = average_gain / average_loss
        return round(100 - (100 / (1 + strength)), 2)

    @staticmethod
    def _max_drawdown(closes: list) -> float:
        peak, worst = closes[0], 0.0
        for close in closes:
            peak = max(peak, close)
            worst = min(worst, (close - peak) / peak)
        return round(worst * 100, 2)

    @staticmethod
    def _synthetic(ticker: str, lookback_days: int) -> list:
        """A deterministic pseudo-random walk seeded by the ticker, so an
        offline run still differs per symbol and repeats exactly."""
        import random

        rng = random.Random(sum(ord(c) for c in ticker))
        drift = (rng.random() - 0.45) * 0.002
        volatility = 0.01 + rng.random() * 0.02
        price = 50.0 + rng.random() * 200.0

        closes = []
        for _ in range(max(lookback_days, 2)):
            price = max(1.0, price * (1.0 + rng.gauss(drift, volatility)))
            closes.append(round(price, 2))
        return closes


if __name__ == "__main__":
    snapshot = MarketDataAgent().snapshot("NVDA", 180)
    print(f"{snapshot['ticker']} [{snapshot['source']}] {snapshot['indicators']}")
