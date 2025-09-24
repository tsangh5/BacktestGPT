from google import genai
import re
import yfinance as yf
import json

# Initialize the client
client = genai.Client()

def validate_ticker(ticker):
    """
    Validate if a ticker symbol exists and has data available.
    Returns (is_valid, error_message)
    """
    if not ticker or not isinstance(ticker, str):
        return False, "Invalid ticker format"
    
    ticker = ticker.strip().upper()
    
    # Basic format check
    if not re.match(r'^[A-Z0-9.-]+$', ticker) or len(ticker) < 1 or len(ticker) > 10:
        return False, f"Ticker '{ticker}' has invalid format"
    
    try:
        # Try to fetch recent data to validate ticker exists
        stock = yf.Ticker(ticker)
        # Get last 5 days of data to check if ticker is valid
        hist = stock.history(period="5d")
        
        if hist.empty:
            return False, f"No data available for ticker '{ticker}'"
        
        return True, f"Ticker '{ticker}' is valid"
    
    except Exception as e:
        return False, f"Error validating ticker '{ticker}': {str(e)}"

def extract_ticker_from_response(response_text):
    """Extract ticker from Gemini's JSON response"""
    try:
        # Try to extract JSON from response
        match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
        else:
            data = json.loads(response_text.strip())
        
        return data.get("ticker", None)
    except:
        return None

def get_alternative_ticker(user_input, invalid_ticker):
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
    
    Return ONLY the ticker symbol (e.g., "AAPL"), nothing else.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=alternative_prompt,
        )
        
        alternative_ticker = response.text.strip().strip('"').upper()
        
        # Validate the alternative ticker
        is_valid, message = validate_ticker(alternative_ticker)
        if is_valid:
            print(f"Found alternative ticker: {alternative_ticker}")
            return alternative_ticker
        else:
            print(f"Alternative ticker {alternative_ticker} is also invalid: {message}")
            return "SPY"  # Default fallback
            
    except Exception as e:
        print(f"Error getting alternative ticker: {e}")
        return "SPY"  # Default fallback

# Define the user input
user_input = "I want to backtest buying Apple when the 50-day moving average crosses above the 200-day moving average, and selling when it crosses below."

# Create the prompt for the AI model
prompt = (
    """
    You are an expert trading strategy translator.  
    Your task is to take a natural language description of a trading/backtesting strategy and convert it into a structured JSON object that can be executed with vectorbt.  

    Follow these rules strictly:  
    1. Always return valid JSON only — no explanation, no extra text.  
    2. The JSON schema must match exactly this format:  

    {
    "ticker": "string (e.g., 'AAPL')",
    "strategy": {
        "indicators": {
        "name": {
            "func": "vectorbt function name (e.g., 'ta.sma', 'ta.rsi')",
            "params": { "param_name": value, "column": "price column (e.g., 'Close')" }
        }
        },
        "entry": {
        "signal": { "op": "string (e.g., 'cross_above', 'greater_than')", "args": ["indicator_or_column", "indicator_or_column"] }
        },
        "exit": {
        "signal": { "op": "string", "args": ["indicator_or_column", "indicator_or_column"] }
        }
    }
    }

    3. Use vectorbt-compatible vocabulary for indicators (e.g., `ta.sma`, `ta.ema`, `ta.rsi`, `ta.macd`).  
    4. Operators must come from this set:  
    - "cross_above"  
    - "cross_below"  
    - "greater_than"  
    - "less_than"  
    - "equal_to"  
    5. Arguments (`args`) can be raw price columns (`Close`, `Open`, `High`, `Low`, `Volume`) or indicator outputs (like `SMA50.ma`, `RSI14.rsi`).  
    6. If the user does not specify a ticker, default to `"SPY"`.  
    7. If the user does not specify an exit condition, leave `"exit"` empty.  

    Return **only the JSON object**, nothing else.

    """ + f"Here is the natural language description: {user_input}"
)

# Generate content using the AI model
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
)

# Extract the response text
text = response.text

# Extract only the content between the first and last curly braces
match = re.search(r'\{.*\}', text, re.DOTALL)

if match:
    json_response = match.group(0)
    print("Initial Gemini response:")
    print(json_response)
    
    # Extract and validate ticker
    extracted_ticker = extract_ticker_from_response(text)
    print(f"\nExtracted ticker: {extracted_ticker}")
    
    if extracted_ticker:
        is_valid, validation_message = validate_ticker(extracted_ticker)
        print(f"Ticker validation: {validation_message}")
        
        if not is_valid:
            print(f"Ticker '{extracted_ticker}' is invalid. Getting alternative...")
            
            # Get alternative ticker
            alternative_ticker = get_alternative_ticker(user_input, extracted_ticker)
            print(f"Alternative ticker: {alternative_ticker}")
            
            # Update the JSON response with the corrected ticker
            try:
                data = json.loads(json_response)
                data["ticker"] = alternative_ticker
                corrected_json = json.dumps(data, indent=2)
                print(f"\nCorrected response with valid ticker:")
                print(corrected_json)
            except Exception as e:
                print(f"Error updating JSON: {e}")
                print("Using original response")
                print(json_response)
        else:
            print(f"Ticker '{extracted_ticker}' is valid!")
            print("\nFinal response:")
            print(json_response)
    else:
        print("No ticker found in response")
        print(json_response)
else:
    print("No JSON found in response:")
    print(text)