from google import genai

client = genai.Client()
user_input = "I want to backtest buying Apple when the 50-day moving average crosses above the 200-day moving average, and selling when it crosses below."
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
import re
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
)
text = response.text
# Extract only the content between the first and last curly braces
match = re.search(r'\{.*\}', text, re.DOTALL)
if match:
    print(match.group(0))
else:
    print(text)