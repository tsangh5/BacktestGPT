import numpy as np
import json
import os
import re
import ast
from dotenv import load_dotenv
from google import genai
from google.genai import types
from backend.backtest_loop import run_backtest

load_dotenv()

# Load registries
print("Loading registries...")
with open('backend/tickers.json') as f:
    tickers_registry = json.load(f)['tickers']
print("Tickers loaded:", list(tickers_registry.keys()))
with open('backend/indicators.json') as f:
    indicators_registry = json.load(f)['indicators']
print("Indicators loaded:", list(indicators_registry.keys()))
with open('backend/operators.json') as f:
    operators_registry = json.load(f)['operators']
print("Operators loaded:", {k: v for k, v in operators_registry.items()})
with open('backend/basic_strategies.json') as f:
    strategies_registry = json.load(f)['strategies']
print("Strategies loaded:", list(strategies_registry.keys()))

def match_registry(item, registry):
    """
    Use Gemini to decide if the item matches any entry in the registry.
    Returns the best match (key, value) or (None, None) if not found.
    """
    print(f"Matching '{item}' against registry (semantic): {list(registry.keys())}")
    client = genai.Client()
    # Build registry description for Gemini prompt
    registry_descriptions = []
    for key, value in registry.items():
        if isinstance(value, dict):
            desc = value.get('description', str(value))
        else:
            desc = str(value)
        registry_descriptions.append(f"{key}: {desc}")
    prompt = (
        f"Given the following registry entries with their descriptions:\n"
        f"{chr(10).join(registry_descriptions)}\n"
        f"Does '{item}' match any of them based on meaning or description? If so, return ONLY the best matching key (exact key string). If none match, return 'None'."
    )
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    print(f"Gemini match_registry response for '{item}':", response.text)
    key_candidate = response.text.strip()
    if key_candidate in registry:
        print(f"Matched '{item}' to '{key_candidate}'")
        return key_candidate, registry[key_candidate]
    print(f"No match for '{item}'")
    return None, None

def generate_conversational_response(user_input, parsing_error_details="", conversation_history=None):
    """
    Use Gemini to generate a conversational response asking for missing information
    or confirming strategy details before running the backtest.
    """
    client = genai.Client()
    
    # Build conversation context
    context = ""
    if conversation_history:
        context = "Previous conversation:\n"
        for msg in conversation_history[-3:]:  # Keep last 3 messages for context
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            context += f"{role.capitalize()}: {content}\n"
        context += "\n"
    
    prompt = f"""
    {context}You are a helpful trading strategy assistant. A user is trying to describe a trading strategy for backtesting.

    Current user input: "{user_input}"
    Technical parsing issue: {parsing_error_details}

    Your task is to have a natural conversation to gather the missing information needed for backtesting. 

    If information is missing, ask ONE specific follow-up question about the most critical missing piece:
    1. If no ticker is clear: Ask which stock/asset they want to trade
    2. If no indicators mentioned: Ask what technical indicators they want to use  
    3. If entry conditions unclear: Ask when exactly they want to buy
    4. If exit conditions unclear: Ask when exactly they want to sell

    Keep responses conversational, friendly, and focused on getting ONE piece of missing info at a time.
    Don't overwhelm with multiple questions or long explanations.

    Examples of good responses:
    - "Which stock would you like to backtest this strategy on? For example: AAPL, GOOGL, or SPY?"
    - "What technical indicator should trigger the buy signal? Something like RSI, moving averages, or MACD?"
    - "When exactly would you want to sell? For example, when RSI goes above 70, or after a certain profit/loss?"

    Return ONLY your conversational response - no formatting, quotes, or JSON.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        return "I'd be happy to help you set up a backtest! What stock would you like to analyze, and what trading signals are you interested in?"

def decode_natural_language(user_input, conversation_history=None):
    def sanitize_for_json(obj):
        if isinstance(obj, float):
            if np.isnan(obj) or np.isinf(obj):
                return 0.0
            return obj
        if isinstance(obj, dict):
            return {k: sanitize_for_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sanitize_for_json(v) for v in obj]
        return obj

    """
    Use Gemini to extract entities and fuzzy match them to registries.
    """
    print(f"Decoding user input: {user_input}")
    client = genai.Client()
    prompt = f"""
    You are an expert trading strategy translator. Your task is to parse natural language trading strategies and convert them to structured JSON.

    CRITICAL RULES:
    1. Return ONLY valid JSON - no explanations or extra text
    2. Pay special attention to specific numbers mentioned (like SMA 50, SMA 200, RSI 30, etc.)
    3. Extract the exact periods/windows from the user's text
    4. Use this EXACT schema:

    {{
      "ticker": "string (default: SPY if not specified)",
      "strategy": {{
        "indicators": [
          {{
            "id": "descriptive_name (e.g., SMA50, SMA200, RSI14)",
            "type": "SMA|RSI|BB|EMA|MACD",
            "params": {{
              "window": number_from_user_input,
              "column": "Close"
            }}
          }}
        ],
        "entry": {{
          "op": "cross_above|cross_below|greater_than|less_than",
          "args": ["first_reference", "second_reference"]
        }},
        "exit": {{
          "op": "cross_above|cross_below|greater_than|less_than", 
          "args": ["first_reference", "second_reference"]
        }}
      }}
    }}

    IMPORTANT EXTRACTION RULES:
    - If user says "SMA 50" or "50-day SMA", set window: 50 and id: "SMA50"
    - If user says "SMA 200" or "200-day SMA", set window: 200 and id: "SMA200"
    - If user says "RSI 14" or "14-period RSI", set window: 14 and id: "RSI14"
    - For cross signals, args should reference the indicator outputs like ["SMA50.ma", "SMA200.ma"]
    - For threshold signals (RSI), args should be like ["RSI14.rsi", "30"] or ["RSI14.rsi", "70"]

    COMMON PATTERNS:
    - "SMA crossover" usually means short SMA crosses above long SMA
    - "Golden cross" = SMA50 crosses above SMA200  
    - "Death cross" = SMA50 crosses below SMA200
    - "RSI oversold" usually means RSI < 30
    - "RSI overbought" usually means RSI > 70

    Parse this request: {user_input}
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    print("Gemini entity extraction response:", response.text)
    
    entities = {"ticker": None, "strategy": None, "indicators": [], "operators": []}
    try:
        # Try to extract JSON from response
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if match:
            entities = json.loads(match.group(0))
            print("Extracted entities:", entities)
        else:
            # If no JSON found, try the whole response
            entities = json.loads(response.text.strip())
            print("Extracted entities (full response):", entities)
    except Exception as e:
        print("JSON extraction failed:", e)
        try:
            entities = ast.literal_eval(response.text)
            print("Extracted entities (ast):", entities)
        except Exception as e2:
            print("AST extraction failed:", e2)
            response_msg = generate_conversational_response(user_input, f"JSON/AST parsing failed: {str(e)}, {str(e2)}", conversation_history)
            return {"conversation": True, "message": response_msg, "needs_clarification": True}

    # Fuzzy match ticker to registry
    ticker_key, ticker_val = (None, None)
    if entities.get("ticker"):
        ticker_key, ticker_val = match_registry(entities["ticker"], tickers_registry)
        print(f"Ticker match: {ticker_key}")
    
    if not ticker_key:
        ticker_key = "SPY"  # Default ticker
        print("Using default ticker: SPY")

    # Check if this matches a basic strategy pattern
    strategy_key, strategy_val = (None, None)
    if entities.get("strategy"):
        strategy_key, strategy_val = match_registry(str(entities.get("strategy", "")), strategies_registry)
        print(f"Strategy match: {strategy_key}")

    # Extract indicators and create custom config
    indicators = entities.get("strategy", {}).get("indicators", [])
    custom_indicators = []
    
    for ind in indicators:
        print(f"[DEBUG] Processing parsed indicator: {ind}")
        
        # Validate indicator structure
        if not isinstance(ind, dict):
            continue
            
        ind_type = ind.get('type', '').upper()
        ind_id = ind.get('id', '')
        params = ind.get('params', {})
        
        # Ensure we have required fields
        if not ind_type or not params.get('window'):
            print(f"[DEBUG] Skipping indicator due to missing type or window: {ind}")
            continue
            
        # Match to registry
        registry_key, registry_val = match_registry(ind_type, indicators_registry)
        if registry_key:
            custom_indicators.append({
                "id": ind_id,
                "type": ind_type,
                "params": params
            })
            print(f"[DEBUG] Added indicator: {ind_id} ({ind_type}) with params: {params}")

    if not custom_indicators:
        print("No valid indicators found")
        response_msg = generate_conversational_response(user_input, "No valid technical indicators could be identified", conversation_history)
        return {"conversation": True, "message": response_msg, "needs_clarification": True}

    # Extract entry/exit rules
    entry_rule = entities.get("strategy", {}).get("entry", {})
    exit_rule = entities.get("strategy", {}).get("exit", {})
    
    print(f"[DEBUG] Entry rule extracted: {entry_rule}")
    print(f"[DEBUG] Exit rule extracted: {exit_rule}")

    # Validate that we have meaningful entry/exit conditions
    if not entry_rule or not entry_rule.get("op") or not entry_rule.get("args"):
        print("Missing or invalid entry rule")
        response_msg = generate_conversational_response(user_input, "No clear entry conditions specified", conversation_history)
        return {"conversation": True, "message": response_msg, "needs_clarification": True}
    
    if not exit_rule or not exit_rule.get("op") or not exit_rule.get("args"):
        print("Missing or invalid exit rule")
        response_msg = generate_conversational_response(user_input, "No clear exit conditions specified", conversation_history)
        return {"conversation": True, "message": response_msg, "needs_clarification": True}

    # Build final strategy config
    strategy_config = {
        "description": f"Custom strategy from: {user_input}",
        "indicators": custom_indicators,
        "entry": entry_rule,
        "exit": exit_rule
    }

    print(f"[DEBUG] Final strategy config: {strategy_config}")

    # Run backtest
    result = run_backtest(
        ticker=ticker_key,
        strategy="CUSTOM",
        strategy_config=strategy_config
    )
    
    return sanitize_for_json(result)

# Example usage
if __name__ == "__main__":
    user_input = input("Describe your backtest: ")
    result = decode_natural_language(user_input)
    print(json.dumps(result, indent=2))