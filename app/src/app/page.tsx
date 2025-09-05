'use client';

import React, { useState, useCallback, useMemo } from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

type ChartObj = { name: string; chart: any };

export default function Home() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [nlInput, setNlInput] = useState('');

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setNlInput(e.target.value);
  }, []);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setData(null);
    try {
      const res = await fetch('http://localhost:8000/natural_backtest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input: nlInput }),
      });
      const json = await res.json();
      setData(json);
    } catch (error) {
      console.error('Fetch error:', error);
    } finally {
      setLoading(false);
    }
  }, [nlInput]);

  const chartData = useMemo(() => {
    return data && data.chart_data ? data.chart_data : {};
  }, [data]);

  const equityChart = useMemo(() => {
    if (!chartData.dates || !chartData.equity) return null;
    return {
      labels: chartData.dates,
      datasets: [
        {
          label: 'Equity Curve',
          data: chartData.equity,
          borderColor: 'rgb(59, 130, 246)',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          fill: false,
        },
      ],
    };
  }, [chartData]);

  const drawdownChart = useMemo(() => {
    if (!chartData.dates || !chartData.drawdown) return null;
    return {
      labels: chartData.dates,
      datasets: [
        {
          label: 'Drawdown (%)',
          data: chartData.drawdown,
          borderColor: 'rgb(239, 68, 68)',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          fill: false,
        },
      ],
    };
  }, [chartData]);

  const indicatorCharts = useMemo((): ChartObj[] => {
    if (!chartData.indicators) return [];
    return Object.entries(chartData.indicators).map(([name, values]) => ({
      name,
      chart: {
        labels: chartData.dates,
        datasets: [
          {
            label: name,
            data: values,
            borderColor: 'rgb(34, 197, 94)',
            backgroundColor: 'rgba(34, 197, 94, 0.1)',
            fill: false,
          },
        ],
      },
    }));
  }, [chartData]);

  const signalCharts = useMemo((): ChartObj[] => {
    if (!chartData.signals) return [];
    return Object.entries(chartData.signals).map(([name, values]) => ({
      name,
      chart: {
        labels: chartData.dates,
        datasets: [
          {
            label: name,
            data: values,
            borderColor: 'rgb(249, 115, 22)',
            backgroundColor: 'rgba(249, 115, 22, 0.1)',
            fill: false,
          },
        ],
      },
    }));
  }, [chartData]);

  const getMetricClassName = (value: number | undefined, type: 'return' | 'ratio' | 'factor' | 'neutral') => {
    if (type === 'neutral') return 'metric-neutral';
    if (value === undefined) return 'metric-neutral';
    
    switch (type) {
      case 'return':
        return value >= 0 ? 'metric-positive' : 'metric-negative';
      case 'ratio':
        return 'metric-info';
      case 'factor':
        return value >= 1 ? 'metric-positive' : 'metric-negative';
      default:
        return 'metric-neutral';
    }
  };

  const metrics = [
    { label: 'Starting Value', value: data?.metrics?.start_value, format: 'currency', type: 'neutral' as const },
    { label: 'Ending Value', value: data?.metrics?.end_value, format: 'currency', type: 'neutral' as const },
    { label: 'Total Return', value: data?.metrics?.total_return, format: 'percent', type: 'return' as const },
    { label: 'CAGR', value: data?.metrics?.CAGR, format: 'percent', type: 'return' as const },
    { label: 'Max Drawdown', value: data?.metrics?.max_drawdown, format: 'percent', type: 'neutral' as const, className: 'metric-negative' },
    { label: 'Sharpe Ratio', value: data?.metrics?.sharpe_ratio, format: 'number', type: 'ratio' as const },
    { label: 'Sortino Ratio', value: data?.metrics?.sortino_ratio, format: 'number', type: 'ratio' as const },
    { label: 'Total Trades', value: data?.metrics?.total_trades, format: 'integer', type: 'neutral' as const },
    { label: 'Win Rate', value: data?.metrics?.win_rate, format: 'percent', type: 'neutral' as const, className: 'metric-positive' },
    { label: 'Avg Winning Trade', value: data?.metrics?.avg_winning_trade, format: 'percent', type: 'neutral' as const, className: 'metric-positive' },
    { label: 'Avg Losing Trade', value: data?.metrics?.avg_losing_trade, format: 'percent', type: 'neutral' as const, className: 'metric-negative' },
    { label: 'Profit Factor', value: data?.metrics?.profit_factor, format: 'number', type: 'factor' as const },
    { label: 'Years', value: data?.metrics?.years, format: 'number', type: 'neutral' as const },
  ];

  const formatValue = (value: number | undefined, format: string) => {
    if (value === undefined) return '0.00';
    
    switch (format) {
      case 'currency':
        return `$${value.toFixed(2)}`;
      case 'percent':
        return `${value.toFixed(2)}%`;
      case 'integer':
        return value.toString();
      case 'number':
      default:
        return value.toFixed(2);
    }
  };

  return (
    <div className="page-container">
      <div className="content-wrapper">
        <h1 className="page-title">Backtest Results</h1>
        
        <form onSubmit={handleSubmit} className="card mb-8">
          <div className="mb-4">
            <label className="form-label">Strategy Description:</label>
            <div className="flex gap-4 items-center">
              <input
                type="text"
                value={nlInput}
                onChange={handleInputChange}
                className="form-input"
                placeholder="e.g. Buy when RSI < 30, sell when RSI > 70 for SPY"
              />
              <button type="submit" disabled={loading} className="btn-primary">
                {loading ? 'Running...' : 'Run Backtest'}
              </button>
            </div>
          </div>
        </form>

        {loading && (
          <div className="loading-container">
            <div className="loading-content">
              <div className="loading-dot"></div>
              <div className="loading-dot" style={{animationDelay: '0.1s'}}></div>
              <div className="loading-dot" style={{animationDelay: '0.2s'}}></div>
              <span className="loading-text">Loading...</span>
            </div>
          </div>
        )}

        {!loading && data && (
          <div className="content-section">
            {/* Metrics Grid */}
            <div className="card">
              <h2 className="section-title">Performance Metrics</h2>
              <div className="metrics-grid">
                {metrics.map(({ label, value, format, type, className }) => (
                  <div key={label} className="metric-card">
                    <div className="metric-label">{label}</div>
                    <div className={className || getMetricClassName(value, type)}>
                      {formatValue(value, format)}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Charts */}
            <div className="charts-grid">
              <div className="chart-container">
                <h2 className="section-title">Equity Curve</h2>
                <div className="chart-wrapper">
                  {equityChart && <Line data={equityChart} options={{maintainAspectRatio: false}} />}
                </div>
              </div>

              <div className="chart-container">
                <h2 className="section-title">Drawdown (%)</h2>
                <div className="chart-wrapper">
                  {drawdownChart && <Line data={drawdownChart} options={{maintainAspectRatio: false}} />}
                </div>
              </div>
            </div>

            {/* Indicators */}
            {indicatorCharts.length > 0 && (
              <div className="card">
                <h2 className="section-title">Indicators</h2>
                <div className="indicators-grid">
                  {indicatorCharts.map(({ name, chart }) => (
                    <div key={name} className="rounded-lg p-4">
                      <h3 className="subsection-title">{name}</h3>
                      <div className="chart-wrapper-sm">
                        <Line data={chart} options={{maintainAspectRatio: false}} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Signals */}
            {signalCharts.length > 0 && (
              <div className="card">
                <h2 className="section-title">Signals</h2>
                <div className="indicators-grid">
                  {signalCharts.map(({ name, chart }) => (
                    <div key={name} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                      <h3 className="subsection-title">{name}</h3>
                      <div className="chart-wrapper-sm">
                        <Line data={chart} options={{maintainAspectRatio: false}} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}