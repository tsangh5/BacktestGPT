"""Typed strategy specification.

The LLM emits JSON conforming to AgentResponse (enforced server-side by
Gemini's constrained decoding against this schema). Pydantic then validates
semantics — operand kinds, logical-operator arity, and that every indicator
reference points at a declared indicator with a valid output — so anything
that reaches the backtest engine is guaranteed executable.
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

PriceColumn = Literal["Close", "Open", "High", "Low", "Volume"]

COMPARISON_OPS = ("gt", "lt", "gte", "lte", "cross_above", "cross_below")
LOGICAL_OPS = ("and", "or", "not")

# Outputs each indicator type produces; the first entry is the default when
# an operand omits `output`.
INDICATOR_OUTPUTS = {
    "SMA": ("ma",),
    "EMA": ("ma",),
    "RSI": ("rsi",),
    "BB": ("middle", "upper", "lower"),
    "MACD": ("macd", "signal", "hist"),
}


TRANSFORMS = ("pct_change", "shift", "rolling_max", "rolling_min", "rolling_mean", "rolling_std", "abs")
ROLLING_TRANSFORMS = ("rolling_max", "rolling_min", "rolling_mean", "rolling_std")
MATH_OPS = ("add", "sub", "mul", "div")


class Operand(BaseModel):
    """A value expression: an indicator output, a price column, a number, a
    transform of another expression, or arithmetic between two expressions.
    Recursive, so derived series like "2% below the 52-week high" are
    expressible: mul(rolling_max(Close, 252), 0.98)."""

    kind: Literal["indicator", "price", "constant", "transform", "math"]
    indicator_id: Optional[str] = Field(
        None, description="id of a declared indicator (kind=indicator)"
    )
    output: Optional[str] = Field(
        None,
        description="indicator output: ma | rsi | middle | upper | lower | macd | signal | hist",
    )
    column: Optional[PriceColumn] = Field(None, description="price column (kind=price)")
    value: Optional[float] = Field(None, description="numeric constant (kind=constant)")
    transform: Optional[Literal[
        "pct_change", "shift", "rolling_max", "rolling_min", "rolling_mean", "rolling_std", "abs"
    ]] = Field(None, description="transform to apply to `operand` (kind=transform)")
    operand: Optional["Operand"] = Field(
        None, description="input expression for a transform (kind=transform)"
    )
    periods: Optional[int] = Field(
        None, ge=1, description="lookback for pct_change/shift (default 1)"
    )
    window: Optional[int] = Field(None, ge=1, description="window for rolling_* transforms")
    op: Optional[Literal["add", "sub", "mul", "div"]] = Field(
        None, description="arithmetic operator (kind=math)"
    )
    left: Optional["Operand"] = Field(None, description="left expression (kind=math)")
    right: Optional["Operand"] = Field(None, description="right expression (kind=math)")

    @model_validator(mode="after")
    def _check_kind_fields(self) -> "Operand":
        if self.kind == "indicator" and not self.indicator_id:
            raise ValueError("operand of kind 'indicator' requires indicator_id")
        if self.kind == "price" and not self.column:
            raise ValueError("operand of kind 'price' requires column")
        if self.kind == "constant" and self.value is None:
            raise ValueError("operand of kind 'constant' requires value")
        if self.kind == "transform":
            if not self.transform or self.operand is None:
                raise ValueError("operand of kind 'transform' requires transform and operand")
            if self.transform in ROLLING_TRANSFORMS and not self.window:
                raise ValueError(f"transform '{self.transform}' requires window")
        if self.kind == "math":
            if not self.op or self.left is None or self.right is None:
                raise ValueError("operand of kind 'math' requires op, left, and right")
        return self


class Condition(BaseModel):
    """A signal rule: either a comparison of two operands, or a logical
    combination of sub-conditions (arbitrarily nested)."""

    op: Literal["gt", "lt", "gte", "lte", "cross_above", "cross_below", "and", "or", "not"]
    left: Optional[Operand] = None
    right: Optional[Operand] = None
    conditions: Optional[List["Condition"]] = Field(
        None, description="sub-conditions for and/or/not"
    )

    @model_validator(mode="after")
    def _check_arity(self) -> "Condition":
        if self.op in COMPARISON_OPS:
            if self.left is None or self.right is None:
                raise ValueError(f"comparison '{self.op}' requires left and right operands")
        elif self.op == "not":
            if not self.conditions or len(self.conditions) != 1:
                raise ValueError("'not' requires exactly one sub-condition")
        else:  # and / or
            if not self.conditions or len(self.conditions) < 2:
                raise ValueError(f"'{self.op}' requires at least two sub-conditions")
        return self


class Indicator(BaseModel):
    id: str = Field(description="unique reference name, e.g. 'sma50', 'rsi14'")
    type: Literal["SMA", "EMA", "RSI", "BB", "MACD"]
    window: Optional[int] = Field(
        None, ge=1, description="lookback window (SMA/EMA/RSI/BB); defaults per type"
    )
    std: Optional[float] = Field(None, gt=0, description="std-dev multiplier (BB only, default 2)")
    fast_window: Optional[int] = Field(None, ge=1, description="MACD fast EMA window (default 12)")
    slow_window: Optional[int] = Field(None, ge=1, description="MACD slow EMA window (default 26)")
    signal_window: Optional[int] = Field(None, ge=1, description="MACD signal window (default 9)")
    column: PriceColumn = "Close"


class StrategySpec(BaseModel):
    ticker: str = Field(description="stock ticker symbol, e.g. 'AAPL'")
    start_date: str = Field("2015-01-01", description="backtest start, YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="backtest end, YYYY-MM-DD (default: today)")
    initial_cash: float = Field(100_000, gt=0)
    fees: float = Field(0.001, ge=0, description="per-trade fees as a fraction, e.g. 0.001 = 0.1%")
    stop_loss: Optional[float] = Field(
        None, gt=0, lt=1, description="stop-loss as a fraction, e.g. 0.05 = 5%"
    )
    take_profit: Optional[float] = Field(
        None, gt=0, description="take-profit as a fraction, e.g. 0.1 = 10%"
    )
    indicators: List[Indicator] = Field(default_factory=list)
    entry: Condition
    exit: Optional[Condition] = Field(
        None, description="omit to hold until end of period (or until a stop triggers)"
    )

    @model_validator(mode="after")
    def _check_references(self) -> "StrategySpec":
        ids = [ind.id for ind in self.indicators]
        if len(ids) != len(set(ids)):
            raise ValueError("indicator ids must be unique")
        by_id = {ind.id: ind for ind in self.indicators}

        def check_operand(operand: Optional[Operand]) -> None:
            if operand is None:
                return
            if operand.kind == "indicator":
                ind = by_id.get(operand.indicator_id)
                if ind is None:
                    raise ValueError(
                        f"condition references undeclared indicator '{operand.indicator_id}'"
                    )
                valid_outputs = INDICATOR_OUTPUTS[ind.type]
                if operand.output is not None and operand.output not in valid_outputs:
                    raise ValueError(
                        f"indicator '{ind.id}' ({ind.type}) has no output "
                        f"'{operand.output}'; valid outputs: {', '.join(valid_outputs)}"
                    )
            check_operand(operand.operand)
            check_operand(operand.left)
            check_operand(operand.right)

        def check_condition(cond: Condition) -> None:
            check_operand(cond.left)
            check_operand(cond.right)
            for sub in cond.conditions or []:
                check_condition(sub)

        check_condition(self.entry)
        if self.exit is not None:
            check_condition(self.exit)
        return self


class AgentResponse(BaseModel):
    """What the LLM returns each turn: a chat message, plus a complete
    strategy spec once (and only once) enough information has been gathered."""

    message: str = Field(
        description="conversational reply: a clarifying question, or a short "
        "confirmation of the strategy about to be backtested"
    )
    strategy: Optional[StrategySpec] = Field(
        None, description="null until the strategy is fully specified"
    )
