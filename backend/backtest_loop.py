"""Backtest engine: executes a validated StrategySpec against market data.

The spec is a typed AST (see schema.py), so execution is a deterministic
tree-walk — no LLM output is interpreted here. Anything schema-valid runs;
anything else never reaches this module.
"""
from datetime import date
from typing import Dict, Optional

import pandas as pd
import vectorbt as vbt

from backend.schema import (
    Condition,
    Indicator,
    INDICATOR_OUTPUTS,
    Operand,
    StrategySpec,
)

DEFAULT_WINDOWS = {"SMA": 20, "EMA": 20, "RSI": 14, "BB": 20}


def fetch_price_data(ticker: str, start_date: str, end_date: Optional[str]) -> Dict[str, pd.Series]:
    end = end_date or date.today().isoformat()
    data = vbt.YFData.download(ticker, start=start_date, end=end, missing_index="drop")
    price = {col: data.get(col) for col in ("Close", "Open", "High", "Low", "Volume")}
    if price["Close"] is None or len(price["Close"]) == 0:
        raise ValueError(f"No price data returned for '{ticker}' between {start_date} and {end}")
    return price


def compute_indicators(
    price: Dict[str, pd.Series], indicators: list[Indicator]
) -> Dict[str, Dict[str, pd.Series]]:
    """Compute every declared indicator, keyed by id then output name."""
    values: Dict[str, Dict[str, pd.Series]] = {}
    for ind in indicators:
        series = price[ind.column]
        window = ind.window or DEFAULT_WINDOWS.get(ind.type)
        if ind.type == "SMA":
            values[ind.id] = {"ma": vbt.MA.run(series, window).ma}
        elif ind.type == "EMA":
            values[ind.id] = {"ma": vbt.MA.run(series, window, ewm=True).ma}
        elif ind.type == "RSI":
            values[ind.id] = {"rsi": vbt.RSI.run(series, window=window).rsi}
        elif ind.type == "BB":
            bb = vbt.BBANDS.run(series, window=window, alpha=ind.std or 2.0)
            values[ind.id] = {"middle": bb.middle, "upper": bb.upper, "lower": bb.lower}
        elif ind.type == "MACD":
            macd = vbt.MACD.run(
                series,
                fast_window=ind.fast_window or 12,
                slow_window=ind.slow_window or 26,
                signal_window=ind.signal_window or 9,
            )
            values[ind.id] = {"macd": macd.macd, "signal": macd.signal, "hist": macd.hist}
    return values


def resolve_operand(
    operand: Operand,
    price: Dict[str, pd.Series],
    indicator_values: Dict[str, Dict[str, pd.Series]],
    indicator_types: Dict[str, str],
):
    if operand.kind == "constant":
        return operand.value
    if operand.kind == "price":
        return price[operand.column]
    if operand.kind == "indicator":
        outputs = indicator_values[operand.indicator_id]
        # Default to the indicator's primary output when unspecified
        output = operand.output or INDICATOR_OUTPUTS[indicator_types[operand.indicator_id]][0]
        return outputs[output]

    if operand.kind == "transform":
        inner = resolve_operand(operand.operand, price, indicator_values, indicator_types)
        if not isinstance(inner, pd.Series):
            raise ValueError(f"transform '{operand.transform}' requires a series input")
        if operand.transform == "pct_change":
            return inner.pct_change(operand.periods or 1)
        if operand.transform == "shift":
            return inner.shift(operand.periods or 1)
        if operand.transform == "rolling_max":
            return inner.rolling(operand.window).max()
        if operand.transform == "rolling_min":
            return inner.rolling(operand.window).min()
        if operand.transform == "rolling_mean":
            return inner.rolling(operand.window).mean()
        if operand.transform == "rolling_std":
            return inner.rolling(operand.window).std()
        return inner.abs()

    # kind == "math": elementwise arithmetic; pandas broadcasts scalars
    left = resolve_operand(operand.left, price, indicator_values, indicator_types)
    right = resolve_operand(operand.right, price, indicator_values, indicator_types)
    if operand.op == "add":
        return left + right
    if operand.op == "sub":
        return left - right
    if operand.op == "mul":
        return left * right
    return left / right


def evaluate_condition(
    cond: Condition,
    price: Dict[str, pd.Series],
    indicator_values: Dict[str, Dict[str, pd.Series]],
    indicator_types: Dict[str, str],
) -> pd.Series:
    """Recursively evaluate a condition tree into a boolean signal series."""
    if cond.op in ("and", "or", "not"):
        children = [
            evaluate_condition(sub, price, indicator_values, indicator_types)
            for sub in cond.conditions
        ]
        if cond.op == "not":
            return ~children[0]
        result = children[0]
        for child in children[1:]:
            result = (result & child) if cond.op == "and" else (result | child)
        return result

    left = resolve_operand(cond.left, price, indicator_values, indicator_types)
    right = resolve_operand(cond.right, price, indicator_values, indicator_types)

    if cond.op in ("cross_above", "cross_below"):
        # Crossings need both sides as series to compare against the prior bar
        index = price["Close"].index
        if not isinstance(left, pd.Series):
            left = pd.Series(left, index=index, dtype=float)
        if not isinstance(right, pd.Series):
            right = pd.Series(right, index=index, dtype=float)
        if cond.op == "cross_above":
            return (left > right) & (left.shift(1) <= right.shift(1))
        return (left < right) & (left.shift(1) >= right.shift(1))

    ops = {
        "gt": lambda a, b: a > b,
        "lt": lambda a, b: a < b,
        "gte": lambda a, b: a >= b,
        "lte": lambda a, b: a <= b,
    }
    return ops[cond.op](left, right)


def _safe_float(value, default=0.0) -> float:
    try:
        return float(value) if not pd.isna(value) else default
    except (TypeError, ValueError):
        return default


def _build_metrics(portfolio, close: pd.Series) -> dict:
    stats = portfolio.stats()
    start_value = _safe_float(stats["Start Value"])
    end_value = _safe_float(stats["End Value"])
    years = (close.index[-1] - close.index[0]).days / 365.25
    cagr = ((end_value / start_value) ** (1 / years) - 1) if years > 0 and start_value > 0 else 0.0
    return {
        "start_value": start_value,
        "end_value": end_value,
        "total_return": _safe_float(stats["Total Return [%]"]),
        "CAGR": cagr * 100,
        "max_drawdown": _safe_float(stats["Max Drawdown [%]"]),
        "sharpe_ratio": _safe_float(stats["Sharpe Ratio"]),
        "sortino_ratio": _safe_float(stats.get("Sortino Ratio", 0.0)),
        "win_rate": _safe_float(stats["Win Rate [%]"]),
        "avg_winning_trade": _safe_float(stats.get("Avg Winning Trade [%]", 0.0)),
        "avg_losing_trade": _safe_float(stats.get("Avg Losing Trade [%]", 0.0)),
        "profit_factor": _safe_float(stats.get("Profit Factor", 0.0)),
        "total_trades": int(_safe_float(stats["Total Trades"])),
        "years": years,
    }


def _build_chart_data(
    portfolio,
    price: Dict[str, pd.Series],
    indicator_values: Dict[str, Dict[str, pd.Series]],
    entries: pd.Series,
    exits: pd.Series,
) -> dict:
    equity = portfolio.value()
    chart = {
        "dates": equity.index.strftime("%Y-%m-%d").tolist(),
        "equity": equity.tolist(),
        "drawdown": (portfolio.drawdown() * 100).tolist(),
        "close": price["Close"].tolist(),
        "indicators": {
            f"{ind_id}.{output}" if len(outputs) > 1 else ind_id: series.tolist()
            for ind_id, outputs in indicator_values.items()
            for output, series in outputs.items()
        },
        "signals": {
            "Entries": entries.astype(int).tolist(),
            "Exits": exits.astype(int).tolist(),
        },
    }
    return chart


def run_backtest_spec(spec: StrategySpec) -> dict:
    """Execute a validated strategy spec. Returns metrics + chart data,
    or an `error` key with a human-readable message."""
    try:
        price = fetch_price_data(spec.ticker, spec.start_date, spec.end_date)
        indicator_values = compute_indicators(price, spec.indicators)
        indicator_types = {ind.id: ind.type for ind in spec.indicators}

        entries = evaluate_condition(spec.entry, price, indicator_values, indicator_types)
        if spec.exit is not None:
            exits = evaluate_condition(spec.exit, price, indicator_values, indicator_types)
        else:
            exits = pd.Series(False, index=price["Close"].index)

        portfolio = vbt.Portfolio.from_signals(
            close=price["Close"],
            entries=entries.fillna(False),
            exits=exits.fillna(False),
            init_cash=spec.initial_cash,
            fees=spec.fees,
            sl_stop=spec.stop_loss,
            tp_stop=spec.take_profit,
            freq="D",
        )

        return {
            "metrics": _build_metrics(portfolio, price["Close"]),
            "chart_data": _build_chart_data(portfolio, price, indicator_values, entries, exits),
            "strategy": spec.model_dump(exclude_none=True),
        }
    except Exception as e:  # surface a clean message rather than a traceback
        print(f"[ERROR] Backtest failed: {e}")
        return {"error": str(e), "metrics": None, "chart_data": None}


# ---------------------------------------------------------------------------
# Legacy named-strategy support for the /backtest endpoint: builds a
# StrategySpec so both endpoints share one execution path.
# ---------------------------------------------------------------------------

def _legacy_spec(ticker, strategy, start_date, end_date, initial_cash, fees, **params) -> StrategySpec:
    def sma_operand(ind_id):
        return Operand(kind="indicator", indicator_id=ind_id, output="ma")

    if strategy == "RSI":
        window = params.get("rsi_period", 14)
        rsi = Operand(kind="indicator", indicator_id="rsi", output="rsi")
        return StrategySpec(
            ticker=ticker, start_date=start_date, end_date=end_date,
            initial_cash=initial_cash, fees=fees,
            indicators=[Indicator(id="rsi", type="RSI", window=window)],
            entry=Condition(op="lt", left=rsi,
                            right=Operand(kind="constant", value=params.get("rsi_oversold", 30))),
            exit=Condition(op="gt", left=rsi,
                           right=Operand(kind="constant", value=params.get("rsi_overbought", 70))),
        )

    # Default: SMA crossover
    fast, slow = params.get("sma_fast", 5), params.get("sma_slow", 20)
    return StrategySpec(
        ticker=ticker, start_date=start_date, end_date=end_date,
        initial_cash=initial_cash, fees=fees,
        indicators=[
            Indicator(id="sma_fast", type="SMA", window=fast),
            Indicator(id="sma_slow", type="SMA", window=slow),
        ],
        entry=Condition(op="cross_above", left=sma_operand("sma_fast"), right=sma_operand("sma_slow")),
        exit=Condition(op="cross_below", left=sma_operand("sma_fast"), right=sma_operand("sma_slow")),
    )


def run_backtest(ticker="SPY", strategy="SMA", start_date="2015-01-01", end_date=None,
                 initial_cash=100_000, fees=0.001, **strategy_params) -> dict:
    """Legacy entry point used by the /backtest endpoint."""
    spec = _legacy_spec(ticker, strategy, start_date, end_date, initial_cash, fees, **strategy_params)
    return run_backtest_spec(spec)
