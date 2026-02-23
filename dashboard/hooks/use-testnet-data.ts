import { useState, useEffect, useCallback } from 'react';
import { testnetAPI, Position, Trade, AccountMetrics, RiskMetrics } from '@/lib/api-client';

// Hook for fetching positions with auto-refresh
export function usePositions(refreshInterval: number = 5000) {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPositions = useCallback(async () => {
    try {
      const data = await testnetAPI.getPositions();
      setPositions(data);
      setError(null);
    } catch (err) {
      setError('Failed to fetch positions');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, refreshInterval);
    return () => clearInterval(interval);
  }, [fetchPositions, refreshInterval]);

  return { positions, loading, error, refresh: fetchPositions };
}

// Hook for fetching trades
export function useTrades(refreshInterval: number = 10000) {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTrades = useCallback(async () => {
    try {
      const data = await testnetAPI.getTrades();
      setTrades(data);
      setError(null);
    } catch (err) {
      setError('Failed to fetch trades');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTrades();
    const interval = setInterval(fetchTrades, refreshInterval);
    return () => clearInterval(interval);
  }, [fetchTrades, refreshInterval]);

  return { trades, loading, error, refresh: fetchTrades };
}

// Hook for account metrics
export function useAccountMetrics(refreshInterval: number = 5000) {
  const [metrics, setMetrics] = useState<AccountMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMetrics = useCallback(async () => {
    try {
      const data = await testnetAPI.getAccountMetrics();
      setMetrics(data);
      setError(null);
    } catch (err) {
      setError('Failed to fetch metrics');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, refreshInterval);
    return () => clearInterval(interval);
  }, [fetchMetrics, refreshInterval]);

  return { metrics, loading, error, refresh: fetchMetrics };
}

// Hook for risk metrics
export function useRiskMetrics(refreshInterval: number = 5000) {
  const [riskMetrics, setRiskMetrics] = useState<RiskMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRiskMetrics = useCallback(async () => {
    try {
      const data = await testnetAPI.getRiskMetrics();
      setRiskMetrics(data);
      setError(null);
    } catch (err) {
      setError('Failed to fetch risk metrics');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRiskMetrics();
    const interval = setInterval(fetchRiskMetrics, refreshInterval);
    return () => clearInterval(interval);
  }, [fetchRiskMetrics, refreshInterval]);

  return { riskMetrics, loading, error, refresh: fetchRiskMetrics };
}

// Hook for WebSocket real-time updates
export function useRealtimeUpdates() {
  const [connected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<any>(null);

  useEffect(() => {
    const handleMessage = (data: any) => {
      setLastUpdate(data);

      // Handle different message types
      switch (data.type) {
        case 'position_update':
          // Update positions
          break;
        case 'trade_executed':
          // New trade executed
          break;
        case 'metrics_update':
          // Metrics updated
          break;
        default:
          console.log('Unknown message type:', data.type);
      }
    };

    // Subscribe to connection changes
    const unsubscribe = testnetAPI.onConnectionChange(setConnected);

    // Attempt to connect
    testnetAPI.connectWebSocket(handleMessage);

    return () => {
      unsubscribe();
      testnetAPI.disconnectWebSocket();
    };
  }, []);

  return { connected, lastUpdate };
}

// Combined hook for all execution data
export function useExecutionData() {
  const { positions, loading: positionsLoading, error: positionsError } = usePositions();
  const { trades, loading: tradesLoading, error: tradesError } = useTrades();
  const { metrics, loading: metricsLoading, error: metricsError } = useAccountMetrics();
  const { riskMetrics, loading: riskLoading, error: riskError } = useRiskMetrics();
  const { connected } = useRealtimeUpdates();

  return {
    positions,
    trades,
    metrics,
    riskMetrics,
    loading: positionsLoading || tradesLoading || metricsLoading || riskLoading,
    error: positionsError || tradesError || metricsError || riskError,
    wsConnected: connected,
  };
}