import numpy as np
import json
import os
import re
import ast
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from backend.backtest_loop import run_backtest
import yfinance as yf

def is_valid_ticker_format(ticker):
    """Basic validation for ticker format"""
    if not ticker or not isinstance(ticker, str):
        return False
    
    ticker = ticker.strip().upper()
    
    # Basic format checks for common ticker formats
    if len(ticker) < 1 or len(ticker) > 10:
        return False
    
    # Allow alphanumeric characters, dots, and hyphens (common in ticker symbols)
    if not re.match(r'^[A-Z0-9.-]+$', ticker):
        return False
    
    return True

# Ticker validation cache to avoid repeated yfinance calls
_ticker_validation_cache = {}

def validate_ticker_exists(ticker):
    """
    Validate if a ticker symbol exists and has data available using yfinance.
    Uses caching to avoid repeated API calls for the same ticker.
    Returns (is_valid, error_message)
    """
    if not ticker or not isinstance(ticker, str):
        return False, "Invalid ticker format"
    
    ticker = ticker.strip().upper()
    
    # Basic format check first
    if not is_valid_ticker_format(ticker):
        return False, f"Ticker '{ticker}' has invalid format"
    
    # Check cache first
    if ticker in _ticker_validation_cache:
        cached_result = _ticker_validation_cache[ticker]
        return cached_result['is_valid'], cached_result['message']
    
    try:
        # Try to fetch recent data to validate ticker exists
        stock = yf.Ticker(ticker)
        # Get last 5 days of data to check if ticker is valid
        hist = stock.history(period="5d")
        
        if hist.empty:
            result = (False, f"No data available for ticker '{ticker}'")
        else:
            result = (True, f"Ticker '{ticker}' is valid and has data")
        
        # Cache the result
        _ticker_validation_cache[ticker] = {
            'is_valid': result[0],
            'message': result[1]
        }
        
        return result
    
    except Exception as e:
        result = (False, f"Error validating ticker '{ticker}': {str(e)}")
        
        # Cache the error result too (to avoid repeated failed calls)
        _ticker_validation_cache[ticker] = {
            'is_valid': result[0],
            'message': result[1]
        }
        
        return result

def get_alternative_ticker_from_gemini(user_input, invalid_ticker, client):
    """Ask Gemini to find an alternative ticker from the user input"""
    
    alternative_prompt = f"""
    The user input was: "{user_input}"
    
    You previously extracted the ticker "{invalid_ticker}" but this ticker is not valid or doesn't exist.
    
    Please analyze the user input again and:
    1. If there's a company name mentioned, provide the correct stock ticker symbol
    2. If the ticker was misspelled, provide the correct spelling
    3. If no specific company/ticker is mentioned, return "SPY" as default
    
    Common company name to ticker mappings:
    - Apple -> AAPL
    - Microsoft -> MSFT  
    - Google/Alphabet -> GOOGL
    - Amazon -> AMZN
    - Tesla -> TSLA
    - Meta/Facebook -> META
    - Netflix -> NFLX
    - NVIDIA -> NVDA
    - Berkshire Hathaway -> BRK.B
    
    Return ONLY the ticker symbol (e.g., "AAPL"), nothing else.
    """
    
    result = safe_gemini_call(client, alternative_prompt, context="ticker correction")
    
    if not result["success"]:
        print(f"Error getting alternative ticker: {result['error']}")
        return "SPY"  # Default fallback
    
    alternative_ticker = result["response"].strip().strip('"').upper()
    
    # Validate the alternative ticker
    is_valid, message = validate_ticker_exists(alternative_ticker)
    if is_valid:
        print(f"Found valid alternative ticker: {alternative_ticker}")
        return alternative_ticker
    else:
        print(f"Alternative ticker {alternative_ticker} is also invalid: {message}")
        return "SPY"  # Default fallback

def validate_strategy_compatibility(strategy_data, indicators_registry, operators_registry, strategies_registry, client=None):
    """
    Check if a strategy uses supported indicators, operators, and patterns.
    Also validates ticker availability.
    Returns (is_compatible, feedback_message, updated_strategy_data)
    """
    issues = []
    suggestions = []
    updated_strategy = strategy_data.copy()  # Make a copy to potentially update ticker
    
    # Validate ticker if present
    ticker = strategy_data.get('ticker')
    if ticker:
        is_valid_ticker, ticker_message = validate_ticker_exists(ticker)
        if not is_valid_ticker:
            print(f"Ticker validation failed: {ticker_message}")
            if client:
                # Try to get alternative ticker from Gemini if client is available
                alternative_ticker = get_alternative_ticker_from_gemini("", ticker, client)
                print(f"Trying alternative ticker: {alternative_ticker}")
                
                is_valid_alt, alt_message = validate_ticker_exists(alternative_ticker)
                if is_valid_alt:
                    print(f"Alternative ticker {alternative_ticker} is valid: {alt_message}")
                    updated_strategy['ticker'] = alternative_ticker
                    suggestions.append(f"Changed ticker from '{ticker}' to '{alternative_ticker}' (original ticker was not available)")
                else:
                    issues.append(f"Ticker '{ticker}' is not valid or has no data available")
                    issues.append(f"Alternative ticker '{alternative_ticker}' is also invalid")
            else:
                issues.append(f"Ticker '{ticker}' is not valid or has no data available")
        else:
            print(f"Ticker validation successful: {ticker_message}")
    
    # Check if it matches a basic strategy pattern
    if 'indicators' in strategy_data and 'entry' in strategy_data and 'exit' in strategy_data:
        
        # Validate indicators
        for indicator in strategy_data.get('indicators', []):
            indicator_type = indicator.get('type', '').upper()
            if indicator_type not in indicators_registry:
                issues.append(f"Indicator '{indicator_type}' is not supported")
                # Suggest similar indicators
                similar = [name for name in indicators_registry.keys() 
                          if name.lower() in indicator_type.lower() or indicator_type.lower() in name.lower()]
                if similar:
                    suggestions.append(f"Try using {', '.join(similar)} instead of {indicator_type}")
        
        # Validate operators in conditions
        def check_operators_in_condition(condition, path=""):
            if isinstance(condition, dict):
                op = condition.get('op', '')
                if op:
                    # Check if operator exists in any category
                    op_found = False
                    for category, ops in operators_registry.items():
                        if op in ops:
                            op_found = True
                            break
                    if not op_found:
                        issues.append(f"Operator '{op}' is not supported{path}")
                        # Suggest similar operators
                        all_ops = []
                        for ops in operators_registry.values():
                            all_ops.extend(ops)
                        similar_ops = [o for o in all_ops if o in op or op in o]
                        if similar_ops:
                            suggestions.append(f"Try using {', '.join(similar_ops)} instead of {op}")
                
                # Recursively check nested conditions
                for key, value in condition.items():
                    if key == 'args' and isinstance(value, list):
                        for i, arg in enumerate(value):
                            check_operators_in_condition(arg, f"{path} (arg {i+1})")
                    elif isinstance(value, dict):
                        check_operators_in_condition(value, f"{path}.{key}")
            elif isinstance(condition, list):
                for i, item in enumerate(condition):
                    check_operators_in_condition(item, f"{path}[{i}]")
        
        # Check entry and exit conditions
        if 'entry' in strategy_data:
            check_operators_in_condition(strategy_data['entry'], " in entry condition")
        if 'exit' in strategy_data:
            check_operators_in_condition(strategy_data['exit'], " in exit condition")
    
    # Check if it matches any basic strategy pattern
    strategy_matches = []
    for strategy_name, strategy_info in strategies_registry.items():
        # Simple pattern matching based on indicators used
        strategy_indicators = [ind.get('type') for ind in strategy_info.get('indicators', [])]
        user_indicators = [ind.get('type') for ind in strategy_data.get('indicators', [])]
        
        if set(strategy_indicators).intersection(set(user_indicators)):
            strategy_matches.append((strategy_name, strategy_info['description']))
    
    # Prepare feedback message
    if issues:
        feedback = "I understand your strategy, but there are some compatibility issues:\n\n"
        for issue in issues:
            feedback += f"❌ {issue}\n"
        
        if suggestions:
            feedback += "\n💡 **Suggestions:**\n"
            for suggestion in suggestions:
                feedback += f"• {suggestion}\n"
        
        feedback += f"\n📋 **Available indicators:** {', '.join(indicators_registry.keys())}\n"
        
        all_operators = []
        for category, ops in operators_registry.items():
            all_operators.extend([f"{op} ({category})" for op in ops])
        feedback += f"🔧 **Available operators:** {', '.join(all_operators[:10])}{'...' if len(all_operators) > 10 else ''}\n"
        
        if strategy_matches:
            feedback += f"\n🎯 **Similar strategies you could try:**\n"
            for name, desc in strategy_matches[:3]:  # Show top 3 matches
                feedback += f"• **{name}**: {desc}\n"
        else:
            # If no matches, suggest some popular strategies
            feedback += f"\n🎯 **Popular strategies you could try instead:**\n"
            popular_strategies = list(strategies_registry.items())[:3]
            for name, info in popular_strategies:
                feedback += f"• **{name}**: {info['description']}\n"
        
        feedback += f"\n💬 Try rephrasing your strategy using the supported components above!"
        
        return False, feedback, updated_strategy
    
    # If no issues, strategy is compatible
    success_message = "Your strategy looks compatible with our system! 🎉"
    if suggestions:
        success_message += "\n\n" + "\n".join(f"✅ {s}" for s in suggestions)
    return True, success_message, updated_strategy

load_dotenv()

# Conversation state storage (in production, this should be a database)
conversation_states = {}

class ConversationState:
    """Manages the accumulated strategy information across conversation turns"""
    
    def __init__(self, conversation_id=None):
        self.conversation_id = conversation_id or "default"
        self.ticker = None
        self.indicators = []
        self.entry_conditions = {}
        self.exit_conditions = {}
        self.strategy_complete = False
        self.last_updated = time.time()
    
    def update_from_input(self, user_input, extracted_entities):
        """Update conversation state with new information from user input"""
        updated_fields = []
        
        # Update ticker if specified (accept any valid ticker symbol)
        if extracted_entities.get("ticker") and extracted_entities["ticker"] != "SPY":
            new_ticker = extracted_entities["ticker"].upper()  # Normalize to uppercase
            if is_valid_ticker_format(new_ticker) and self.ticker != new_ticker:
                # Validate ticker exists with actual data
                is_valid_ticker, ticker_message = validate_ticker_exists(new_ticker)
                if is_valid_ticker:
                    self.ticker = new_ticker
                    updated_fields.append("ticker")
                    print(f"✅ Ticker validation successful: {ticker_message}")
                else:
                    print(f"❌ Ticker validation failed: {ticker_message}")
                    # Try to get alternative ticker from Gemini
                    # Note: We'd need access to the Gemini client here, but for now let's use a simple mapping
                    company_to_ticker = {
                        "APPLE": "AAPL",
                        "MICROSOFT": "MSFT", 
                        "GOOGLE": "GOOGL",
                        "AMAZON": "AMZN",
                        "TESLA": "TSLA",
                        "META": "META",
                        "NETFLIX": "NFLX",
                        "NVIDIA": "NVDA"
                    }
                    
                    alternative_ticker = company_to_ticker.get(new_ticker, "SPY")
                    is_valid_alt, alt_message = validate_ticker_exists(alternative_ticker)
                    if is_valid_alt:
                        print(f"✅ Using alternative ticker: {alternative_ticker}")
                        self.ticker = alternative_ticker
                        updated_fields.append("ticker")
                    else:
                        print(f"❌ Alternative ticker {alternative_ticker} also invalid, defaulting to SPY")
                        self.ticker = "SPY"
                        updated_fields.append("ticker")
        
        # Update indicators
        new_indicators = extracted_entities.get("strategy", {}).get("indicators", [])
        for new_ind in new_indicators:
            # Check if this exact indicator (by id) is already in our list
            existing = next((ind for ind in self.indicators if ind.get("id") == new_ind.get("id")), None)
            if not existing:
                self.indicators.append(new_ind)
                updated_fields.append(f"indicator_{new_ind.get('type')}")
            elif existing.get("params") != new_ind.get("params"):
                # Update existing indicator parameters
                existing.update(new_ind)
                updated_fields.append(f"indicator_{new_ind.get('type')}_params")
        
        # Update entry conditions
        new_entry = extracted_entities.get("strategy", {}).get("entry", {})
        if new_entry and self._is_meaningful_rule(new_entry):
            if self.entry_conditions != new_entry:
                self.entry_conditions = new_entry
                updated_fields.append("entry_conditions")
        
        # Update exit conditions  
        new_exit = extracted_entities.get("strategy", {}).get("exit", {})
        if new_exit and self._is_meaningful_rule(new_exit):
            if self.exit_conditions != new_exit:
                self.exit_conditions = new_exit
                updated_fields.append("exit_conditions")
        
        self.last_updated = time.time()
        return updated_fields
    
    def _is_meaningful_rule(self, rule):
        """Check if a rule has meaningful arguments (not default/meaningless values)"""
        args = rule.get("args", [])
        if not args or len(args) < 2:
            return False
        
        meaningless_values = ["0", 0, "Close", "Open", "High", "Low"]
        
        # If both args are basic price columns or zeros, it's meaningless
        if args[0] in meaningless_values and args[1] in meaningless_values:
            return False
            
        # If we're comparing price to zero, it's meaningless
        if (args[0] in ["Close", "Open", "High", "Low"] and args[1] in ["0", 0]) or \
           (args[1] in ["Close", "Open", "High", "Low"] and args[0] in ["0", 0]):
            return False
            
        return True
    
    def is_complete(self):
        """Check if we have enough information to run a backtest"""
        has_indicators = len(self.indicators) > 0
        has_meaningful_entry = bool(self.entry_conditions and self._is_meaningful_rule(self.entry_conditions))
        has_meaningful_exit = bool(self.exit_conditions and self._is_meaningful_rule(self.exit_conditions))
        
        self.strategy_complete = has_indicators and has_meaningful_entry and has_meaningful_exit
        return self.strategy_complete
    
    def get_missing_components(self):
        """Return list of missing strategy components"""
        missing = []
        
        if not self.ticker:
            missing.append("ticker")
        if not self.indicators:
            missing.append("indicators")
        if not self.entry_conditions or not self._is_meaningful_rule(self.entry_conditions):
            missing.append("entry_conditions")
        if not self.exit_conditions or not self._is_meaningful_rule(self.exit_conditions):
            missing.append("exit_conditions")
            
        return missing
    
    def to_strategy_config(self):
        """Convert conversation state to strategy config for backtesting"""
        if not self.is_complete():
            return None
            
        return {
            "ticker": self.ticker or "SPY",
            "strategy_config": {
                "description": "Strategy built through conversation",
                "indicators": self.indicators,
                "entry": self.entry_conditions,
                "exit": self.exit_conditions
            }
        }
    
    def get_summary(self):
        """Get a summary of current conversation state"""
        summary = []
        
        if self.ticker:
            summary.append(f"Ticker: {self.ticker}")
        
        if self.indicators:
            ind_names = [f"{ind.get('type', 'Unknown')}({ind.get('params', {}).get('window', 'N/A')})" for ind in self.indicators]
            summary.append(f"Indicators: {', '.join(ind_names)}")
        
        if self.entry_conditions and self._is_meaningful_rule(self.entry_conditions):
            summary.append(f"Entry: {self.entry_conditions.get('op', 'N/A')} with {self.entry_conditions.get('args', [])}")
        
        if self.exit_conditions and self._is_meaningful_rule(self.exit_conditions):
            summary.append(f"Exit: {self.exit_conditions.get('op', 'N/A')} with {self.exit_conditions.get('args', [])}")
        
        return " | ".join(summary) if summary else "No strategy components defined yet"

def get_conversation_state(conversation_history):
    """Get or create conversation state based on conversation history"""
    # Use first few messages as conversation ID (simple approach)
    # In production, use proper session/user management
    conversation_id = "conv_" + str(hash(str(conversation_history[:2])))
    
    if conversation_id not in conversation_states:
        conversation_states[conversation_id] = ConversationState(conversation_id)
    
    return conversation_states[conversation_id]

# Registry cache to avoid loading on every import
_registries_cache = None

def get_registries():
    """Load registries with caching to improve performance"""
    global _registries_cache
    
    if _registries_cache is None:
        print("Loading registries...")
        # Note: Ticker registry removed - system now accepts any valid ticker format via is_valid_ticker_format()
        
        with open('backend/indicators.json') as f:
            indicators_registry = json.load(f)['indicators']
        print("Indicators loaded:", list(indicators_registry.keys()))
        
        with open('backend/operators.json') as f:
            operators_registry = json.load(f)['operators']
        print("Operators loaded:", {k: v for k, v in operators_registry.items()})
        
        with open('backend/basic_strategies.json') as f:
            strategies_registry = json.load(f)['strategies']
        print("Strategies loaded:", list(strategies_registry.keys()))
        
        _registries_cache = {
            'indicators': indicators_registry,
            'operators': operators_registry,
            'strategies': strategies_registry
        }
    
    return _registries_cache['indicators'], _registries_cache['operators'], _registries_cache['strategies']

def safe_gemini_call(client, prompt, context="general", max_retries=3, retry_delay=2):
    """
    Safely call Gemini API with proper error handling for 503 overload errors.
    
    Args:
        client: Gemini client instance
        prompt: The prompt to send
        context: Context description for error messages
        max_retries: Maximum number of retries for 503 errors
        retry_delay: Delay between retries in seconds
    
    Returns:
        dict: {"success": bool, "response": str/None, "error": str/None}
    """
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            return {"success": True, "response": response.text, "error": None}
            
        except Exception as e:
            error_msg = str(e).lower()
            print(f"Gemini API error on attempt {attempt + 1}: {e}")
            
            # Check for 503 overload error
            if "503" in error_msg or "overloaded" in error_msg or "service unavailable" in error_msg:
                if attempt < max_retries:
                    print(f"Model overloaded, retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                    continue
                else:
                    return {
                        "success": False, 
                        "response": None,
                        "error": "The AI model is currently overloaded. Please try again in a few moments. This happens during peak usage times."
                    }
            
            # Check for rate limiting
            elif "429" in error_msg or "quota" in error_msg or "rate limit" in error_msg:
                return {
                    "success": False,
                    "response": None, 
                    "error": "We've hit the rate limit for the AI service. Please wait a moment and try again."
                }
            
            # Check for network/connectivity issues
            elif "network" in error_msg or "connection" in error_msg or "timeout" in error_msg:
                return {
                    "success": False,
                    "response": None,
                    "error": "There's a connectivity issue with the AI service. Please check your internet connection and try again."
                }
            
            # Generic error
            else:
                return {
                    "success": False,
                    "response": None,
                    "error": f"The AI service encountered an issue while processing your {context} request. Please try again."
                }
    
    # This shouldn't be reached, but just in case
    return {
        "success": False,
        "response": None,
        "error": "Unable to process your request after multiple attempts. Please try again later."
    }

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
    
    result = safe_gemini_call(client, prompt, context="registry matching")
    
    if not result["success"]:
        print(f"Gemini API error for '{item}': {result['error']}")
        return None, None
    
    print(f"Gemini match_registry response for '{item}':", result["response"])
    key_candidate = result["response"].strip()
    if key_candidate in registry:
        print(f"Matched '{item}' to '{key_candidate}'")
        return key_candidate, registry[key_candidate]
    print(f"No match for '{item}'")
    return None, None

def generate_conversational_response(user_input, parsing_error_details="", conversation_history=None):
    """
    Use Gemini to generate a conversational response asking for missing information
    or confirming strategy details before running the backtest.
    Uses the full conversation efficiently with smart summarization for long conversations.
    """
    client = genai.Client()
    
    # Build conversation context efficiently
    context = ""
    if conversation_history:
        # For conversations longer than 10 messages, use smart summarization
        if len(conversation_history) > 10:
            # Get the first 2 messages (initial context)
            initial_context = conversation_history[:2]
            # Get the last 6 messages (recent context)
            recent_context = conversation_history[-6:]
            
            # Summarize the middle part if it exists
            middle_messages = conversation_history[2:-6] if len(conversation_history) > 8 else []
            
            context = "Conversation summary:\n"
            
            # Add initial context
            for msg in initial_context:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                context += f"{role.capitalize()}: {content}\n"
            
            # Add summary of middle messages if they exist
            if middle_messages:
                context += f"\n[Previous discussion covered: {len(middle_messages)} messages about strategy details]\n\n"
            
            # Add recent context
            context += "Recent conversation:\n"
            for msg in recent_context:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                context += f"{role.capitalize()}: {content}\n"
        else:
            # For shorter conversations, use all messages
            context = "Full conversation:\n"
            for msg in conversation_history:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                context += f"{role.capitalize()}: {content}\n"
        
        context += "\n"
    
    prompt = f"""
    {context}You are a helpful trading strategy assistant. A user is trying to describe a trading strategy for backtesting.

    Current user input: "{user_input}"
    Technical parsing issue: {parsing_error_details}

    Your task is to have a natural conversation to gather the missing information needed for backtesting. 

    Analyze what's missing and ask ONE specific follow-up question about the most critical missing piece:
    
    Context awareness:
    - Look at what's already been established in the conversation
    - Build on existing information rather than repeating questions
    - Focus on the next logical step in building the strategy
    
    Priority order for missing components:
    1. If only ticker mentioned (like "I want to buy AAPL"): Ask about the strategy/indicators
    2. If only indicator mentioned (like "MACD"): Ask about entry/exit conditions
    3. If indicators established but no entry: Ask about buy signals
    4. If indicators and entry established but no exit: Ask about sell signals
    5. If everything present but vague: Ask for more specific values
    
    Keep responses conversational, friendly, and focused on getting ONE piece of missing info at a time.
    Don't overwhelm with multiple questions or long explanations.
    Reference what's already been established to show you're listening.

    Examples of contextual responses:
    - For "I want to buy AAPL": "Great! I've noted you want to trade AAPL. What trading indicators or signals would you like to use for this strategy? For example, moving averages, RSI, MACD, or something else?"
    - For "MACD" after ticker is known: "Perfect! So we'll use MACD for [TICKER]. When would you want to buy and sell? For example, buy when MACD line crosses above the signal line?"
    - When building on existing info: "I have [existing components]. Now I just need to know when to [missing component]. For example..."
    - For refinement: "I have your basic strategy setup. Could you be more specific about [specific parameter]?"

    Return ONLY your conversational response - no formatting, quotes, or JSON.
    """
    
    result = safe_gemini_call(client, prompt, context="conversation")
    
    if not result["success"]:
        # Return a user-friendly error message that can be displayed in the chat
        return f"I'm having trouble connecting to the AI service right now. {result['error']} In the meantime, could you provide more details about your trading strategy?"
    
    return result["response"].strip()

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
    Use Gemini to extract entities and manage conversation state to build complete strategies.
    Now accumulates information across conversation turns until enough to run backtest.
    """
    print(f"Decoding user input: {user_input}")
    
    # Get or create conversation state
    conv_state = get_conversation_state(conversation_history or [])
    print(f"[CONVERSATION STATE] Current: {conv_state.get_summary()}")
    
    client = genai.Client()
    
    # Build conversation context for better understanding
    conversation_context = ""
    if conversation_history:
        # Extract key information from the entire conversation
        conversation_context = "\n\nPrevious conversation context:\n"
        
        # For very long conversations, use smart summarization
        if len(conversation_history) > 15:
            # Get key messages: first 2, last 8, and identify any that mention specific details
            important_messages = []
            
            # Always include the first couple of messages
            important_messages.extend(conversation_history[:2])
            
            # Look for messages with specific technical details in the middle
            middle_messages = conversation_history[2:-8]
            for msg in middle_messages:
                content = msg.get('content', '').lower()
                # Check if message contains important trading terms
                if any(term in content for term in ['sma', 'rsi', 'ema', 'macd', 'buy', 'sell', 'cross', 'above', 'below', 'stock', 'ticker']):
                    important_messages.append(msg)
            
            # Always include recent messages
            important_messages.extend(conversation_history[-8:])
            
            # Remove duplicates while preserving order
            seen = set()
            filtered_messages = []
            for msg in important_messages:
                msg_id = f"{msg.get('role', '')}:{msg.get('content', '')[:50]}"
                if msg_id not in seen:
                    seen.add(msg_id)
                    filtered_messages.append(msg)
            
            for msg in filtered_messages:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                conversation_context += f"{role.capitalize()}: {content}\n"
        else:
            # For shorter conversations, include everything
            for msg in conversation_history:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                conversation_context += f"{role.capitalize()}: {content}\n"
    
    # Add current conversation state to context
    conversation_context += f"\n\nCurrent accumulated strategy state: {conv_state.get_summary()}\n"
    
    prompt = f"""
    You are an expert trading strategy translator. Your task is to parse natural language and extract any new trading strategy information from the current user input.

    CRITICAL RULES:
    1. Return ONLY valid JSON - no explanations or extra text
    2. Extract any new information from the current input that adds to the strategy
    3. Use the conversation context to understand what's already been established
    4. Focus on extracting what's NEW in the current message
    5. Use this EXACT schema:

    {{
      "ticker": "string (only if explicitly mentioned in current input)",
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

    EXTRACTION FOCUS:
    - Extract NEW indicators mentioned in current input
    - Extract NEW entry/exit conditions from current input
    - If current input only mentions one aspect (like just "RSI 14"), only extract that
    - Don't repeat information already established in previous conversation
    - For incomplete information, extract what you can and leave other fields empty

    VALIDATION RULES:
    - Only include indicators if specific parameters are mentioned
    - Only include entry/exit if meaningful conditions are specified
    - Do NOT create placeholder or default conditions
    - If input is just clarification/confirmation, return empty strategy object

    IMPORTANT EXTRACTION RULES:
    - If user says "SMA 50" or "50-day SMA", set window: 50 and id: "SMA50"
    - If user says "SMA 200" or "200-day SMA", set window: 200 and id: "SMA200"
    - If user says "RSI 14" or "14-period RSI", set window: 14 and id: "RSI14"
    - For cross signals, args should reference the indicator outputs like ["SMA50.ma", "SMA200.ma"]
    - For threshold signals (RSI), args should be like ["RSI14.rsi", "30"] or ["RSI14.rsi", "70"]
    - DO NOT use "Close" vs "0" comparisons - these are meaningless

    {conversation_context}

    Current user input to extract NEW information from: {user_input}
    
    Extract only the NEW trading strategy information from this specific input, building on what's already established.
    """

    result = safe_gemini_call(client, prompt, context="strategy parsing")
    
    if not result["success"]:
        # Return a conversational error that will be displayed to the user
        response_msg = f"I'm having trouble processing your request right now. {result['error']} Could you please try rephrasing your trading strategy?"
        return {"conversation": True, "message": response_msg, "needs_clarification": True}
    
    print("Gemini entity extraction response:", result["response"])
    
    entities = {"ticker": None, "strategy": {"indicators": [], "entry": {}, "exit": {}}}
    try:
        # Try to extract JSON from response
        match = re.search(r'\{.*\}', result["response"], re.DOTALL)
        if match:
            entities = json.loads(match.group(0))
            print("Extracted entities:", entities)
        else:
            # If no JSON found, try the whole response
            entities = json.loads(result["response"].strip())
            print("Extracted entities (full response):", entities)
    except Exception as e:
        print("JSON extraction failed:", e)
        try:
            entities = ast.literal_eval(result["response"])
            print("Extracted entities (ast):", entities)
        except Exception as e2:
            print("AST extraction failed:", e2)
            # Don't immediately ask for clarification, check conversation state first
            pass

    # Update conversation state with new information
    updated_fields = conv_state.update_from_input(user_input, entities)
    print(f"[CONVERSATION STATE] Updated fields: {updated_fields}")
    print(f"[CONVERSATION STATE] New state: {conv_state.get_summary()}")
    
    # Check if we have enough information to run a backtest
    if conv_state.is_complete():
        print("[CONVERSATION STATE] Strategy is complete! Validating compatibility...")
        
        # Get strategy config from conversation state
        strategy_info = conv_state.to_strategy_config()
        
        # Validate strategy compatibility with our registries
        indicators_registry, operators_registry, strategies_registry = get_registries()
        is_compatible, feedback_message, updated_strategy_config = validate_strategy_compatibility(
            strategy_info["strategy_config"], 
            indicators_registry, 
            operators_registry, 
            strategies_registry,
            client
        )
        
        if not is_compatible:
            print(f"[VALIDATION] Strategy compatibility issues found")
            return {"conversation": True, "message": feedback_message, "needs_clarification": True}
        
        print("[CONVERSATION STATE] Strategy is compatible! Running backtest...")
        
        # Update the conversation state with any ticker corrections from validation
        if updated_strategy_config.get('ticker') != strategy_info["strategy_config"].get('ticker'):
            conv_state.ticker = updated_strategy_config.get('ticker')
            print(f"[TICKER VALIDATION] Updated ticker to: {conv_state.ticker}")
        
        # Run backtest with accumulated information (use updated config if ticker changed)
        strategy_info["strategy_config"] = updated_strategy_config
        result = run_backtest(
            ticker=strategy_info["ticker"],
            strategy="CUSTOM",
            strategy_config=strategy_info["strategy_config"]
        )
        
        return sanitize_for_json(result)
    
    else:
        # Strategy is not complete, ask for missing information
        missing_components = conv_state.get_missing_components()
        print(f"[CONVERSATION STATE] Missing components: {missing_components}")
        
        # Generate contextual clarification request
        clarification_context = f"Current strategy state: {conv_state.get_summary()}"
        response_msg = generate_conversational_response(
            user_input, 
            f"Missing components: {', '.join(missing_components)}. {clarification_context}", 
            conversation_history
        )
        return {"conversation": True, "message": response_msg, "needs_clarification": True}

# Fast path removed - not needed

# Performance monitoring
performance_stats = {
    'registry_loads': 0,
    'ticker_validations': 0,
    'gemini_calls': 0,
    'cache_hits': 0
}

def get_performance_stats():
    """Get current performance statistics"""
    return performance_stats.copy()

# Example usage
if __name__ == "__main__":
    user_input = input("Describe your backtest: ")
    result = decode_natural_language(user_input)
    print(json.dumps(result, indent=2))