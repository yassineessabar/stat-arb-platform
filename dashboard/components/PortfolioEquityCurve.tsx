'use client'

import React, { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Area, AreaChart } from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface PortfolioDataPoint {
  timestamp: string
  portfolioValue: number
  pnl: number
  cumulative: number
}

interface PortfolioEquityCurveProps {
  mode: 'paper' | 'live'
  marginBalance: number
  unrealizedPnL: number
  realizedPnL: number
}

export function PortfolioEquityCurve({ mode, marginBalance, unrealizedPnL, realizedPnL }: PortfolioEquityCurveProps) {
  const [data, setData] = useState<PortfolioDataPoint[]>([])
  const [timeframe, setTimeframe] = useState<'1H' | '24H' | '7D' | 'ALL'>('24H')
  const [isLoading, setIsLoading] = useState(true)
  const [historicalData, setHistoricalData] = useState<PortfolioDataPoint[]>([])

  useEffect(() => {
    const fetchPortfolioData = async () => {
      try {
        const response = await fetch(`/api/portfolio-history?timeframe=${timeframe}&mode=${mode}`)
        const result = await response.json()
        if (result.success) {
          setHistoricalData(result.data)
        }
      } catch (error) {
        console.error('Failed to fetch portfolio data:', error)
        // Generate sample data if API fails
        generateSampleData()
      } finally {
        setIsLoading(false)
      }
    }

    fetchPortfolioData()
    const interval = setInterval(fetchPortfolioData, 30000) // Update every 30 seconds

    return () => clearInterval(interval)
  }, [timeframe, mode])

  useEffect(() => {
    // Combine historical data with current live values
    const currentPortfolioValue = marginBalance + unrealizedPnL
    const currentTime = new Date().toISOString()

    if (historicalData.length > 0) {
      const lastPoint = historicalData[historicalData.length - 1]
      const updatedData = [...historicalData]

      // Update the last point or add new one if time has passed
      const lastTime = new Date(lastPoint.timestamp)
      const timeDiff = new Date().getTime() - lastTime.getTime()

      if (timeDiff > 60000) { // More than 1 minute passed
        updatedData.push({
          timestamp: currentTime,
          portfolioValue: currentPortfolioValue,
          pnl: unrealizedPnL + realizedPnL,
          cumulative: realizedPnL + unrealizedPnL
        })
      } else {
        // Update last point with current values
        updatedData[updatedData.length - 1] = {
          ...lastPoint,
          portfolioValue: currentPortfolioValue,
          pnl: unrealizedPnL + realizedPnL,
          cumulative: realizedPnL + unrealizedPnL
        }
      }

      setData(updatedData)
    } else {
      // No historical data, create initial point
      setData([{
        timestamp: currentTime,
        portfolioValue: currentPortfolioValue,
        pnl: unrealizedPnL + realizedPnL,
        cumulative: realizedPnL + unrealizedPnL
      }])
    }
  }, [historicalData, marginBalance, unrealizedPnL, realizedPnL])

  const generateSampleData = () => {
    const now = new Date()
    const sampleData: PortfolioDataPoint[] = []
    const baseValue = marginBalance || 10000
    let cumulative = 0

    const points = timeframe === '1H' ? 12 : timeframe === '24H' ? 24 : timeframe === '7D' ? 168 : 720
    const interval = timeframe === '1H' ? 5 : timeframe === '24H' ? 60 : timeframe === '7D' ? 60 : 60

    for (let i = points; i >= 0; i--) {
      const timestamp = new Date(now.getTime() - (i * interval * 60 * 1000))
      const pnl = (Math.random() - 0.48) * baseValue * 0.01 // ~0.5% variations
      cumulative += pnl

      sampleData.push({
        timestamp: timestamp.toISOString(),
        portfolioValue: baseValue + cumulative,
        pnl: pnl,
        cumulative: cumulative
      })
    }

    // Add current real value as last point
    sampleData.push({
      timestamp: now.toISOString(),
      portfolioValue: marginBalance + unrealizedPnL,
      pnl: unrealizedPnL + realizedPnL,
      cumulative: realizedPnL + unrealizedPnL
    })

    setHistoricalData(sampleData)
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value)
  }

  const formatTooltipValue = (value: number, name: string) => {
    if (name === 'Portfolio Value' || name === 'PnL') return formatCurrency(value)
    return value
  }

  const formatXAxisTick = (tickItem: string) => {
    const date = new Date(tickItem)
    if (timeframe === '1H') {
      return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    } else if (timeframe === '24H') {
      return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    } else if (timeframe === '7D') {
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    } else {
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    }
  }

  const currentPortfolioValue = marginBalance + unrealizedPnL
  const totalPnL = unrealizedPnL + realizedPnL
  const isProfit = totalPnL >= 0
  const returnPercentage = marginBalance > 0 ? (totalPnL / marginBalance) * 100 : 0

  // Calculate statistics
  const maxValue = data.length > 0 ? Math.max(...data.map(d => d.portfolioValue)) : currentPortfolioValue
  const minValue = data.length > 0 ? Math.min(...data.map(d => d.portfolioValue)) : currentPortfolioValue
  const maxDrawdown = maxValue > 0 ? ((maxValue - minValue) / maxValue) * 100 : 0

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-xl font-bold">
              Portfolio Equity Curve
              <span className={`ml-3 text-sm font-normal px-2 py-1 rounded ${
                mode === 'paper'
                  ? 'bg-orange-100 text-orange-700'
                  : 'bg-red-100 text-red-700'
              }`}>
                {mode === 'paper' ? '🟠 PAPER' : '🔴 LIVE'}
              </span>
            </CardTitle>
          </div>
          <div className="flex gap-2">
            {(['1H', '24H', '7D', 'ALL'] as const).map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`px-3 py-1 text-sm rounded-md transition-colors ${
                  timeframe === tf
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-4 grid grid-cols-4 gap-4">
          <div>
            <span className="text-sm text-gray-500">Portfolio Value</span>
            <div className="text-xl font-semibold">
              {formatCurrency(currentPortfolioValue)}
            </div>
          </div>
          <div>
            <span className="text-sm text-gray-500">Total P&L</span>
            <div className={`text-xl font-semibold ${isProfit ? 'text-green-600' : 'text-red-600'}`}>
              {isProfit && '+'}{formatCurrency(totalPnL)}
            </div>
          </div>
          <div>
            <span className="text-sm text-gray-500">Return</span>
            <div className={`text-xl font-semibold ${isProfit ? 'text-green-600' : 'text-red-600'}`}>
              {returnPercentage >= 0 && '+'}{returnPercentage.toFixed(2)}%
            </div>
          </div>
          <div>
            <span className="text-sm text-gray-500">Max Drawdown</span>
            <div className="text-xl font-semibold text-orange-600">
              -{maxDrawdown.toFixed(2)}%
            </div>
          </div>
        </div>

        <div className="mt-2 flex items-center gap-6 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-green-500 rounded-full"></div>
            <span className="text-gray-600">Unrealized: </span>
            <span className={`font-medium ${unrealizedPnL >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatCurrency(unrealizedPnL)}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
            <span className="text-gray-600">Realized: </span>
            <span className={`font-medium ${realizedPnL >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatCurrency(realizedPnL)}
            </span>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          </div>
        ) : data.length === 0 ? (
          <div className="flex items-center justify-center h-64 text-gray-500">
            No portfolio data available
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={350}>
            <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="colorPortfolio" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                </linearGradient>
                <linearGradient id="colorProfit" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                </linearGradient>
                <linearGradient id="colorLoss" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey="timestamp"
                tickFormatter={formatXAxisTick}
                stroke="#6b7280"
                style={{ fontSize: '12px' }}
              />
              <YAxis
                tickFormatter={(value) => `$${(value / 1000).toFixed(1)}k`}
                stroke="#6b7280"
                style={{ fontSize: '12px' }}
                domain={['dataMin - 100', 'dataMax + 100']}
              />
              <Tooltip
                formatter={formatTooltipValue}
                labelFormatter={(label) => new Date(label).toLocaleString()}
                contentStyle={{
                  backgroundColor: 'rgba(255, 255, 255, 0.95)',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  padding: '12px'
                }}
              />
              <ReferenceLine
                y={marginBalance}
                stroke="#9ca3af"
                strokeDasharray="3 3"
                label={{ value: "Initial", position: "left", style: { fontSize: 10, fill: '#9ca3af' } }}
              />
              <Area
                type="monotone"
                dataKey="portfolioValue"
                stroke="#3b82f6"
                fill="url(#colorPortfolio)"
                strokeWidth={2}
                name="Portfolio Value"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  )
}