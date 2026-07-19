"""Schema validation tests: everything that reaches the engine must be executable."""
import pytest
from pydantic import ValidationError

from backend.schema import AgentResponse, Condition, Indicator, Operand, StrategySpec


def sma_cross_spec(**overrides):
    spec = {
        "ticker": "AAPL",
        "indicators": [
            {"id": "sma50", "type": "SMA", "window": 50},
            {"id": "sma200", "type": "SMA", "window": 200},
        ],
        "entry": {
            "op": "cross_above",
            "left": {"kind": "indicator", "indicator_id": "sma50", "output": "ma"},
            "right": {"kind": "indicator", "indicator_id": "sma200", "output": "ma"},
        },
        "exit": {
            "op": "cross_below",
            "left": {"kind": "indicator", "indicator_id": "sma50", "output": "ma"},
            "right": {"kind": "indicator", "indicator_id": "sma200", "output": "ma"},
        },
    }
    spec.update(overrides)
    return spec


def test_valid_spec_parses_with_defaults():
    spec = StrategySpec.model_validate(sma_cross_spec())
    assert spec.ticker == "AAPL"
    assert spec.start_date == "2015-01-01"
    assert spec.initial_cash == 100_000
    assert spec.fees == 0.001


def test_compound_condition_parses():
    spec = sma_cross_spec(
        indicators=[
            {"id": "rsi14", "type": "RSI", "window": 14},
            {"id": "sma200", "type": "SMA", "window": 200},
        ],
        entry={
            "op": "and",
            "conditions": [
                {
                    "op": "lt",
                    "left": {"kind": "indicator", "indicator_id": "rsi14"},
                    "right": {"kind": "constant", "value": 30},
                },
                {
                    "op": "gt",
                    "left": {"kind": "price", "column": "Close"},
                    "right": {"kind": "indicator", "indicator_id": "sma200"},
                },
            ],
        },
        exit=None,
    )
    parsed = StrategySpec.model_validate(spec)
    assert parsed.entry.op == "and"
    assert len(parsed.entry.conditions) == 2


def test_undeclared_indicator_reference_rejected():
    spec = sma_cross_spec()
    spec["entry"]["left"]["indicator_id"] = "ema20"  # never declared
    with pytest.raises(ValidationError, match="undeclared indicator"):
        StrategySpec.model_validate(spec)


def test_invalid_output_for_indicator_type_rejected():
    spec = sma_cross_spec()
    spec["entry"]["left"]["output"] = "rsi"  # SMA has no 'rsi' output
    with pytest.raises(ValidationError, match="has no output"):
        StrategySpec.model_validate(spec)


def test_duplicate_indicator_ids_rejected():
    spec = sma_cross_spec()
    spec["indicators"][1]["id"] = "sma50"
    with pytest.raises(ValidationError, match="unique"):
        StrategySpec.model_validate(spec)


def test_comparison_requires_both_operands():
    with pytest.raises(ValidationError, match="requires left and right"):
        Condition.model_validate({"op": "gt", "left": {"kind": "constant", "value": 1}})


def test_logical_op_arity():
    leaf = {
        "op": "gt",
        "left": {"kind": "price", "column": "Close"},
        "right": {"kind": "constant", "value": 100},
    }
    with pytest.raises(ValidationError, match="at least two"):
        Condition.model_validate({"op": "and", "conditions": [leaf]})
    with pytest.raises(ValidationError, match="exactly one"):
        Condition.model_validate({"op": "not", "conditions": [leaf, leaf]})


def test_operand_kind_field_requirements():
    with pytest.raises(ValidationError):
        Operand.model_validate({"kind": "indicator"})  # missing indicator_id
    with pytest.raises(ValidationError):
        Operand.model_validate({"kind": "constant"})  # missing value


def test_agent_response_clarification_turn():
    parsed = AgentResponse.model_validate_json(
        '{"message": "Which ticker would you like to trade?", "strategy": null}'
    )
    assert parsed.strategy is None
    assert "ticker" in parsed.message
