# BacktestGPT

A conversational AI-powered trading strategy backtesting platform that lets you describe trading strategies in natural language and get instant performance analysis.

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
- **Flexible Strategy Building**: Support for custom entry/exit conditions with multiple operators
- **Production Ready**: Deployed on Render with FastAPI backend and Next.js frontend

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
- **Hosting**: Render
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

# Create .env file with your API key
echo "GEMINI_API_KEY=your_api_key_here" > .env
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

#### Traditional Backtest
```
POST /backtest
Content-Type: application/json

{
  "ticker": "SPY",
  "strategy": "SMA",
  "start_date": "2010-01-01",
  "end_date": "2025-01-01",
  "initial_cash": 100000,
  "fees": 0.001,
  "sma_fast": 50,
  "sma_slow": 200
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

- `cross_above` - When first indicator crosses above second
- `cross_below` - When first indicator crosses below second
- `greater_than` / `gt` - Simple comparison
- `less_than` / `lt` - Simple comparison
- `equal_to` / `eq` - Equality check
- `greater_than_or_equal` / `gte` - Greater than or equal
- `less_than_or_equal` / `lte` - Less than or equal

## Project Structure

```
backtestGPT/
├── backend/
│   ├── main.py                 # FastAPI application & routes
│   ├── backtest_loop.py        # Core backtesting logic with VectorBT
│   ├── llm_decode.py           # Natural language processing & AI integration
│   ├── genai.py                # Gemini API client setup
│   ├── indicators.json         # Indicator registry
│   ├── operators.json          # Operator registry
│   ├── basic_strategies.json   # Predefined strategy templates
│   └── requirements.txt        # Python dependencies
├── app/                        # Next.js frontend
│   ├── src/
│   │   └── app/
│   │       ├── page.tsx        # Main UI component
│   │       └── globals.css     # Global styles
│   ├── package.json            # Node dependencies
│   └── next.config.ts          # Next.js configuration
├── render.yaml                 # Render deployment configuration
└── README.md                   # This file
```

## Key Features Explained

### Conversational AI
The system uses Google Gemini to maintain conversation context and progressively build trading strategies. It intelligently tracks what information has been provided and asks targeted follow-up questions to complete the strategy definition.

### Ticker Validation
All ticker symbols are validated against yfinance to ensure data availability before running backtests. The system includes intelligent caching to avoid repeated API calls and can suggest alternative ticker symbols for common company names.

### Strategy Compatibility Checking
Before running a backtest, the system validates that:
- All indicators are supported
- All operators are valid
- The strategy structure is complete
- The ticker has available data

### Performance Optimization
- Registry caching for faster indicator/operator lookups
- Ticker validation caching to reduce API calls
- Smart conversation summarization for long conversations
- Efficient data handling with pandas and numpy

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

The application is configured for deployment on Render using the included `render.yaml` file:

1. Connect your GitHub repository to Render
2. Add your `GEMINI_API_KEY` environment variable in the Render dashboard
3. Render will automatically deploy both backend and frontend services

The deployment configuration includes:
- Automatic health checks
- Environment variable management
- Build and start commands
- Service linking for backend/frontend communication

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
