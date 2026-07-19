"""Unit tests for conversation state and registry loading (no network)."""
from backend.llm_decode import ConversationState, get_registries, is_valid_ticker_format


def test_ticker_format_validation():
    assert is_valid_ticker_format("AAPL")
    assert is_valid_ticker_format("BRK.B")
    assert not is_valid_ticker_format("")
    assert not is_valid_ticker_format("WAY_TOO_LONG_TICKER")
    assert not is_valid_ticker_format("bad ticker!")
    assert not is_valid_ticker_format(None)


def test_registries_load_from_any_cwd():
    indicators, operators, strategies = get_registries()
    assert "SMA" in indicators
    assert any("cross_above" in ops for ops in operators.values())
    assert len(strategies) > 0


def test_new_conversation_reports_all_components_missing():
    state = ConversationState()
    missing = state.get_missing_components()
    assert set(missing) == {"ticker", "indicators", "entry_conditions", "exit_conditions"}
    assert not state.is_complete()


def test_meaningful_rule_detection():
    state = ConversationState()
    assert state._is_meaningful_rule(
        {"op": "cross_above", "args": ["SMA50.ma", "SMA200.ma"]}
    )
    # Comparing price to zero or price to price is treated as a placeholder
    assert not state._is_meaningful_rule({"op": "greater_than", "args": ["Close", "0"]})
    assert not state._is_meaningful_rule({"op": "greater_than", "args": []})


def test_complete_state_builds_strategy_config():
    state = ConversationState()
    state.ticker = "AAPL"
    state.indicators = [
        {"id": "SMA50", "type": "SMA", "params": {"window": 50, "column": "Close"}},
        {"id": "SMA200", "type": "SMA", "params": {"window": 200, "column": "Close"}},
    ]
    state.entry_conditions = {"op": "cross_above", "args": ["SMA50.ma", "SMA200.ma"]}
    state.exit_conditions = {"op": "cross_below", "args": ["SMA50.ma", "SMA200.ma"]}

    assert state.is_complete()
    config = state.to_strategy_config()
    assert config["ticker"] == "AAPL"
    assert config["strategy_config"]["entry"]["op"] == "cross_above"
