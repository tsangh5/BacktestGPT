import vectorbt as vbt
import pandas as pd
import numpy as np
import yfinance as yf
from typing import Optional

class VectorBTBacktester:
    def __init__(self, ticker: str, start_date: str = "2010-01-01", end_date: str = "2025-01-01"):
        """Initialize with data fetching"""
        self.ticker = ticker
        try:
            self.data_fetcher = vbt.YFData.download(
                ticker, 
                start=start_date, 
                end=end_date,
                missing_index='drop'  # Handle missing data gracefully
            )
            self.close = self.data_fetcher.get('Close')
            self.high = self.data_fetcher.get('High') 
            self.low = self.data_fetcher.get('Low')
            self.volume = self.data_fetcher.get('Volume')
            self.open = self.data_fetcher.get('Open')
        except Exception as e:
            raise Exception(f"Error fetching data for {ticker}: {str(e)}")
    
    def add_indicators(self, **kwargs):
        """Add technical indicators with flexible parameter handling"""
        try:
            # Handle SMA indicators
            sma_fast = kwargs.get('sma_fast', 5)
            sma_slow = kwargs.get('sma_slow', 20)
            self.sma_fast = vbt.MA.run(self.close, sma_fast)
            self.sma_slow = vbt.MA.run(self.close, sma_slow)
            
            # Handle RSI
            rsi_period = kwargs.get('rsi_period', 14)
            self.rsi = vbt.RSI.run(self.close, window=rsi_period)
            
            # Handle Bollinger Bands
            bb_window = kwargs.get('bb_window', 20)
            self.bb = vbt.BBANDS.run(self.close, window=bb_window)
            
            # Handle any additional SMAs from indicators config
            for key, value in kwargs.items():
                if key.startswith('sma') and key not in ['sma_fast', 'sma_slow']:
                    # Extract period from key like 'sma50_window' -> 50
                    try:
                        if '_window' in key:
                            period = int(key.replace('sma', '').replace('_window', ''))
                        else:
                            period = int(key.replace('sma', ''))
                        setattr(self, f'sma{period}', vbt.MA.run(self.close, period))
                    except ValueError:
                        continue
            
            return self
        except Exception as e:
            raise Exception(f"Error calculating indicators: {str(e)}")
    
    def generate_signals(self, strategy: str = "SMA", entry=None, exit=None, **kwargs):
        """Generate trading signals based on strategy or custom entry/exit rules"""
        try:
            # If custom entry/exit rules are provided, use them
            if entry and exit:
                entries = self._apply_signal_rule(entry)
                exits = self._apply_signal_rule(exit)
            else:
                if strategy == "SMA":
                    entries = self.sma_fast.ma_crossed_above(self.sma_slow.ma)
                    exits = self.sma_fast.ma_crossed_below(self.sma_slow.ma)
                elif strategy == "RSI":
                    rsi_oversold = kwargs.get('rsi_oversold', 30)
                    rsi_overbought = kwargs.get('rsi_overbought', 70)
                    entries = self.rsi.rsi < rsi_oversold
                    exits = self.rsi.rsi > rsi_overbought
                elif strategy == "BB_MEAN_REVERSION":
                    entries = self.close < self.bb.lower
                    exits = self.close > self.bb.middle
                elif strategy == "MOMENTUM":
                    returns = self.close.pct_change()
                    momentum_threshold = kwargs.get('momentum_threshold', 0.02)
                    stop_loss = kwargs.get('stop_loss', -0.01)
                    entries = returns > momentum_threshold
                    exits = returns < stop_loss
                else:
                    entries = self.sma_fast.ma_crossed_above(self.sma_slow.ma)
                    exits = self.sma_fast.ma_crossed_below(self.sma_slow.ma)
            
            self.entries = entries
            self.exits = exits
            return self
        except Exception as e:
            raise Exception(f"Error generating signals: {str(e)}")

    def _apply_signal_rule(self, rule):
        """Apply a signal rule from config"""
        if not isinstance(rule, dict):
            return pd.Series([False]*len(self.close), index=self.close.index)
        
        op = rule.get('op')
        args = rule.get('args', [])
        
        if not op or len(args) < 2:
            return pd.Series([False]*len(self.close), index=self.close.index)
        
        try:
            left = self._resolve_series(args[0])
            right = self._resolve_series(args[1])
            
            # Ensure both are pandas Series for vectorbt operations
            if not isinstance(left, pd.Series):
                left = pd.Series([left] * len(self.close), index=self.close.index)
            if not isinstance(right, pd.Series):
                right = pd.Series([right] * len(self.close), index=self.close.index)
            
            if op == 'cross_above':
                # For cross above, we need to detect when left crosses above right
                return (left > right) & (left.shift(1) <= right.shift(1))
            elif op == 'cross_below':
                # For cross below, we need to detect when left crosses below right
                return (left < right) & (left.shift(1) >= right.shift(1))
            elif op in ['gt', 'greater_than']:
                return left > right
            elif op in ['lt', 'less_than']:
                return left < right
            elif op in ['eq', 'equal_to']:
                return left == right
            elif op in ['gte', 'greater_than_or_equal']:
                return left >= right
            elif op in ['lte', 'less_than_or_equal']:
                return left <= right
            else:
                print(f"Unknown operator: {op}")
                return pd.Series([False]*len(self.close), index=self.close.index)
                
        except Exception as e:
            print(f"Error applying signal rule: {e}")
            return pd.Series([False]*len(self.close), index=self.close.index)

    def _resolve_series(self, ref):
        """Resolve a string reference or number to a pandas Series or value"""
        # If ref is a number, return as-is
        if isinstance(ref, (int, float)):
            return ref
        
        # If ref is a string that can be converted to float, return as float
        if isinstance(ref, str):
            try:
                if ref.replace('.', '', 1).replace('-', '', 1).isdigit():
                    return float(ref)
            except:
                pass
        
        # Handle string references to price data and indicators
        if isinstance(ref, str):
            ref_lower = ref.lower()
            
            # Basic price data
            if ref_lower == 'close':
                return self.close
            elif ref_lower == 'open':
                return self.open
            elif ref_lower == 'high':
                return self.high
            elif ref_lower == 'low':
                return self.low
            elif ref_lower == 'volume':
                return self.volume
            
            # Handle indicator references like 'SMA50.ma', 'RSI14.rsi'
            if '.' in ref:
                ind_name, attr = ref.split('.', 1)
                ind_name = ind_name.lower()
                
                # Map common indicator references
                if ind_name.startswith('sma'):
                    # Extract period from name like 'sma50'
                    try:
                        if ind_name == 'sma_fast' or ind_name == 'smafast':
                            ind_obj = self.sma_fast
                        elif ind_name == 'sma_slow' or ind_name == 'smaslow':
                            ind_obj = self.sma_slow
                        else:
                            # Try to find SMA with specific period
                            period = ''.join(filter(str.isdigit, ind_name))
                            if period:
                                ind_obj = getattr(self, f'sma{period}', None)
                            else:
                                ind_obj = None
                        
                        if ind_obj and hasattr(ind_obj, attr):
                            return getattr(ind_obj, attr)
                    except:
                        pass
                
                elif ind_name.startswith('rsi'):
                    if hasattr(self, 'rsi') and hasattr(self.rsi, attr):
                        return getattr(self.rsi, attr)
                
                elif ind_name.startswith('bb'):
                    if hasattr(self, 'bb') and hasattr(self.bb, attr):
                        return getattr(self.bb, attr)
        
        # Fallback: return zeros
        print(f"Warning: Could not resolve reference '{ref}', using zeros")
        return pd.Series([0]*len(self.close), index=self.close.index)

    def run_backtest(self, initial_cash: float = 100000, fees: float = 0.001):
        """Run the backtest"""
        try:
            self.portfolio = vbt.Portfolio.from_signals(
                close=self.close,
                entries=self.entries,
                exits=self.exits,
                init_cash=initial_cash,
                fees=fees,
                freq='D'
            )
            return self
        except Exception as e:
            raise Exception(f"Error running backtest: {str(e)}")
    
    def get_metrics(self):
        """Get comprehensive performance metrics"""
        try:
            stats = self.portfolio.stats()
            start_value = stats['Start Value']
            end_value = float(stats['End Value'])
            years = float((self.close.index[-1] - self.close.index[0]).days / 365.25)
            cagr = (end_value / start_value) ** (1 / years) - 1
            
            # Handle NaN values gracefully
            def safe_float(value, default=0.0):
                return float(value) if not pd.isna(value) else default
            
            return {
                "start_value": start_value,
                "end_value": end_value,
                "total_return": safe_float(stats['Total Return [%]']),
                "CAGR": cagr * 100,
                "max_drawdown": safe_float(stats['Max Drawdown [%]']),
                "sortino_ratio": safe_float(stats.get("Sortino Ratio", 0.0)),
                "sharpe_ratio": safe_float(stats['Sharpe Ratio']),
                "win_rate": safe_float(stats['Win Rate [%]']),
                "avg_winning_trade": safe_float(stats.get("Avg Winning Trade [%]", 0.0)),
                "avg_losing_trade": safe_float(stats.get("Avg Losing Trade [%]", 0.0)),
                "profit_factor": safe_float(stats.get("Profit Factor", 0.0)),
                "total_trades": int(safe_float(stats['Total Trades'])),
                "years": years
            }
        except Exception as e:
            raise Exception(f"Error calculating metrics: {str(e)}")
    
    def get_chart_data(self):
        """Get data formatted for charts, including indicators and signals"""
        try:
            equity_curve = self.portfolio.value()
            drawdown = self.portfolio.drawdown() * 100
            
            chart_data = {
                "dates": equity_curve.index.strftime('%Y-%m-%d').tolist(),
                "equity": equity_curve.tolist(),
                "drawdown": drawdown.tolist(),
                "close": self.close.tolist()
            }
            
            # Add indicators if available
            indicators = {}
            if hasattr(self, 'sma_fast'):
                indicators['SMA Fast'] = self.sma_fast.ma.tolist()
            if hasattr(self, 'sma_slow'):
                indicators['SMA Slow'] = self.sma_slow.ma.tolist()
            if hasattr(self, 'rsi'):
                indicators['RSI'] = self.rsi.rsi.tolist()
            if hasattr(self, 'bb'):
                indicators['BB Lower'] = self.bb.lower.tolist()
                indicators['BB Middle'] = self.bb.middle.tolist()
                indicators['BB Upper'] = self.bb.upper.tolist()
            
            # Add any additional SMA indicators
            for attr_name in dir(self):
                if attr_name.startswith('sma') and attr_name not in ['sma_fast', 'sma_slow']:
                    try:
                        sma_obj = getattr(self, attr_name)
                        if hasattr(sma_obj, 'ma'):
                            indicators[f'SMA {attr_name[3:]}'] = sma_obj.ma.tolist()
                    except:
                        continue
            
            if indicators:
                chart_data['indicators'] = indicators
            
            # Add signals if available
            signals = {}
            if hasattr(self, 'entries'):
                signals['Entries'] = self.entries.astype(int).tolist()
            if hasattr(self, 'exits'):
                signals['Exits'] = self.exits.astype(int).tolist()
            
            if signals:
                chart_data['signals'] = signals
            
            return chart_data
        except Exception as e:
            raise Exception(f"Error preparing chart data: {str(e)}")

# Main function that replaces your original run_backtest
def run_backtest(ticker: str = "SPY", 
                strategy: str = "SMA", 
                start_date: str = "2010-01-01",
                end_date: str = "2025-01-01",
                initial_cash: float = 100000,
                fees: float = 0.001,
                **strategy_params):
    """
    Main backtest function - handles both simple strategy params and complex configs
    
    Args:
        ticker: Stock ticker symbol
        strategy: Strategy name ("SMA", "RSI", "BB_MEAN_REVERSION", "MOMENTUM")
        start_date: Start date for backtest
        end_date: End date for backtest
        initial_cash: Starting capital
        fees: Transaction fees (as decimal, e.g., 0.001 = 0.1%)
        **strategy_params: Strategy-specific parameters or strategy_config
    
    Returns:
        Dictionary with metrics and chart_data
    """
    try:
        bt = VectorBTBacktester(ticker, start_date, end_date)
        
        # Check if we have a strategy_config (from LLM)
        if 'strategy_config' in strategy_params:
            config = strategy_params['strategy_config']
            print(f"[DEBUG] Processing strategy config: {config}")
            
            # Extract indicator parameters
            indicators = config.get('indicators', [])
            indicator_kwargs = {}
            
            for ind in indicators:
                print(f"[DEBUG] Processing indicator: {ind}")
                ind_type = ind.get('type', '').lower()
                ind_id = ind.get('id', '').lower()
                params = ind.get('params', {})
                
                if ind_type == 'sma' or 'sma' in ind_id:
                    window = params.get('window', 20)
                    # Extract period number from id like 'sma50'
                    period = ''.join(filter(str.isdigit, ind_id))
                    
                    if period:
                        # Store both the generic sma_fast/slow and specific period
                        if period in ['5', '10', '20', '50']:
                            indicator_kwargs['sma_fast'] = window if period in ['5', '10'] else indicator_kwargs.get('sma_fast', window)
                        if period in ['20', '50', '100', '200']:
                            indicator_kwargs['sma_slow'] = window if period in ['50', '100', '200'] else indicator_kwargs.get('sma_slow', window)
                        
                        # Also store the specific period for direct access
                        indicator_kwargs[f'sma{period}_window'] = window
                    else:
                        # Default SMA handling
                        if 'fast' in ind_id:
                            indicator_kwargs['sma_fast'] = window
                        elif 'slow' in ind_id:
                            indicator_kwargs['sma_slow'] = window
                
                elif ind_type == 'rsi':
                    window = params.get('window', 14)
                    indicator_kwargs['rsi_period'] = window
                
                elif ind_type == 'bb' or ind_type == 'bollinger':
                    window = params.get('window', 20)
                    indicator_kwargs['bb_window'] = window
            
            print(f"[DEBUG] Indicator kwargs: {indicator_kwargs}")
            bt.add_indicators(**indicator_kwargs)
            
            # Extract entry/exit rules
            entry = config.get('entry', {})
            exit = config.get('exit', {})
            
            print(f"[DEBUG] Entry rule: {entry}")
            print(f"[DEBUG] Exit rule: {exit}")
            
            bt.generate_signals(strategy, entry=entry, exit=exit)
            
        else:
            # Handle simple strategy parameters (legacy mode)
            bt.add_indicators(**strategy_params)
            bt.generate_signals(strategy, **strategy_params)
        
        bt.run_backtest(initial_cash, fees)
        
        return {
            "metrics": bt.get_metrics(),
            "chart_data": bt.get_chart_data()
        }
        
    except Exception as e:
        print(f"[ERROR] Backtest failed: {str(e)}")
        return {
            "error": str(e),
            "metrics": None,
            "chart_data": None
        }

# Legacy compatibility - keep your old function signature working
def run_backtest_legacy(ticker="SPY", strategy="SMA"):
    """Maintains compatibility with your existing code"""
    return run_backtest(ticker, strategy)