import yfinance as yf
# df = yf.download("SPY", start="2010-01-01", end="2025-01-01")
# df.to_csv("data/SPY.csv")
df = yf.download("NDAQ", start="2010-01-01", end="2025-01-01")
df.to_csv("data/NDAQ.csv")