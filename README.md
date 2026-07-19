# BacktestGPT

A conversational AI-powered trading strategy backtesting platform that lets you describe trading strategies in natural language and get instant performance analysis.

> **Live demo:** frontend on Vercel, API on Render — see the [Deployment](#deployment) section to run your own.

## Overview

BacktestGPT transforms the complex process of backtesting trading strategies into a simple conversation. Instead of writing code or configuring complex parameters, just describe your strategy naturally: "Buy Apple when the 50-day SMA crosses above the 200-day SMA" - and get comprehensive backtest results with performance metrics and visualizations.

## Features

- **Natural Language Interface**: Describe trading strategies in plain English
- **Conversational AI**: Build complex strategies through guided conversations
- **Real-time Validation**: Automatic ticker symbol validation using yfinance
- **Technical Indicators**: Support for SMA, RSI, Bollinger Bands, EMA, MACD, and more
- **Comprehensive Metrics**: Get detailed performance analytics including:
  - Total Return & CAGR
  - Sharpe & Sortino Ratios
  - Max Drawdown
  - Win Rate & Profit Factor
  - Trade Statistics
- **Interactive Visualizations**: View equity curves, drawdowns, price charts with indicators, and trade signals
- **Flexible Strategy Building**: Compound entry/exit conditions (AND/OR/NOT nesting), stop-loss/take-profit, custom date ranges, cash, and fees — all from natural language
- **Production Ready**: Next.js frontend on Vercel, FastAPI backend on Render

## Tech Stack

### Backend
- **Framework**: FastAPI
- **Backtesting Engine**: VectorBT
- **AI Model**: Google Gemini 2.5 Flash
- **Data Source**: yfinance
- **Technical Analysis**: pandas, numpy, vectorbt

### Frontend
- **Framework**: Next.js 15 (React 19)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Charts**: Chart.js with react-chartjs-2
- **Font**: Geist

### Infrastructure
- **Hosting**: Vercel (frontend) + Render (backend API)
- **API**: RESTful FastAPI endpoints
- **Deployment**: Automated via render.yaml

## Getting Started

### Prerequisites
- Python 3.9+
- Node.js 18+
- npm or yarn
- Google Gemini API key

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/backtestGPT.git
cd backtestGPT
```

2. **Set up the backend**
```bash
# Install Python dependencies
pip install -r backend/requirements.txt

# Create .env file with your API key (never commit this file)
cp .env.example .env
# then edit .env and set GEMINI_API_KEY
```

3. **Set up the frontend**
```bash
cd app
npm install
```

### Running Locally

1. **Start the backend server**
```bash
# From the root directory
uvicorn backend.main:app --reload
```
The API will be available at `http://localhost:8000`

2. **Start the frontend development server**
```bash
# From the app directory
cd app
npm run dev
```
The frontend will be available at `http://localhost:3000`

### Running Tests

```bash
pip install -r backend/requirements-dev.txt
pytest tests/
```

The test suite covers the API surface, signal-rule evaluation on synthetic price data, and conversation-state management — no network or API key required.

## Usage

### Natural Language Examples

**Simple Moving Average Strategy**
```
"Backtest Apple stock using a golden cross strategy - buy when 50-day SMA crosses above 200-day SMA, sell when it crosses below"
```

**RSI Strategy**
```
"Test Tesla with RSI: buy when RSI goes below 30, sell when it goes above 70"
```

**Compound Conditions, Stops & Custom Parameters**
```
"Buy NVDA when RSI(14) is under 35 AND the price is above the 200-day SMA.
Sell when RSI goes over 70. Use a 5% stop loss, $50k starting cash, from 2018 onwards."
```

**Multi-step Conversation**
```
User: "I want to test a strategy on Microsoft"
BacktestGPT: "Great! What trading indicators would you like to use?"
User: "Use a 20-day SMA and 50-day SMA"
BacktestGPT: "Perfect! When should I buy and sell?"
User: "Buy when the 20 crosses above the 50, sell when it crosses below"
```

### API Endpoints

#### Health Check
```
GET /health
```

#### Preset Backtest
```
POST /backtest
Content-Type: application/json

{
  "ticker": "SPY",
  "strategy": "SMA",
  "start_date": "2015-01-01",
  "initial_cash": 100000,
  "fees": 0.001,
  "sma_fast": 50,
  "sma_slow": 200
}
```

#### Strategy AST Backtest (no LLM)
```
POST /backtest_spec
Content-Type: application/json

{
  "ticker": "AAPL",
  "stop_loss": 0.05,
  "indicators": [
    {"id": "sma50", "type": "SMA", "window": 50},
    {"id": "sma200", "type": "SMA", "window": 200}
  ],
  "entry": {
    "op": "cross_above",
    "left": {"kind": "indicator", "indicator_id": "sma50"},
    "right": {"kind": "indicator", "indicator_id": "sma200"}
  },
  "exit": {
    "op": "cross_below",
    "left": {"kind": "indicator", "indicator_id": "sma50"},
    "right": {"kind": "indicator", "indicator_id": "sma200"}
  }
}
```

#### Natural Language Backtest
```
POST /natural_backtest
Content-Type: application/json

{
  "input": "Backtest Apple with a 50/200 SMA crossover strategy",
  "conversation_history": []
}
```

## Supported Indicators

- **SMA** (Simple Moving Average) - Trend following indicator
- **RSI** (Relative Strength Index) - Momentum oscillator
- **BB** (Bollinger Bands) - Volatility indicator
- **EMA** (Exponential Moving Average) - Weighted moving average
- **MACD** (Moving Average Convergence Divergence) - Trend and momentum

## Supported Operators

**Comparisons** (between indicator outputs, price columns, and constants):
- `cross_above` / `cross_below` - Crossover detection (fires only on the crossing bar)
- `gt` / `lt` / `gte` / `lte` - Threshold comparisons

**Logical combinators** (arbitrarily nestable):
- `and` / `or` / `not` - Compose comparisons into compound rules, e.g. "RSI under 30 **and** price above the 200-day SMA"

**Risk controls** (separate from exit rules):
- `stop_loss` / `take_profit` - Fractional stops applied by the portfolio simulator

## Project Structure

```
backtestGPT/
├── backend/
│   ├── main.py                 # FastAPI application & routes
│   ├── schema.py               # Typed strategy AST (Pydantic) + LLM response schema
│   ├── backtest_loop.py        # Backtest engine: AST evaluation with VectorBT
│   ├── llm_decode.py           # NL agent: Gemini structured outputs + repair loop
│   ├── requirements.txt        # Python dependencies
│   └── requirements-dev.txt    # Dev/test dependencies
├── app/                        # Next.js frontend
│   ├── src/
│   │   └── app/
│   │       ├── page.tsx        # Main UI component
│   │       └── globals.css     # Global styles
│   ├── package.json            # Node dependencies
│   └── next.config.ts          # Next.js configuration
├── tests/                      # Pytest suite (schema, engine, agent, API)
├── render.yaml                 # Render deployment config for the backend API
├── .env.example                # Environment variable template
└── README.md                   # This file
```

## Architecture: How Natural Language Becomes a Backtest

The NL→backtest pipeline is built on **schema-constrained LLM decoding into a typed strategy AST**:

1. **One structured Gemini call per turn.** The model receives the full conversation and a JSON Schema (generated from Pydantic models in `schema.py`) that Gemini enforces at decoding time — invalid tokens are eliminated as the response is generated, so the output always has the right shape. The model either asks one clarifying question or emits a complete strategy.
2. **A recursive expression tree, not a flat rule format.** Entry/exit conditions are ASTs: comparison leaves (`cross_above`, `gt`, ...) composed by `and`/`or`/`not` nodes at any nesting depth. This is what makes compound strategies expressible.
3. **Semantic validation + repair loop.** Pydantic validators check what schemas can't — that every indicator reference points to a declared indicator with a valid output, operator arity, unique ids. If validation fails, the errors are fed back to the model for one corrected attempt (per benchmark findings that error feedback dramatically improves LLM structured-generation success rates).
4. **Deterministic execution.** The engine (`backtest_loop.py`) walks the validated tree into boolean signal series and hands them to VectorBT — no LLM output is ever interpreted or executed as code, so there's nothing to sandbox.
5. **Stateless server.** Conversation state lives entirely in the chat history the frontend sends with each request — no server-side sessions to collide or expire.

Ticker symbols are additionally validated against yfinance (with per-process caching) before any backtest runs.

## Performance Metrics

The backtester provides comprehensive performance analytics:

- **Start/End Value** - Portfolio value at beginning and end
- **Total Return** - Overall percentage return
- **CAGR** - Compound Annual Growth Rate
- **Max Drawdown** - Largest peak-to-trough decline
- **Sharpe Ratio** - Risk-adjusted return metric
- **Sortino Ratio** - Downside risk-adjusted return
- **Win Rate** - Percentage of profitable trades
- **Profit Factor** - Ratio of gross profit to gross loss
- **Average Win/Loss** - Average size of winning vs losing trades
- **Total Trades** - Number of trades executed

## Deployment

The frontend deploys on [Vercel](https://vercel.com) and the FastAPI backend on [Render](https://render.com).

### Backend (Render)

1. In the Render dashboard, choose **New → Blueprint** and select this repository — the included `render.yaml` configures the service
2. When prompted, set the `GEMINI_API_KEY` environment variable (it is intentionally not stored in the repo)
3. Render builds and deploys with a pinned Python 3.11 runtime and health checks against `/health`

> **Note:** On Render's free plan, services spin down when idle — the first request after a quiet period can take ~1 minute while the service cold-starts.

### Frontend (Vercel)

1. Import the repository in Vercel and set **Root Directory** to `app`
2. Add an environment variable `NEXT_PUBLIC_API_URL` pointing at the Render backend (e.g. `https://backtestgpt-backend.onrender.com` — a bare hostname also works, `https://` is added automatically)
3. Deploy — Vercel auto-detects Next.js and rebuilds on every push

### Security

- API keys are supplied via environment variables only; `.env` is git-ignored and `.env.example` documents what's needed.
- The backend never exposes the Gemini key to the browser — all LLM calls happen server-side.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

This project is open source and available under the MIT License.

## Acknowledgments

- Built with [VectorBT](https://vectorbt.dev/) for high-performance backtesting
- Powered by [Google Gemini](https://ai.google.dev/) for natural language understanding
- Market data provided by [yfinance](https://github.com/ranaroussi/yfinance)
- Frontend framework by [Next.js](https://nextjs.org/)
- Charts powered by [Chart.js](https://www.chartjs.org/)

## Contact

For questions, suggestions, or issues, please open an issue on GitHub.

---

**Note**: This tool is for educational and research purposes only. Past performance does not guarantee future results. Always conduct thorough research before making investment decisions.
