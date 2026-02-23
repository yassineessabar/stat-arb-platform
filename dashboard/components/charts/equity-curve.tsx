"use client";

import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { format } from 'date-fns';

interface EquityCurveProps {
  strategyData: Array<{
    date: string;
    strategy: number;
    btc: number;
  }>;
}

export function EquityCurve({ strategyData }: EquityCurveProps) {
  const formatTooltip = (value: any, name: string) => {
    if (typeof value === 'number') {
      return [`${(value * 100).toFixed(1)}%`, name === 'strategy' ? 'Strategy' : 'BTC Benchmark'];
    }
    return [value, name];
  };

  const formatDate = (tickItem: string) => {
    try {
      const date = new Date(tickItem);
      return format(date, 'MMM dd');
    } catch {
      return tickItem;
    }
  };

  return (
    <ResponsiveContainer width="100%" height={400}>
      <LineChart
        data={strategyData}
        margin={{
          top: 20,
          right: 30,
          left: 20,
          bottom: 20,
        }}
      >
        <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
        <XAxis
          dataKey="date"
          tickFormatter={formatDate}
          tick={{ fontSize: 12 }}
          interval="preserveStartEnd"
        />
        <YAxis
          tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
          tick={{ fontSize: 12 }}
        />
        <Tooltip
          formatter={formatTooltip}
          labelFormatter={(label) => `Date: ${formatDate(label)}`}
          contentStyle={{
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            border: 'none',
            borderRadius: '8px',
            color: 'white',
            fontSize: '12px'
          }}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="strategy"
          stroke="#2563eb"
          strokeWidth={2.5}
          dot={false}
          name="Strategy"
          connectNulls={false}
        />
        <Line
          type="monotone"
          dataKey="btc"
          stroke="#f59e0b"
          strokeWidth={2}
          strokeDasharray="5 5"
          dot={false}
          name="BTC Benchmark"
          connectNulls={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}