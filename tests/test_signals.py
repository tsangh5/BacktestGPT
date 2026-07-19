"""Unit tests for signal rule evaluation on synthetic price data (no network)."""
import pandas as pd
import pytest

from backend.backtest_loop import VectorBTBacktester


@pytest.fixture
def backtester():
    """Build a backtester on synthetic data, bypassing the yfinance download."""
    bt = object.__new__(VectorBTBacktester)
    index = pd.date_range("2024-01-01", periods=6, freq="D")
    bt.ticker = "TEST"
    bt.close = pd.Series([100, 101, 102, 101, 100, 99], index=index, dtype=float)
    bt.open = bt.close - 1
    bt.high = bt.close + 1
    bt.low = bt.close - 2
    bt.volume = pd.Series([1000] * 6, index=index, dtype=float)
    return bt


def test_cross_above_fires_once(backtester):
    fast = pd.Series([1, 1, 3, 3, 3, 3], index=backtester.close.index, dtype=float)
    slow = pd.Series([2, 2, 2, 2, 2, 2], index=backtester.close.index, dtype=float)
    backtester.sma_fast = type("Ind", (), {"ma": fast})()
    backtester.sma_slow = type("Ind", (), {"ma": slow})()

    signal = backtester._apply_signal_rule(
        {"op": "cross_above", "args": ["sma_fast.ma", "sma_slow.ma"]}
    )
    # Fires only on the day of the crossing, not while fast stays above slow
    assert signal.sum() == 1
    assert bool(signal.iloc[2])


def test_greater_than_with_numeric_threshold(backtester):
    signal = backtester._apply_signal_rule(
        {"op": "greater_than", "args": ["Close", "100.5"]}
    )
    assert signal.tolist() == [False, True, True, True, False, False]


def test_unknown_operator_returns_no_signals(backtester):
    signal = backtester._apply_signal_rule(
        {"op": "teleport", "args": ["Close", "Open"]}
    )
    assert not signal.any()


def test_malformed_rule_returns_no_signals(backtester):
    assert not backtester._apply_signal_rule(None).any()
    assert not backtester._apply_signal_rule({"op": "greater_than", "args": []}).any()


def test_resolve_series_price_columns(backtester):
    assert backtester._resolve_series("Close") is backtester.close
    assert backtester._resolve_series("volume") is backtester.volume
    assert backtester._resolve_series("42") == 42.0
    assert backtester._resolve_series(7) == 7
