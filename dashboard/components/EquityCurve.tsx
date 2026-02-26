'use client'

import React, { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Area, AreaChart } from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface PnLDataPoint {
  timestamp: string
  pnl: number
  cumulative: number
}

export function EquityCurve() {
  const [data, setData] = useState<PnLDataPoint[]>([])
  const [timeframe, setTimeframe] = useState<'1H' | '24H' | '7D' | 'ALL'>('24H')
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchPnLData = async () => {
      try {
        const response = await fetch(`/api/pnl-history?timeframe=${timeframe}`)
        const result = await response.json()
        if (result.success) {
          setData(result.data)
        }
      } catch (error) {
        console.error('Failed to fetch PnL data:', error)
      } finally {
        setIsLoading(false)
      }
    }

    fetchPnLData()
    const interval = setInterval(fetchPnLData, 30000) // Update every 30 seconds

    return () => clearInterval(interval)
  }, [timeframe])

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value)
  }

  const formatTooltipValue = (value: number, name: string) => {
    if (name === 'PnL') return formatCurrency(value)
    if (name === 'Cumulative') return formatCurrency(value)
    return value
  }

  const formatXAxisTick = (tickItem: string) => {
    const date = new Date(tickItem)
    if (timeframe === '1H') {
      return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    } else if (timeframe === '24H') {
      return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    } else {
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    }
  }

  const latestPnL = data.length > 0 ? data[data.length - 1].cumulative : 0
  const isProfit = latestPnL >= 0

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-xl font-bold">Equity Curve</CardTitle>
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
        <div className="mt-2 flex items-center gap-4">
          <div>
            <span className="text-sm text-gray-500">Total PnL: </span>
            <span className={`text-lg font-semibold ${isProfit ? 'text-green-600' : 'text-red-600'}`}>
              {formatCurrency(latestPnL)}
            </span>
          </div>
          {data.length > 1 && (
            <div>
              <span className="text-sm text-gray-500">Change: </span>
              <span className={`text-lg font-semibold ${isProfit ? 'text-green-600' : 'text-red-600'}`}>
                {((latestPnL / 100) * 100).toFixed(2)}%
              </span>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          </div>
        ) : data.length === 0 ? (
          <div className="flex items-center justify-center h-64 text-gray-500">
            No PnL data available
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={350}>
            <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <defs>
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
                tickFormatter={(value) => `$${value}`}
                stroke="#6b7280"
                style={{ fontSize: '12px' }}
              />
              <Tooltip
                formatter={formatTooltipValue}
                labelFormatter={(label) => new Date(label).toLocaleString()}
                contentStyle={{
                  backgroundColor: 'rgba(255, 255, 255, 0.95)',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px'
                }}
              />
              <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />
              <Area
                type="monotone"
                dataKey="cumulative"
                stroke={isProfit ? '#10b981' : '#ef4444'}
                fill={isProfit ? 'url(#colorProfit)' : 'url(#colorLoss)'}
                strokeWidth={2}
                name="Cumulative"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  )
}