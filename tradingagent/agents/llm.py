# SPDX-FileCopyrightText: 2026 Canyon Code, Inc.
# SPDX-License-Identifier: AGPL-3.0-only

# The one model call every reasoning agent in this workflow makes.
#
# Nothing here names an endpoint. CanyonOS sets OPENAI_BASE_URL in every agent
# container so the call goes through its own LLM gateway, which applies the
# caps in config/llms.yaml, prepends the agent's system prompt from
# config/prompts.yaml, and records token and cost telemetry against this
# execution. The workflow's only credential is OPENAI_API_KEY.
#
# Six agents make the same shaped call, so it lives here rather than six times
# over.
#
# Not an agent, despite sitting in agents/: nothing in the manifest names it,
# so it has no container and no replicas of its own. It is a module that ships
# inside each agent's image and runs there. The manifest's entrypoint list is
# what says which files here are services.

import os

# A GPT-4-class model, and a small one on purpose: one request here is at
# least 14 calls, so the per-call price is multiplied by fourteen before
# anyone sees an answer. Override with OPENAI_MODEL to use a larger one.
DEFAULT_MODEL = "gpt-4o-mini"


# A cap on output tokens, off unless MAX_OUTPUT_TOKENS is set. Unset is the
# right default: on a reasoning model the cap covers the thinking as well as
# the answer, so a number chosen to bound the prose starves the reasoning and
# the model returns nothing at all. Set it only to bound a model that runs
# away and trips a timeout -- which is what upstream TradingAgents uses its
# own `max_tokens` for, and why theirs defaults to None too.
MAX_OUTPUT_TOKENS = os.environ.get("MAX_OUTPUT_TOKENS")


def ask(prompt: str) -> str:
    """Send one prompt and return the reply as text.

    Raises on failure rather than returning a placeholder: a trading opinion
    invented because the model was unreachable is worse than no opinion, and
    the stage that called this says which agent it was.

    Sends neither `temperature` nor a token cap, so every model answers the
    way it wants to. Reasoning models reject any temperature but their own and
    spend a token budget on thinking; leaving both unset is what lets this run
    against whatever OPENAI_MODEL names. Each agent asks for the length it
    wants in words, and the ones parsing JSON validate what comes back.
    """
    from openai import OpenAI

    options = {}
    if MAX_OUTPUT_TOKENS:
        # Not `max_tokens`: newer models reject that name outright with a 400
        # ("Use 'max_completion_tokens' instead"), while every model that
        # still accepts the old name also accepts this one.
        options["max_completion_tokens"] = int(MAX_OUTPUT_TOKENS)

    response = OpenAI().chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", DEFAULT_MODEL),
        messages=[{"role": "user", "content": prompt}],
        **options,
    )

    choice = response.choices[0]
    text = (choice.message.content or "").strip()
    if text:
        return text

    if choice.finish_reason == "length":
        raise ValueError(
            f"The model stopped at the {MAX_OUTPUT_TOKENS}-token cap without "
            "finishing an answer. On a reasoning model that cap covers the "
            "thinking too; raise MAX_OUTPUT_TOKENS or unset it."
        )
    raise ValueError(
        f"The model returned no content (finish_reason={choice.finish_reason!r})."
    )


def describe(snapshot: dict) -> str:
    """One market snapshot as the plain text every analyst is given.

    Written once so the four analysts genuinely disagree about the same
    figures, rather than about four slightly different renderings of them.
    """
    lines = [f"Ticker: {snapshot['ticker']}"]
    if snapshot.get("source") == "synthetic":
        lines.append(
            "NOTE: live market data was unavailable. These figures are synthetic "
            "and must not be presented as real. Say so in your answer."
        )

    indicators = snapshot.get("indicators") or {}
    if indicators:
        lines.append("\nPrice and indicators:")
        lines += [f"  {name}: {value}" for name, value in indicators.items()]

    fundamentals = snapshot.get("fundamentals") or {}
    if not fundamentals:
        lines.append("\nFundamentals: unavailable for this ticker.")
        return "\n".join(lines)

    lines.append("\nFundamentals:")
    lines += [f"  {name}: {value}" for name, value in fundamentals.items()]

    # The prices are bounded by `as_of`; these are not. Yahoo returns whatever
    # is current, so a question about a past date gets a past chart and
    # present fundamentals. Nobody can tell that from the numbers, so it is
    # said here -- this is the difference between an example and a backtest.
    as_of = snapshot.get("as_of")
    if snapshot.get("fundamentals_are_current") and as_of not in (None, "", "today"):
        lines.append(
            f"  NOTE: these are today's figures, not as they stood on {as_of}. "
            "The price history above does end there. Say so if you rely on them."
        )

    return "\n".join(lines)
