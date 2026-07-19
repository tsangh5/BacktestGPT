"""Engine tests on synthetic price data (no network): indicator computation,
condition-tree evaluation, and a full spec execution via a patched data fetch."""
import numpy as np
import pandas as pd
import pytest

from backend import backtest_loop
from backend.backtest_loop import (
    compute_indicators,
    evaluate_condition,
    run_backtest_spec,
)
from backend.schema import Condition, Indicator, Operand, StrategySpec


@pytest.fixture
def price():
    idx = pd.date_range("2022-01-01", periods=300, freq="D")
    rng = np.random.default_rng(42)
    close = pd.Series(100 + np.cumsum(rng.normal(0.05, 1, 300)), index=idx)
    return {
        "Close": close,
        "Open": close.shift(1).fillna(close.iloc[0]),
        "High": close + 1,
        "Low": close - 1,
        "Volume": pd.Series(1_000_000.0, index=idx),
    }


def test_all_indicator_types_compute(price):
    indicators = [
        Indicator(id="sma20", type="SMA", window=20),
        Indicator(id="ema20", type="EMA", window=20),
        Indicator(id="rsi14", type="RSI", window=14),
        Indicator(id="bb", type="BB", window=20),
        Indicator(id="macd", type="MACD"),
    ]
    values = compute_indicators(price, indicators)
    assert set(values["sma20"]) == {"ma"}
    assert set(values["ema20"]) == {"ma"}
    assert set(values["rsi14"]) == {"rsi"}
    assert set(values["bb"]) == {"middle", "upper", "lower"}
    assert set(values["macd"]) == {"macd", "signal", "hist"}
    # EMA must actually differ from SMA (the old engine silently zeroed EMAs)
    assert not values["ema20"]["ma"].equals(values["sma20"]["ma"])
    # BB bands ordered correctly
    tail = values["bb"]
    assert (tail["upper"].dropna() >= tail["middle"].dropna()).all()


def test_cross_above_fires_only_on_crossing_bar(price):
    idx = price["Close"].index[:6]
    fast = pd.Series([1, 1, 3, 3, 3, 3], index=idx, dtype=float)
    slow = pd.Series([2, 2, 2, 2, 2, 2], index=idx, dtype=float)
    values = {"fast": {"ma": fast}, "slow": {"ma": slow}}
    types_map = {"fast": "SMA", "slow": "SMA"}
    cond = Condition(
        op="cross_above",
        left=Operand(kind="indicator", indicator_id="fast"),
        right=Operand(kind="indicator", indicator_id="slow"),
    )
    small_price = {k: v.iloc[:6] for k, v in price.items()}
    signal = evaluate_condition(cond, small_price, values, types_map)
    assert signal.sum() == 1 and bool(signal.iloc[2])


def test_compound_and_condition(price):
    values = compute_indicators(price, [Indicator(id="rsi14", type="RSI", window=14)])
    types_map = {"rsi14": "RSI"}
    rsi_low = Condition(
        op="lt",
        left=Operand(kind="indicator", indicator_id="rsi14"),
        right=Operand(kind="constant", value=45),
    )
    price_high = Condition(
        op="gt",
        left=Operand(kind="price", column="Close"),
        right=Operand(kind="constant", value=float(price["Close"].median())),
    )
    combined = Condition(op="and", conditions=[rsi_low, price_high])
    a = evaluate_condition(rsi_low, price, values, types_map).fillna(False)
    b = evaluate_condition(price_high, price, values, types_map)
    both = evaluate_condition(combined, price, values, types_map).fillna(False)
    assert both.equals(a & b)
    assert both.sum() <= min(a.sum(), b.sum())


def test_not_condition_inverts(price):
    cond = Condition(
        op="gt",
        left=Operand(kind="price", column="Close"),
        right=Operand(kind="constant", value=0),
    )
    negated = Condition(op="not", conditions=[cond])
    assert not evaluate_condition(negated, price, {}, {}).any()


def test_full_spec_run_with_patched_fetch(price, monkeypatch):
    monkeypatch.setattr(backtest_loop, "fetch_price_data", lambda *a, **k: price)
    spec = StrategySpec(
        ticker="TEST",
        stop_loss=0.05,
        indicators=[
            Indicator(id="sma10", type="SMA", window=10),
            Indicator(id="sma30", type="SMA", window=30),
        ],
        entry=Condition(
            op="cross_above",
            left=Operand(kind="indicator", indicator_id="sma10"),
            right=Operand(kind="indicator", indicator_id="sma30"),
        ),
        exit=Condition(
            op="cross_below",
            left=Operand(kind="indicator", indicator_id="sma10"),
            right=Operand(kind="indicator", indicator_id="sma30"),
        ),
    )
    result = run_backtest_spec(spec)
    assert "error" not in result
    metrics = result["metrics"]
    assert metrics["start_value"] == 100_000
    assert metrics["total_trades"] >= 1
    chart = result["chart_data"]
    assert len(chart["dates"]) == 300
    assert set(chart["indicators"]) == {"sma10", "sma30"}
    assert sum(chart["signals"]["Entries"]) >= 1


def test_spec_run_surfaces_fetch_error(monkeypatch):
    def boom(*a, **k):
        raise ValueError("No price data returned for 'NOPE'")

    monkeypatch.setattr(backtest_loop, "fetch_price_data", boom)
    spec = StrategySpec(
        ticker="NOPE",
        entry=Condition(
            op="gt",
            left=Operand(kind="price", column="Close"),
            right=Operand(kind="constant", value=0),
        ),
    )
    result = run_backtest_spec(spec)
    assert "No price data" in result["error"]
