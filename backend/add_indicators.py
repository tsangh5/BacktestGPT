import pandas as pd
import os
import numpy as np

data_path = "data"
# Load CSV
with os.scandir(data_path) as entries:
    for entry in entries:
        if entry.name.endswith(".csv") and entry.is_file():
            df = pd.read_csv(entry.path)
            df['SMA20'] = df['Close'].rolling(20).mean()
            df['SMA50'] = df['Close'].rolling(50).mean()
            delta = df['Close'].diff()
            gain = np.where(delta>0, delta, 0)
            loss = np.where(delta<0, -delta, 0)
            avg_gain = pd.Series(gain).rolling(14).mean()
            avg_loss = pd.Series(loss).rolling(14).mean()
            rs = avg_gain / (avg_loss + 1e-9)
            df['RSI14'] = 100 - (100/(1+rs))
            # Generate SMA signals
            df['long_entry'] = (df['SMA20'] > df['SMA50']) & (df['SMA20'].shift(1) <= df['SMA50'].shift(1))
            df['long_exit'] = (df['SMA20'] < df['SMA50']) & (df['SMA20'].shift(1) >= df['SMA50'].shift(1))
            # Generate RSI signals
            df['rsi_long_entry'] = df['RSI14'] < 30  # Buy when oversold
            df['rsi_short_entry'] = df['RSI14'] > 70  # Sell when overbought
            df.to_csv(entry.path, index=False)
            print("Successfully added technical indicators (SMA20, SMA50, RSI14, golden cross/long entry, death cross/long exit, Oversold / RSI long, Overbought / RSI short) to", entry.name)