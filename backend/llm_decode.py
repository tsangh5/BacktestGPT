"""Natural-language → StrategySpec agent.

One structured Gemini call per turn: the model sees the full conversation and
returns an AgentResponse — either a clarifying question (strategy=null) or a
complete, schema-valid StrategySpec. Constrained decoding guarantees the JSON
shape; Pydantic validates semantics; a single repair retry feeds validation
errors back to the model. Conversation state lives in the chat history the
frontend already sends, so the server stays stateless.
"""
import math
import re
import time

import yfinance as yf
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import ValidationError

from backend.backtest_loop import run_backtest_spec
from backend.schema import AgentResponse

load_dotenv()

MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """\
You are BacktestGPT, an assistant that turns natural-language trading strategy
descriptions into precise, executable backtest specifications.

Each turn, return an AgentResponse JSON object:
- If anything essential is missing or ambiguous, set strategy to null and ask
  ONE friendly, specific question in `message`. Build on what the conversation
  has already established — never re-ask for information the user has given.
- Once the strategy is fully specified, fill in `strategy` and write a short
  confirmation in `message` summarizing what you're about to backtest.

What counts as essential: a ticker, and an entry rule. An exit rule is
strongly preferred — if the user gave none, ask once; if they decline or say
"just hold", leave exit null. Everything else has sensible defaults (start
2015-01-01, end today, $100,000 cash, 0.1% fees) — use the user's values when
given, defaults otherwise, and do NOT ask about them.

How to build the spec:
- Declare every indicator you reference in `indicators` with a unique id
  (e.g. "50-day SMA" -> {id: "sma50", type: "SMA", window: 50}).
- Conditions are trees: comparisons (gt, lt, gte, lte, cross_above,
  cross_below) compare two operands; and/or/not combine sub-conditions, so
  compound rules like "RSI below 30 AND price above the 200-day SMA" become
  {op: "and", conditions: [...]}.
- Operands are recursive value expressions:
  * {kind: "indicator", indicator_id, output} for indicator values.
    Outputs: SMA/EMA -> ma; RSI -> rsi; BB -> middle, upper, lower;
    MACD -> macd, signal, hist.
  * {kind: "price", column} for raw prices; {kind: "constant", value} for numbers.
  * {kind: "transform", transform, operand, periods?, window?} derives a new
    series: pct_change (fractional change over `periods` bars, default 1),
    shift (value `periods` bars ago), rolling_max / rolling_min /
    rolling_mean / rolling_std (over `window` bars), abs.
  * {kind: "math", op: add|sub|mul|div, left, right} for arithmetic between
    expressions.
- Use transforms for anything not covered by a named indicator. Examples:
  * "falls 2% in a day" -> pct_change(Close, 1) lte -0.02  (percentages are
    fractions: 2% -> 0.02; "falls"/"drops" are negative changes)
  * "10% below its 52-week high" ->
    Close lte mul(rolling_max(Close, 252), 0.9)   (252 trading days/year, 21/month)
  * "volume is twice its 20-day average" ->
    Volume gte mul(rolling_mean(Volume, 20), 2)
  * "gap up 1% at the open" -> Open gte mul(shift(Close, 1), 1.01)
  * "down 3 days in a row" -> and: [Close lt shift(Close,1),
    shift(Close,1) lt shift(Close,2), shift(Close,2) lt shift(Close,3)]
- "Golden cross" = 50-day SMA cross_above 200-day SMA; "death cross" is the
  reverse. "MACD crosses above its signal line" compares outputs macd and
  signal of one MACD indicator.
- Stop-losses and take-profits go in stop_loss / take_profit as fractions
  (5% -> 0.05), not as exit conditions.
- Map company names to tickers (Apple -> AAPL, Microsoft -> MSFT, etc.).
- If the user corrects an earlier detail, use the corrected value.

If the user asks for something these building blocks cannot express — news or
sentiment triggers, earnings dates, fundamentals (P/E, revenue), intraday
timing, options, shorting, or multi-asset portfolios — do NOT approximate it
with something else. Set strategy to null and briefly say that part isn't
supported, naming the closest thing you CAN do (price/volume behavior,
technical indicators, stops). Never silently substitute a different strategy
than the one the user asked for.

Only emit a strategy when you are confident it reflects the user's intent.
"""

# ---------------------------------------------------------------------------
# Ticker validation (with cache, to avoid repeated yfinance calls)
# ---------------------------------------------------------------------------

_ticker_cache: dict = {}


def is_valid_ticker_format(ticker) -> bool:
    if not ticker or not isinstance(ticker, str):
        return False
    ticker = ticker.strip().upper()
    return bool(re.match(r"^[A-Z0-9.-]{1,10}$", ticker))


def validate_ticker_exists(ticker):
    """Returns (is_valid, message). Results are cached per process."""
    if not is_valid_ticker_format(ticker):
        return False, f"Ticker '{ticker}' has an invalid format"
    ticker = ticker.strip().upper()
    if ticker in _ticker_cache:
        return _ticker_cache[ticker]
    try:
        hist = yf.Ticker(ticker).history(period="5d")
        result = (
            (True, f"Ticker '{ticker}' is valid")
            if not hist.empty
            else (False, f"No market data available for ticker '{ticker}'")
        )
    except Exception as e:
        result = (False, f"Could not validate ticker '{ticker}': {e}")
    _ticker_cache[ticker] = result
    return result


# ---------------------------------------------------------------------------
# Gemini call with structured output + retry/repair
# ---------------------------------------------------------------------------

def _build_contents(conversation_history, user_input):
    contents = []
    for msg in conversation_history or []:
        role = "user" if msg.get("role") == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg.get("content", ""))]))
    contents.append(types.Content(role="user", parts=[types.Part(text=user_input)]))
    return contents


def _generate(client, contents):
    """One structured-output call with retries for transient API errors."""
    last_error = None
    for attempt in range(3):
        try:
            return client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_json_schema=AgentResponse.model_json_schema(),
                ),
            )
        except Exception as e:
            last_error = e
            if any(s in str(e).lower() for s in ("503", "overloaded", "unavailable", "429")):
                time.sleep(2 * (attempt + 1))
                continue
            raise
    raise last_error


def _sanitize(obj):
    """Replace NaN/inf with None so the payload is valid JSON (charts render
    nulls as gaps, which is correct for indicator warm-up periods)."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def _conversation_reply(message):
    return {"conversation": True, "message": message, "needs_clarification": True}


def decode_natural_language(user_input, conversation_history=None):
    client = genai.Client()
    contents = _build_contents(conversation_history, user_input)

    agent = None
    for attempt in range(2):
        try:
            response = _generate(client, contents)
        except Exception as e:
            print(f"[agent] Gemini call failed: {e}")
            return _conversation_reply(
                "I'm having trouble reaching the AI service right now — please try again "
                "in a moment."
            )
        try:
            agent = AgentResponse.model_validate_json(response.text)
            break
        except ValidationError as e:
            # Repair loop: show the model its own output and the validation
            # errors, and let it try once more.
            print(f"[agent] validation failed (attempt {attempt + 1}): {e}")
            contents.append(types.Content(role="model", parts=[types.Part(text=response.text)]))
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            text="Your previous response failed validation with these "
                            f"errors:\n{e}\nReturn a corrected AgentResponse."
                        )
                    ],
                )
            )

    if agent is None:
        return _conversation_reply(
            "I couldn't turn that into a valid strategy — could you rephrase it? "
            "For example: \"Buy AAPL when the 50-day SMA crosses above the 200-day "
            "SMA, sell on the reverse cross.\""
        )

    if agent.strategy is None:
        return _conversation_reply(agent.message)

    spec = agent.strategy
    spec.ticker = spec.ticker.strip().upper()
    is_valid, ticker_message = validate_ticker_exists(spec.ticker)
    if not is_valid:
        return _conversation_reply(
            f"{ticker_message}. Could you double-check the ticker symbol or name "
            "the company you'd like to trade?"
        )

    result = run_backtest_spec(spec)
    if result.get("error"):
        return _conversation_reply(
            f"I built your strategy but the backtest failed: {result['error']}. "
            "Want to try a different date range or ticker?"
        )

    result["message"] = agent.message
    return _sanitize(result)
