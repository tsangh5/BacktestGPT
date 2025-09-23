'use client';

import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import Image from 'next/image';
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
import type { ChartDataset } from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

// Types
type ChatMessage = {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
};

type ChartDataObj = {
  dates: string[];
  equity: number[];
  drawdown: number[];
  indicators?: Record<string, number[]>;
  signals?: Record<string, number[]>;
};

type Metrics = {
  start_value?: number;
  end_value?: number;
  total_return?: number;
  CAGR?: number;
  max_drawdown?: number;
  sharpe_ratio?: number;
  sortino_ratio?: number;
  total_trades?: number;
  win_rate?: number;
  avg_winning_trade?: number;
  avg_losing_trade?: number;
  profit_factor?: number;
  years?: number;
};

type DataType = {
  chart_data: ChartDataObj;
  metrics: Metrics;
  conversation?: any;  // keep any here if structure is unknown
  needs_clarification?: boolean;
  message?: string;
  error?: string;
};

type ChartObj = { 
  name: string; 
  chart: { 
    labels: string[]; 
    datasets: ChartDataset<'line'>[]; 
  }; 
};
// Styles moved outside component (prevents recreation on every render)
const styles = {
  positive: 'metric-positive',
  negative: 'metric-negative',
  neutral: 'metric-neutral',
  info: 'metric-info',
};

// Main Component
export default function Home() {
  const [data, setData] = useState<DataType | null>(null);
  const [loading, setLoading] = useState(false);
  const [processingBacktest, setProcessingBacktest] = useState(false);
  const [nlInput, setNlInput] = useState('');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: 'Hi! I\'ll help you create and backtest a trading strategy. What would you like to backtest?',
      timestamp: new Date()
    }
  ]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  /** Handlers (memoized with useCallback) */
  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setNlInput(e.target.value);
  }, []);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, loading]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      if (!nlInput.trim()) return;
      
      // Add user message to chat
      const userMessage: ChatMessage = {
        role: 'user',
        content: nlInput,
        timestamp: new Date()
      };
      
      setChatHistory(prev => [...prev, userMessage]);
      setLoading(true);
      const currentInput = nlInput;
      setNlInput(''); // Clear input immediately
      
      try {
        const res = await fetch('http://localhost:8000/natural_backtest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            input: currentInput,
            conversation_history: chatHistory.map(msg => ({
              role: msg.role,
              content: msg.content
            }))
          }),
        });
        const json = await res.json();
        
        if (json.conversation && json.needs_clarification) {
          // Add assistant clarification message to chat
          const assistantMessage: ChatMessage = {
            role: 'assistant',
            content: json.message,
            timestamp: new Date()
          };
          setChatHistory(prev => [...prev, assistantMessage]);
          setData(null); // Clear any previous results
        } else if (json.error) {
          // Handle other errors
          const errorMessage: ChatMessage = {
            role: 'assistant',
            content: `I encountered an issue: ${json.error}`,
            timestamp: new Date()
          };
          setChatHistory(prev => [...prev, errorMessage]);
        } else {
          // Success - show results and confirmation message
          const successMessage: ChatMessage = {
            role: 'assistant',
            content: 'Great! I\'ve run your backtest. Here are the results:',
            timestamp: new Date()
          };
          setChatHistory(prev => [...prev, successMessage]);
          
          // Show processing state while results are being prepared
          setProcessingBacktest(true);
          setTimeout(() => {
            setData(json);
            setProcessingBacktest(false);
          }, 500); // Brief delay to show the blue dots
        }
      } catch (error) {
        console.error('Fetch error:', error);
        const errorMessage: ChatMessage = {
          role: 'assistant',
          content: 'Sorry, I encountered a connection error. Please try again.',
          timestamp: new Date()
        };
        setChatHistory(prev => [...prev, errorMessage]);
      } finally {
        setLoading(false);
      }
    },
    [nlInput, chatHistory]
  );

  /** Chart Data (memoized with useMemo) */
  const chartData = useMemo(() => {
    return data?.chart_data ?? {};
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

  const indicatorCharts = useMemo<ChartObj[]>(() => {
    if (!chartData.indicators) return [];
    return Object.entries(chartData.indicators).map(([name, values]) => ({
      name,
      chart: {
        labels: chartData.dates,
        datasets: [
          {
            label: name,
            data: values as number[],
            borderColor: 'rgb(34, 197, 94)',
            backgroundColor: 'rgba(34, 197, 94, 0.1)',
            fill: false,
          },
        ],
      },
    }));
  }, [chartData]);

  const signalCharts = useMemo<ChartObj[]>(() => {
    if (!chartData.signals) return [];
    return Object.entries(chartData.signals).map(([name, values]) => ({
      name,
      chart: {
        labels: chartData.dates,
        datasets: [
          {
            label: name,
            data: values as number[],
            borderColor: 'rgb(249, 115, 22)',
            backgroundColor: 'rgba(249, 115, 22, 0.1)',
            fill: false,
          },
        ],
      },
    }));
  }, [chartData]);

  /** Metric Styling */
  const getMetricClassName = useCallback(
    (value: number | undefined, type: 'return' | 'ratio' | 'factor' | 'neutral') => {
      if (type === 'neutral' || value === undefined) return styles.neutral;
      switch (type) {
        case 'return':
          return value >= 0 ? styles.positive : styles.negative;
        case 'ratio':
          return styles.info;
        case 'factor':
          return value >= 1 ? styles.positive : styles.negative;
        default:
          return styles.neutral;
      }
    },
    []
  );

  /** Metrics (memoized list for stable rendering) */
  const metrics = useMemo(
    () => [
      { label: 'Starting Value', value: data?.metrics?.start_value, format: 'currency', type: 'neutral' as const },
      { label: 'Ending Value', value: data?.metrics?.end_value, format: 'currency', type: 'neutral' as const },
      { label: 'Total Return', value: data?.metrics?.total_return, format: 'percent', type: 'return' as const },
      { label: 'CAGR', value: data?.metrics?.CAGR, format: 'percent', type: 'return' as const },
      { label: 'Max Drawdown', value: data?.metrics?.max_drawdown, format: 'percent', type: 'neutral' as const, className: styles.negative },
      { label: 'Sharpe Ratio', value: data?.metrics?.sharpe_ratio, format: 'number', type: 'ratio' as const },
      { label: 'Sortino Ratio', value: data?.metrics?.sortino_ratio, format: 'number', type: 'ratio' as const },
      { label: 'Total Trades', value: data?.metrics?.total_trades, format: 'integer', type: 'neutral' as const },
      { label: 'Win Rate', value: data?.metrics?.win_rate, format: 'percent', type: 'neutral' as const, className: styles.positive },
      { label: 'Avg Winning Trade', value: data?.metrics?.avg_winning_trade, format: 'percent', type: 'neutral' as const, className: styles.positive },
      { label: 'Avg Losing Trade', value: data?.metrics?.avg_losing_trade, format: 'percent', type: 'neutral' as const, className: styles.negative },
      { label: 'Profit Factor', value: data?.metrics?.profit_factor, format: 'number', type: 'factor' as const },
      { label: 'Years', value: data?.metrics?.years, format: 'number', type: 'neutral' as const },
    ],
    [data]
  );

  /** Value Formatter */
  const formatValue = useCallback((value: number | undefined, format: string) => {
    if (value === undefined) return '0.00';
    switch (format) {
      case 'currency':
        return `$${value.toFixed(2)}`;
      case 'percent':
        return `${value.toFixed(2)}%`;
      case 'integer':
        return value.toString();
      default:
        return value.toFixed(2);
    }
  }, []);

  /** Render */
  return (
    <div className="page-container" style={{ padding: '2rem', maxWidth: '1400px', margin: '0 auto' }}>
      <div className="content-wrapper" style={{ padding: '0 1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '2rem', gap: '1rem' }}>
          <Image 
            src="/logo.svg" 
            alt="BacktestGPT Logo" 
            width={48} 
            height={48}
            style={{ flexShrink: 0 }}
          />
          <h1 className="page-title" style={{ margin: '0', fontSize: '2.5rem', fontWeight: 'bold' }}>BacktestGPT</h1>
        </div>

        {/* Chat Interface */}
        <div 
          className="chat-container"
          style={{ 
            backgroundColor: 'white', 
            borderRadius: '0.75rem', 
            boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)', 
            marginBottom: '3rem', 
            margin: '0 0 3rem 0',
            display: 'flex', 
            flexDirection: 'column', 
            height: '24rem' 
          }}
        >
          <div 
            className="chat-header"
            style={{ 
              padding: '1rem', 
              borderBottom: '1px solid #e5e7eb', 
              backgroundColor: '#f9fafb', 
              borderTopLeftRadius: '0.5rem', 
              borderTopRightRadius: '0.5rem' 
            }}
          >
            <h2 
              className="chat-title"
              style={{ 
                fontSize: '1.125rem', 
                fontWeight: '600', 
                color: '#111827', 
                margin: 0 
              }}
            >
              Strategy Assistant
            </h2>
          </div>
          
          <div 
            className="chat-messages"
            style={{ 
              flex: '1', 
              padding: '1rem', 
              display: 'flex', 
              flexDirection: 'column', 
              gap: '1rem', 
              overflowY: 'auto' 
            }}
          >
            {chatHistory.map((message, index) => (
              <div 
                key={index} 
                className={`message ${message.role}`}
                style={{ 
                  display: 'flex', 
                  justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start' 
                }}
              >
                <div 
                  className="message-content"
                  style={{ 
                    maxWidth: message.role === 'user' ? '16rem' : '24rem', 
                    padding: '0.5rem 1rem', 
                    borderRadius: '0.5rem',
                    backgroundColor: message.role === 'user' ? '#3b82f6' : '#f3f4f6',
                    color: message.role === 'user' ? 'white' : '#111827'
                  }}
                >
                  <div 
                    className="message-text"
                    style={{ 
                      fontSize: '0.875rem', 
                      lineHeight: '1.5' 
                    }}
                  >
                    {message.content}
                  </div>
                </div>
              </div>
            ))}
            
            {loading && (
              <div 
                className="message assistant"
                style={{ 
                  display: 'flex', 
                  justifyContent: 'flex-start' 
                }}
              >
                <div 
                  className="message-content"
                  style={{ 
                    maxWidth: '24rem', 
                    padding: '0.5rem 1rem', 
                    borderRadius: '0.5rem',
                    backgroundColor: '#f3f4f6',
                    color: '#111827'
                  }}
                >
                  <div 
                    className="typing-indicator"
                    style={{ 
                      display: 'flex', 
                      gap: '0.25rem' 
                    }}
                  >
                    <div 
                      className="typing-dot"
                      style={{ 
                        width: '0.5rem', 
                        height: '0.5rem', 
                        backgroundColor: '#9ca3af', 
                        borderRadius: '50%',
                        animation: 'bounce 1.4s ease-in-out infinite both'
                      }}
                    ></div>
                    <div 
                      className="typing-dot"
                      style={{ 
                        width: '0.5rem', 
                        height: '0.5rem', 
                        backgroundColor: '#9ca3af', 
                        borderRadius: '50%',
                        animation: 'bounce 1.4s ease-in-out infinite both',
                        animationDelay: '0.16s'
                      }}
                    ></div>
                    <div 
                      className="typing-dot"
                      style={{ 
                        width: '0.5rem', 
                        height: '0.5rem', 
                        backgroundColor: '#9ca3af', 
                        borderRadius: '50%',
                        animation: 'bounce 1.4s ease-in-out infinite both',
                        animationDelay: '0.32s'
                      }}
                    ></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
          
          <form 
            onSubmit={handleSubmit} 
            className="chat-input-form"
            style={{ 
              padding: '1rem', 
              borderTop: '1px solid #e5e7eb', 
              display: 'flex', 
              gap: '0.5rem' 
            }}
          >
            <input
              type="text"
              value={nlInput}
              onChange={handleInputChange}
              className="chat-input"
              style={{ 
                flex: '1', 
                padding: '0.5rem 0.75rem', 
                border: '1px solid #d1d5db', 
                borderRadius: '0.5rem', 
                fontSize: '0.875rem',
                outline: 'none'
              }}
              placeholder="Describe your trading strategy..."
              disabled={loading}
            />
            <button 
              type="submit" 
              disabled={loading || !nlInput.trim()} 
              className="chat-send-btn"
              style={{ 
                padding: '0.5rem 1rem', 
                backgroundColor: loading || !nlInput.trim() ? '#d1d5db' : '#3b82f6',
                color: 'white', 
                fontWeight: '500', 
                borderRadius: '0.5rem', 
                border: 'none', 
                cursor: loading || !nlInput.trim() ? 'not-allowed' : 'pointer',
                transition: 'background-color 0.2s'
              }}
            >
              {loading ? 'Running...' : 'Send'}
            </button>
          </form>
        </div>

        {/* Backtest Processing State */}
        {processingBacktest && (
          <div className="loading-container">
            <div className="loading-content">
              <div className="loading-dot"></div>
              <div className="loading-dot" style={{ animationDelay: '0.1s' }}></div>
              <div className="loading-dot" style={{ animationDelay: '0.2s' }}></div>
            </div>
          </div>
        )}

        {/* Results */}
        {!loading && !processingBacktest && data && (
          <div 
            className="content-section"
            style={{ display: 'flex', flexDirection: 'column', gap: '3rem' }}
          >
            {/* Metrics Grid */}
            <div 
              className="card"
              style={{ 
                backgroundColor: 'white', 
                borderRadius: '0.75rem', 
                boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)', 
                padding: '2rem',
                margin: '1rem 0'
              }}
            >
              <h2 
                className="section-title"
                style={{ 
                  fontSize: '1.5rem', 
                  fontWeight: '700', 
                  marginBottom: '1.5rem', 
                  color: '#111827' 
                }}
              >
                Performance Metrics
              </h2>
              <div 
                className="metrics-responsive"
              >
                {metrics.map(({ label, value, format, type, className }) => (
                  <div 
                    key={label} 
                    className="metric-card"
                    style={{ 
                      backgroundColor: '#f9fafb', 
                      padding: '1rem', 
                      borderRadius: '0.5rem' 
                    }}
                  >
                    <div 
                      className="metric-label"
                      style={{ 
                        fontSize: '0.875rem', 
                        color: '#4b5563',
                        marginBottom: '0.5rem'
                      }}
                    >
                      {label}
                    </div>
                    <div 
                      className={className || getMetricClassName(value, type)}
                      style={{ 
                        fontSize: '1.25rem', 
                        fontWeight: '700',
                        color: className?.includes('positive') ? '#059669' : 
                              className?.includes('negative') ? '#dc2626' :
                              className?.includes('info') ? '#2563eb' : '#111827'
                      }}
                    >
                      {formatValue(value, format)}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Charts */}
            <div 
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(1, minmax(0, 1fr))',
                gap: '2rem'
              }}
              className="charts-responsive"
            >
              <div 
                className="chart-container"
                style={{ 
                  backgroundColor: 'white', 
                  borderRadius: '0.75rem', 
                  padding: '2rem', 
                  boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
                  margin: '1rem 0'
                }}
              >
                <h2 
                  className="section-title"
                  style={{ 
                    fontSize: '1.5rem', 
                    fontWeight: '700', 
                    marginBottom: '1.5rem', 
                    color: '#111827' 
                  }}
                >
                  Equity Curve
                </h2>
                <div 
                  className="chart-wrapper"
                  style={{ height: '18rem' }}
                >
                  {equityChart && <Line data={equityChart} options={{ maintainAspectRatio: false }} />}
                </div>
              </div>

              <div 
                className="chart-container"
                style={{ 
                  backgroundColor: 'white', 
                  borderRadius: '0.75rem', 
                  padding: '2rem', 
                  boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
                  margin: '1rem 0'
                }}
              >
                <h2 
                  className="section-title"
                  style={{ 
                    fontSize: '1.5rem', 
                    fontWeight: '700', 
                    marginBottom: '1.5rem', 
                    color: '#111827' 
                  }}
                >
                  Drawdown (%)
                </h2>
                <div 
                  className="chart-wrapper"
                  style={{ height: '18rem' }}
                >
                  {drawdownChart && <Line data={drawdownChart} options={{ maintainAspectRatio: false }} />}
                </div>
              </div>
            </div>

            {/* Indicators */}
            {indicatorCharts.length > 0 && (
              <div 
                className="card"
                style={{ 
                  backgroundColor: 'white', 
                  borderRadius: '0.5rem', 
                  boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)', 
                  padding: '1.5rem' 
                }}
              >
                <h2 
                  className="section-title"
                  style={{ 
                    fontSize: '1.5rem', 
                    fontWeight: '700', 
                    marginBottom: '1.5rem', 
                    color: '#111827' 
                  }}
                >
                  Indicators
                </h2>
                <div 
                  className="indicators-grid"
                >
                  {indicatorCharts.map(({ name, chart }) => (
                    <div 
                      key={name} 
                      className="rounded-lg p-4"
                      style={{ 
                        borderRadius: '0.5rem', 
                        padding: '1rem' 
                      }}
                    >
                      <h3 
                        className="subsection-title"
                        style={{ 
                          fontSize: '1.125rem', 
                          fontWeight: '600', 
                          marginBottom: '0.75rem', 
                          color: '#111827' 
                        }}
                      >
                        {name}
                      </h3>
                      <div 
                        className="chart-wrapper-sm"
                        style={{ height: '16rem' }}
                      >
                        <Line data={chart} options={{ maintainAspectRatio: false }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Signals */}
            {signalCharts.length > 0 && (
              <div 
                className="card"
                style={{ 
                  backgroundColor: 'white', 
                  borderRadius: '0.5rem', 
                  boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)', 
                  padding: '1.5rem' 
                }}
              >
                <h2 
                  className="section-title"
                  style={{ 
                    fontSize: '1.5rem', 
                    fontWeight: '700', 
                    marginBottom: '1.5rem', 
                    color: '#111827' 
                  }}
                >
                  Signals
                </h2>
                <div 
                  className="indicators-grid"
                >
                  {signalCharts.map(({ name, chart }) => (
                    <div 
                      key={name} 
                      className="border border-gray-200 dark:border-gray-700 rounded-lg p-4"
                      style={{ 
                        border: '1px solid #e5e7eb',
                        borderRadius: '0.5rem', 
                        padding: '1rem' 
                      }}
                    >
                      <h3 
                        className="subsection-title"
                        style={{ 
                          fontSize: '1.125rem', 
                          fontWeight: '600', 
                          marginBottom: '0.75rem', 
                          color: '#111827' 
                        }}
                      >
                        {name}
                      </h3>
                      <div 
                        className="chart-wrapper-sm"
                        style={{ height: '16rem' }}
                      >
                        <Line data={chart} options={{ maintainAspectRatio: false }} />
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