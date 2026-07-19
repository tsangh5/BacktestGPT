"""Agent tests with a mocked Gemini client: clarification turns, complete
strategies, and the validation repair loop — no network or API key needed."""
import json
from types import SimpleNamespace

import pytest

from backend import llm_decode
from backend.llm_decode import decode_natural_language, is_valid_ticker_format


class FakeModels:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        return SimpleNamespace(text=self._responses.pop(0))


def fake_client(monkeypatch, responses):
    models = FakeModels(responses)
    monkeypatch.setattr(llm_decode.genai, "Client", lambda: SimpleNamespace(models=models))
    return models


COMPLETE_STRATEGY = {
    "message": "Backtesting a golden cross on AAPL!",
    "strategy": {
        "ticker": "aapl",
        "indicators": [
            {"id": "sma50", "type": "SMA", "window": 50},
            {"id": "sma200", "type": "SMA", "window": 200},
        ],
        "entry": {
            "op": "cross_above",
            "left": {"kind": "indicator", "indicator_id": "sma50"},
            "right": {"kind": "indicator", "indicator_id": "sma200"},
        },
        "exit": None,
    },
}


def test_ticker_format_validation():
    assert is_valid_ticker_format("AAPL")
    assert is_valid_ticker_format("BRK.B")
    assert not is_valid_ticker_format("")
    assert not is_valid_ticker_format("WAY_TOO_LONG_TICKER")
    assert not is_valid_ticker_format(None)


def test_clarification_turn(monkeypatch):
    fake_client(
        monkeypatch,
        ['{"message": "What entry rule would you like for MSFT?", "strategy": null}'],
    )
    result = decode_natural_language("I want to trade Microsoft")
    assert result["conversation"] is True
    assert result["needs_clarification"] is True
    assert "MSFT" in result["message"]


def test_complete_strategy_runs_backtest(monkeypatch):
    fake_client(monkeypatch, [json.dumps(COMPLETE_STRATEGY)])
    monkeypatch.setattr(llm_decode, "validate_ticker_exists", lambda t: (True, "ok"))

    captured = {}

    def fake_run(spec):
        captured["spec"] = spec
        return {"metrics": {"total_return": float("nan")}, "chart_data": {"equity": [1.0]}}

    monkeypatch.setattr(llm_decode, "run_backtest_spec", fake_run)
    result = decode_natural_language("golden cross on Apple")

    assert captured["spec"].ticker == "AAPL"  # normalized to uppercase
    assert result["message"] == "Backtesting a golden cross on AAPL!"
    assert result["metrics"]["total_return"] is None  # NaN sanitized to null


def test_repair_loop_recovers_from_invalid_json(monkeypatch):
    models = fake_client(
        monkeypatch,
        [
            '{"message": "broken", "strategy": {"ticker": "AAPL"}}',  # missing entry
            '{"message": "Which entry rule?", "strategy": null}',
        ],
    )
    result = decode_natural_language("test")
    assert len(models.calls) == 2
    # Second call must include the validation-error feedback
    feedback = models.calls[1]["contents"][-1].parts[0].text
    assert "failed validation" in feedback
    assert result["message"] == "Which entry rule?"


def test_gives_up_after_two_invalid_responses(monkeypatch):
    fake_client(monkeypatch, ['{"nope": 1}', '{"still": "nope"}'])
    result = decode_natural_language("test")
    assert result["needs_clarification"] is True
    assert "rephrase" in result["message"]


def test_invalid_ticker_asks_for_correction(monkeypatch):
    fake_client(monkeypatch, [json.dumps(COMPLETE_STRATEGY)])
    monkeypatch.setattr(
        llm_decode, "validate_ticker_exists", lambda t: (False, f"No market data for '{t}'")
    )
    result = decode_natural_language("golden cross on Apple")
    assert result["needs_clarification"] is True
    assert "double-check" in result["message"]


def test_backtest_error_becomes_conversational_reply(monkeypatch):
    fake_client(monkeypatch, [json.dumps(COMPLETE_STRATEGY)])
    monkeypatch.setattr(llm_decode, "validate_ticker_exists", lambda t: (True, "ok"))
    monkeypatch.setattr(
        llm_decode, "run_backtest_spec", lambda spec: {"error": "no data in range"}
    )
    result = decode_natural_language("golden cross on Apple")
    assert result["needs_clarification"] is True
    assert "no data in range" in result["message"]


def test_conversation_history_passed_to_model(monkeypatch):
    models = fake_client(monkeypatch, ['{"message": "ok", "strategy": null}'])
    history = [
        {"role": "assistant", "content": "Hi!"},
        {"role": "user", "content": "Trade AAPL"},
    ]
    decode_natural_language("use RSI", conversation_history=history)
    contents = models.calls[0]["contents"]
    assert [c.role for c in contents] == ["model", "user", "user"]
    assert contents[-1].parts[0].text == "use RSI"
