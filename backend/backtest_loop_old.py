import os
import pandas as pd

def run_backtest(ticker="SPY", strategy="SMA"):
    data_path = "data"
    df = pd.read_csv(os.path.join(data_path, f"{ticker}.csv"))
    df['Date'] = pd.to_datetime(df['Date'])
    df.set_index('Date', inplace=True)

    capital = 100000
    position = 0
    equity_curve = []

    # Choose signals based on strategy
    if strategy == "SMA":
        long_entry_col = 'long_entry'
        long_exit_col = 'long_exit'
    elif strategy == "RSI":
        long_entry_col = 'rsi_long_entry'
        long_exit_col = 'rsi_short_entry'
    else:
        long_entry_col = 'long_entry'
        long_exit_col = 'long_exit'

    for i, row in df.iterrows():
        if row.get(long_entry_col, False) and position == 0:
            position = capital / row['Close']
            entry_price = row['Close']
        elif row.get(long_exit_col, False) and position > 0:
            capital = position * row['Close']
            position = 0
        equity_curve.append(capital if position==0 else position*row['Close'])

    df['Equity'] = equity_curve

    start_val = df['Equity'].iloc[0]
    end_val = df['Equity'].iloc[-1]
    years = (df.index[-1] - df.index[0]).days / 365.25
    CAGR = (end_val/start_val)**(1/years) - 1
    cum_max = df['Equity'].cummax()
    drawdown = (df['Equity'] - cum_max)/cum_max
    max_drawdown = drawdown.min()

    chart_data = {
        "dates": df.index.strftime('%Y-%m-%d').tolist(),
        "equity": df['Equity'].tolist(),
        "drawdown": (drawdown * 100).tolist()
    }

    metrics = {
        "start_value": start_val,
        "end_value": end_val,
        "total_return": ((end_val/start_val)-1)*100,
        "CAGR": CAGR*100,
        "max_drawdown": max_drawdown*100,
        "years": years
    }

    return {
        "metrics": metrics,
        "chart_data": chart_data
    }