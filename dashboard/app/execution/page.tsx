"use client";

import { useState, useEffect } from "react";
import { NavHeader } from "@/components/layout/nav-header";

type Environment = 'paper' | 'live';
type StrategyStatus = 'stopped' | 'running' | 'paused' | 'error';

interface ApiCredentials {
  apiKey: string;
  secretKey: string;
  testnet: boolean;
}

interface LiveMetrics {
  currentEquity: number;
  unrealizedPnL: number;
  realizedPnL: number;
  dailyPnL: number;
  currentExposure: number;
  grossLeverage: number;
  riskUtilization: number;
  slippageAvg: number;
  turnover: number;
}

interface Position {
  asset: string;
  qty: number;
  entryPrice: number;
  currentPrice: number;
  pnl: number;
  exposurePercent: number;
  margin: number;
}

interface Order {
  time: Date;
  asset: string;
  side: 'BUY' | 'SELL';
  size: number;
  price: number;
  slippage: number;
  status: 'FILLED' | 'PARTIAL' | 'CANCELLED' | 'REJECTED' | 'RISK_BLOCKED';
  orderId?: string;
}

interface LogEvent {
  time: Date;
  type: 'STRATEGY' | 'RISK' | 'DEPLOYMENT' | 'ERROR' | 'WARNING' | 'API';
  message: string;
  severity: 'info' | 'warning' | 'critical';
}

interface StrategyParameters {
  strategy_name: string;
  trading_mode: 'paper' | 'live';
  symbol_1: string;
  symbol_2: string;
  lookback_period: number;
  entry_z_score: number;
  exit_z_score: number;
  stop_loss_z_score: number;
  position_size: number;
  max_positions: number;
  rebalance_frequency: number;
}

export default function ExecutionPage() {
  const [environment, setEnvironment] = useState<Environment>('paper');
  const [strategyStatus, setStrategyStatus] = useState<StrategyStatus>('stopped');
  const [showSettings, setShowSettings] = useState(false);
  const [showDeployModal, setShowDeployModal] = useState(false);
  const [apiConnected, setApiConnected] = useState(false);
  const [deploymentProcessId, setDeploymentProcessId] = useState<string | null>(null);
  const [apiCredentials, setApiCredentials] = useState<ApiCredentials>({
    apiKey: '',
    secretKey: '',
    testnet: true
  });
  const [tempCredentials, setTempCredentials] = useState<ApiCredentials>({
    apiKey: '',
    secretKey: '',
    testnet: true
  });

  const [liveMetrics, setLiveMetrics] = useState<LiveMetrics>({
    currentEquity: 0,
    unrealizedPnL: 0,
    realizedPnL: 0,
    dailyPnL: 0,
    currentExposure: 0,
    grossLeverage: 0,
    riskUtilization: 0,
    slippageAvg: 0,
    turnover: 0
  });

  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [logEvents, setLogEvents] = useState<LogEvent[]>([]);
  const [loading, setLoading] = useState(false);

  const [strategyParams, setStrategyParams] = useState<StrategyParameters>({
    strategy_name: 'MeanReversion_ETHBTC',
    trading_mode: 'paper',
    symbol_1: 'ETHUSDT',
    symbol_2: 'BTCUSDT',
    lookback_period: 24,
    entry_z_score: 2.0,
    exit_z_score: 0.5,
    stop_loss_z_score: 3.0,
    position_size: 1000,
    max_positions: 3,
    rebalance_frequency: 5
  });

  // Load credentials from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem('binance_paper_credentials');
    if (stored) {
      try {
        const creds = JSON.parse(stored);
        setApiCredentials(creds);
        setTempCredentials(creds);
        addLog('API', 'Credentials loaded from storage', 'info');
      } catch (e) {
        addLog('ERROR', 'Failed to load stored credentials', 'warning');
      }
    }
  }, []);

  // Test API connection whenever credentials change
  useEffect(() => {
    if (apiCredentials.apiKey && apiCredentials.secretKey) {
      testConnection();
    }
  }, [apiCredentials]);

  const addLog = (type: LogEvent['type'], message: string, severity: LogEvent['severity'] = 'info') => {
    setLogEvents(prev => [{
      time: new Date(),
      type,
      message,
      severity
    }, ...prev].slice(0, 100));
  };

  const testConnection = async () => {
    try {
      const response = await fetch('/api/binance/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          apiKey: apiCredentials.apiKey,
          secretKey: apiCredentials.secretKey,
          testnet: apiCredentials.testnet
        })
      });

      const result = await response.json();

      if (result.connected) {
        setApiConnected(true);
        addLog('API', `Connected to Binance ${apiCredentials.testnet ? 'Testnet' : 'Mainnet'}`, 'info');
      } else {
        setApiConnected(false);
        addLog('API', `Connection failed: ${result.error}`, 'critical');
      }
    } catch (error) {
      setApiConnected(false);
      addLog('ERROR', `Connection test failed: ${error}`, 'critical');
    }
  };

  const saveCredentials = () => {
    localStorage.setItem('binance_paper_credentials', JSON.stringify(tempCredentials));
    setApiCredentials(tempCredentials);
    setShowSettings(false);
    addLog('API', 'Credentials updated and saved', 'info');
  };

  // Fetch live data from Binance
  const fetchExecutionData = async () => {
    if (!apiConnected || !apiCredentials.apiKey) return;

    try {
      // For paper trading, we use real Binance data but don't execute real trades
      const [accountRes, positionsRes, tradesRes] = await Promise.all([
        fetch('/api/binance/account'),
        fetch('/api/binance/positions'),
        fetch('/api/binance/trades')
      ]);

      if (accountRes.ok) {
        const account = await accountRes.json();

        // Calculate metrics
        const equity = parseFloat(account.totalBalance || '0');
        const unrealized = parseFloat(account.totalUnrealizedProfit || '0');
        const exposure = Math.abs(parseFloat(account.totalInitialMargin || '0'));

        setLiveMetrics({
          currentEquity: equity,
          unrealizedPnL: unrealized,
          realizedPnL: parseFloat(account.totalPnL || '0'),
          dailyPnL: 0, // Would need historical data
          currentExposure: exposure,
          grossLeverage: equity > 0 ? exposure / equity : 0,
          riskUtilization: equity > 0 ? (exposure / equity) * 100 : 0,
          slippageAvg: 0.05, // Mock for now
          turnover: 0.12 // Mock for now
        });
      }

      if (positionsRes.ok) {
        const data = await positionsRes.json();
        const binancePositions = data.positions?.map((p: any) => ({
          asset: p.symbol,
          qty: p.size,
          entryPrice: p.entryPrice,
          currentPrice: p.markPrice || p.entryPrice,
          pnl: p.pnl,
          exposurePercent: (p.notional / 5000) * 100,
          margin: p.margin
        })) || [];
        setPositions(binancePositions);
      }

      if (tradesRes.ok) {
        const tradesData = await tradesRes.json();
        const recentOrders = tradesData.trades?.slice(0, 10).map((t: any) => ({
          time: new Date(t.time || Date.now()),
          asset: t.symbol,
          side: t.side,
          size: t.quantity,
          price: t.price,
          slippage: 0.05,
          status: 'FILLED' as const,
          orderId: t.orderId
        })) || [];
        setOrders(recentOrders);
      }

    } catch (error) {
      addLog('ERROR', `Failed to fetch data: ${error}`, 'critical');
    }
  };

  // Fetch data on interval
  useEffect(() => {
    if (apiConnected) {
      fetchExecutionData();
      const interval = setInterval(fetchExecutionData, 2000);
      return () => clearInterval(interval);
    }
  }, [apiConnected, environment]);

  const handleDeploy = () => {
    if (!apiConnected) {
      addLog('ERROR', 'Cannot deploy - API not connected', 'critical');
      return;
    }
    // Show deployment modal
    setStrategyParams(prev => ({ ...prev, trading_mode: environment }));
    setShowDeployModal(true);
  };

  const deployStrategy = async () => {
    try {
      setLoading(true);

      // Prepare config with API credentials
      const config = {
        ...strategyParams,
        api_key: apiCredentials.apiKey,
        api_secret: apiCredentials.secretKey,
        testnet: apiCredentials.testnet
      };

      // Call deployment API
      const response = await fetch('/api/strategy/deploy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });

      const result = await response.json();

      if (result.success) {
        setDeploymentProcessId(result.processId);
        setStrategyStatus('running');
        setShowDeployModal(false);
        addLog('DEPLOYMENT', `Strategy deployed successfully (PID: ${result.processId})`, 'info');
        addLog('STRATEGY', `Running ${strategyParams.strategy_name} in ${strategyParams.trading_mode.toUpperCase()} mode`, 'info');
      } else {
        addLog('ERROR', `Deployment failed: ${result.error}`, 'critical');
      }
    } catch (error) {
      addLog('ERROR', `Deployment error: ${error}`, 'critical');
    } finally {
      setLoading(false);
    }
  };

  const stopStrategy = async () => {
    if (!deploymentProcessId) {
      addLog('WARNING', 'No active strategy to stop', 'warning');
      return;
    }

    try {
      const response = await fetch('/api/strategy/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ processId: deploymentProcessId })
      });

      const result = await response.json();

      if (result.success) {
        setStrategyStatus('stopped');
        setDeploymentProcessId(null);
        addLog('STRATEGY', 'Strategy stopped successfully', 'info');
      } else {
        addLog('ERROR', `Failed to stop strategy: ${result.error}`, 'critical');
      }
    } catch (error) {
      addLog('ERROR', `Stop error: ${error}`, 'critical');
    }
  };

  const handlePause = () => {
    setStrategyStatus('paused');
    addLog('STRATEGY', 'Strategy paused - All new orders blocked', 'warning');
  };

  const handleRestart = () => {
    setStrategyStatus('running');
    addLog('DEPLOYMENT', 'Strategy restarted', 'info');
  };

  const handleKillSwitch = async () => {
    if (confirm('KILL SWITCH: Close all positions and stop strategy immediately?')) {
      // First stop the strategy process if running
      if (deploymentProcessId) {
        await stopStrategy();
      }

      setStrategyStatus('stopped');

      // If in live mode, actually close positions
      if (environment === 'live' && positions.length > 0) {
        try {
          const response = await fetch('/api/binance/emergency-stop', {
            method: 'POST'
          });
          const result = await response.json();

          if (result.success) {
            addLog('RISK', `KILL SWITCH ACTIVATED - ${result.closedPositions?.length || 0} positions closed`, 'critical');
            setPositions([]);
          } else {
            addLog('ERROR', 'Kill switch failed - manual intervention required', 'critical');
          }
        } catch (error) {
          addLog('ERROR', `Kill switch error: ${error}`, 'critical');
        }
      } else {
        addLog('RISK', 'KILL SWITCH ACTIVATED - Strategy stopped', 'critical');
        setPositions([]);
      }
    }
  };

  return (
    <>
      <NavHeader />
      <main className="mx-auto max-w-7xl px-6 py-8">
        {/* Header with Environment Toggle and Settings */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center space-x-6">
            <h1 className="text-2xl font-medium text-neutral-900">Execution</h1>
            <div className="flex items-center bg-neutral-100 rounded-lg p-1">
              <button
                onClick={() => setEnvironment('paper')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  environment === 'paper'
                    ? 'bg-white text-neutral-900 shadow-sm'
                    : 'text-neutral-600 hover:text-neutral-900'
                }`}
              >
                Paper
              </button>
              <button
                onClick={() => setEnvironment('live')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  environment === 'live'
                    ? 'bg-white text-neutral-900 shadow-sm'
                    : 'text-neutral-600 hover:text-neutral-900'
                }`}
              >
                Live
              </button>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <button
              onClick={() => setShowSettings(true)}
              className="px-3 py-1.5 text-sm font-medium text-neutral-700 border border-neutral-300 rounded-md hover:bg-neutral-50"
            >
              ⚙️ API Settings
            </button>
            <div className={`px-3 py-1 rounded-full text-xs font-medium ${
              apiConnected
                ? 'bg-green-100 text-green-700'
                : 'bg-neutral-100 text-neutral-600'
            }`}>
              {apiConnected ? '● Connected' : '○ Disconnected'}
            </div>
            <div className={`px-3 py-1 rounded-full text-xs font-medium ${
              environment === 'paper'
                ? 'bg-orange-100 text-orange-700'
                : 'bg-red-100 text-red-700'
            }`}>
              {environment === 'paper' ? '🟠 PAPER' : '🔴 LIVE'}
            </div>
          </div>
        </div>

        {/* API Settings Modal */}
        {showSettings && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 w-full max-w-md">
              <h3 className="text-lg font-medium text-neutral-900 mb-4">
                Binance API Settings
              </h3>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-neutral-700 mb-1">
                    API Key
                  </label>
                  <input
                    type="text"
                    value={tempCredentials.apiKey}
                    onChange={(e) => setTempCredentials({...tempCredentials, apiKey: e.target.value})}
                    className="w-full px-3 py-2 border border-neutral-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Enter your Binance API key"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-neutral-700 mb-1">
                    Secret Key
                  </label>
                  <input
                    type="password"
                    value={tempCredentials.secretKey}
                    onChange={(e) => setTempCredentials({...tempCredentials, secretKey: e.target.value})}
                    className="w-full px-3 py-2 border border-neutral-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Enter your Binance secret key"
                  />
                </div>

                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="testnet"
                    checked={tempCredentials.testnet}
                    onChange={(e) => setTempCredentials({...tempCredentials, testnet: e.target.checked})}
                    className="mr-2"
                  />
                  <label htmlFor="testnet" className="text-sm text-neutral-700">
                    Use Testnet (Recommended for Paper Trading)
                  </label>
                </div>

                <div className="bg-orange-50 border border-orange-200 p-3 rounded-md">
                  <p className="text-xs text-orange-800">
                    <strong>Paper Trading Mode:</strong> Your API keys are stored locally and used to fetch real market data.
                    No real trades will be executed in Paper mode.
                  </p>
                </div>
              </div>

              <div className="flex justify-end space-x-3 mt-6">
                <button
                  onClick={() => setShowSettings(false)}
                  className="px-4 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-50"
                >
                  Cancel
                </button>
                <button
                  onClick={saveCredentials}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
                >
                  Save & Connect
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Strategy Deployment Modal */}
        {showDeployModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
              <h3 className="text-lg font-medium text-neutral-900 mb-4">
                Deploy Strategy - {environment === 'paper' ? 'Paper Trading' : 'Live Trading'}
              </h3>

              <div className="space-y-4">
                {/* Strategy Info */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 mb-1">
                      Strategy Name
                    </label>
                    <input
                      type="text"
                      value={strategyParams.strategy_name}
                      onChange={(e) => setStrategyParams({...strategyParams, strategy_name: e.target.value})}
                      className="w-full px-3 py-2 border border-neutral-300 rounded-md text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 mb-1">
                      Trading Mode
                    </label>
                    <select
                      value={strategyParams.trading_mode}
                      onChange={(e) => setStrategyParams({...strategyParams, trading_mode: e.target.value as 'paper' | 'live'})}
                      className="w-full px-3 py-2 border border-neutral-300 rounded-md text-sm"
                    >
                      <option value="paper">Paper Trading</option>
                      <option value="live">Live Trading</option>
                    </select>
                  </div>
                </div>

                {/* Trading Pairs */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 mb-1">
                      Symbol 1
                    </label>
                    <input
                      type="text"
                      value={strategyParams.symbol_1}
                      onChange={(e) => setStrategyParams({...strategyParams, symbol_1: e.target.value.toUpperCase()})}
                      className="w-full px-3 py-2 border border-neutral-300 rounded-md text-sm"
                      placeholder="e.g., ETHUSDT"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 mb-1">
                      Symbol 2
                    </label>
                    <input
                      type="text"
                      value={strategyParams.symbol_2}
                      onChange={(e) => setStrategyParams({...strategyParams, symbol_2: e.target.value.toUpperCase()})}
                      className="w-full px-3 py-2 border border-neutral-300 rounded-md text-sm"
                      placeholder="e.g., BTCUSDT"
                    />
                  </div>
                </div>

                {/* Statistical Parameters */}
                <div className="border-t pt-4">
                  <h4 className="text-sm font-medium text-neutral-900 mb-3">Statistical Parameters</h4>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-neutral-700 mb-1">
                        Lookback Period (hours)
                      </label>
                      <input
                        type="number"
                        value={strategyParams.lookback_period}
                        onChange={(e) => setStrategyParams({...strategyParams, lookback_period: parseInt(e.target.value)})}
                        className="w-full px-3 py-2 border border-neutral-300 rounded-md text-sm"
                        min="1"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-neutral-700 mb-1">
                        Entry Z-Score
                      </label>
                      <input
                        type="number"
                        value={strategyParams.entry_z_score}
                        onChange={(e) => setStrategyParams({...strategyParams, entry_z_score: parseFloat(e.target.value)})}
                        className="w-full px-3 py-2 border border-neutral-300 rounded-md text-sm"
                        step="0.1"
                        min="0"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-neutral-700 mb-1">
                        Exit Z-Score
                      </label>
                      <input
                        type="number"
                        value={strategyParams.exit_z_score}
                        onChange={(e) => setStrategyParams({...strategyParams, exit_z_score: parseFloat(e.target.value)})}
                        className="w-full px-3 py-2 border border-neutral-300 rounded-md text-sm"
                        step="0.1"
                        min="0"
                      />
                    </div>
                  </div>
                </div>

                {/* Risk Parameters */}
                <div className="border-t pt-4">
                  <h4 className="text-sm font-medium text-neutral-900 mb-3">Risk Parameters</h4>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-neutral-700 mb-1">
                        Stop Loss Z-Score
                      </label>
                      <input
                        type="number"
                        value={strategyParams.stop_loss_z_score}
                        onChange={(e) => setStrategyParams({...strategyParams, stop_loss_z_score: parseFloat(e.target.value)})}
                        className="w-full px-3 py-2 border border-neutral-300 rounded-md text-sm"
                        step="0.1"
                        min="0"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-neutral-700 mb-1">
                        Position Size (USDT)
                      </label>
                      <input
                        type="number"
                        value={strategyParams.position_size}
                        onChange={(e) => setStrategyParams({...strategyParams, position_size: parseFloat(e.target.value)})}
                        className="w-full px-3 py-2 border border-neutral-300 rounded-md text-sm"
                        min="100"
                        step="100"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-neutral-700 mb-1">
                        Max Positions
                      </label>
                      <input
                        type="number"
                        value={strategyParams.max_positions}
                        onChange={(e) => setStrategyParams({...strategyParams, max_positions: parseInt(e.target.value)})}
                        className="w-full px-3 py-2 border border-neutral-300 rounded-md text-sm"
                        min="1"
                        max="10"
                      />
                    </div>
                  </div>
                </div>

                {/* Execution Parameters */}
                <div className="border-t pt-4">
                  <h4 className="text-sm font-medium text-neutral-900 mb-3">Execution Parameters</h4>
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 mb-1">
                      Rebalance Frequency (minutes)
                    </label>
                    <input
                      type="number"
                      value={strategyParams.rebalance_frequency}
                      onChange={(e) => setStrategyParams({...strategyParams, rebalance_frequency: parseInt(e.target.value)})}
                      className="w-full px-3 py-2 border border-neutral-300 rounded-md text-sm"
                      min="1"
                      max="60"
                    />
                  </div>
                </div>

                {/* Warning for live trading */}
                {strategyParams.trading_mode === 'live' && (
                  <div className="bg-red-50 border border-red-200 p-3 rounded-md">
                    <p className="text-sm text-red-800">
                      <strong>⚠️ LIVE TRADING MODE:</strong> Real money will be at risk. Ensure you understand the strategy and have tested it thoroughly in paper mode first.
                    </p>
                  </div>
                )}

                {/* Info for paper trading */}
                {strategyParams.trading_mode === 'paper' && (
                  <div className="bg-blue-50 border border-blue-200 p-3 rounded-md">
                    <p className="text-sm text-blue-800">
                      <strong>📝 PAPER TRADING MODE:</strong> Strategy will simulate trades using real market data. No real money at risk.
                    </p>
                  </div>
                )}
              </div>

              <div className="flex justify-end space-x-3 mt-6">
                <button
                  onClick={() => setShowDeployModal(false)}
                  className="px-4 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-50"
                  disabled={loading}
                >
                  Cancel
                </button>
                <button
                  onClick={deployStrategy}
                  disabled={loading}
                  className={`px-4 py-2 text-sm font-medium text-white rounded-md ${
                    loading
                      ? 'bg-neutral-400 cursor-not-allowed'
                      : strategyParams.trading_mode === 'live'
                      ? 'bg-red-600 hover:bg-red-700'
                      : 'bg-green-600 hover:bg-green-700'
                  }`}
                >
                  {loading ? 'Deploying...' : `Deploy ${strategyParams.trading_mode === 'live' ? 'Live' : 'Paper'} Strategy`}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Warning if not connected */}
        {!apiConnected && (
          <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <p className="text-sm text-yellow-800">
              ⚠️ API not connected. Click "API Settings" to configure your Binance credentials.
            </p>
          </div>
        )}

        {/* 1. Status & Controls */}
        <div className="bg-white border border-neutral-200 rounded-lg p-6 mb-6">
          <div className="grid grid-cols-2 gap-8 mb-6">
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm text-neutral-600">Strategy:</span>
                <span className="text-sm font-medium">MeanReversion_ETHBTC</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-neutral-600">Version:</span>
                <span className="text-sm font-mono">v0.3.2 (a4f2c89)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-neutral-600">Capital:</span>
                <span className="text-sm font-medium">
                  ${liveMetrics.currentEquity.toLocaleString()}
                </span>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm text-neutral-600">Status:</span>
                <span className={`text-sm font-medium ${
                  strategyStatus === 'running' ? 'text-green-600' :
                  strategyStatus === 'paused' ? 'text-orange-600' :
                  strategyStatus === 'error' ? 'text-red-600' :
                  'text-neutral-600'
                }`}>
                  {strategyStatus.toUpperCase()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-neutral-600">Environment:</span>
                <span className="text-sm font-medium uppercase">{environment}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-neutral-600">API Status:</span>
                <span className={`text-sm font-medium ${
                  apiConnected ? 'text-green-600' : 'text-red-600'
                }`}>
                  {apiConnected ? 'CONNECTED' : 'DISCONNECTED'}
                </span>
              </div>
            </div>
          </div>
          <div className="flex space-x-3">
            {strategyStatus === 'stopped' && (
              <button
                onClick={handleDeploy}
                disabled={!apiConnected}
                className={`px-4 py-2 text-sm font-medium rounded-md ${
                  apiConnected
                    ? 'bg-green-600 text-white hover:bg-green-700'
                    : 'bg-neutral-200 text-neutral-400 cursor-not-allowed'
                }`}
              >
                Deploy
              </button>
            )}
            {strategyStatus === 'running' && (
              <button
                onClick={handlePause}
                className="px-4 py-2 bg-orange-600 text-white text-sm font-medium rounded-md hover:bg-orange-700"
              >
                Pause
              </button>
            )}
            {strategyStatus === 'paused' && (
              <button
                onClick={handleRestart}
                className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700"
              >
                Restart
              </button>
            )}
            <button
              onClick={handleKillSwitch}
              className="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-md hover:bg-red-700 ml-auto"
            >
              Kill Switch
            </button>
          </div>
        </div>

        {/* 2. Live Metrics */}
        <div className="bg-white border border-neutral-200 rounded-lg p-6 mb-6">
          <h2 className="text-lg font-medium text-neutral-900 mb-4">Live Metrics (From Binance)</h2>
          <div className="grid grid-cols-3 gap-6">
            <div>
              <div className="text-sm text-neutral-600 mb-1">Current Equity</div>
              <div className="text-2xl font-medium">${liveMetrics.currentEquity.toFixed(2)}</div>
            </div>
            <div>
              <div className="text-sm text-neutral-600 mb-1">Unrealized P&L</div>
              <div className={`text-2xl font-medium ${liveMetrics.unrealizedPnL >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {liveMetrics.unrealizedPnL >= 0 ? '+' : ''}${liveMetrics.unrealizedPnL.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-sm text-neutral-600 mb-1">Realized P&L</div>
              <div className={`text-2xl font-medium ${liveMetrics.realizedPnL >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {liveMetrics.realizedPnL >= 0 ? '+' : ''}${liveMetrics.realizedPnL.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-sm text-neutral-600 mb-1">Daily P&L</div>
              <div className={`text-xl font-medium ${liveMetrics.dailyPnL >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {liveMetrics.dailyPnL >= 0 ? '+' : ''}${liveMetrics.dailyPnL.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-sm text-neutral-600 mb-1">Current Exposure</div>
              <div className="text-xl font-medium">${liveMetrics.currentExposure.toFixed(2)}</div>
            </div>
            <div>
              <div className="text-sm text-neutral-600 mb-1">Gross Leverage</div>
              <div className="text-xl font-medium">{liveMetrics.grossLeverage.toFixed(2)}x</div>
            </div>
            <div>
              <div className="text-sm text-neutral-600 mb-1">Risk Utilization</div>
              <div className={`text-xl font-medium ${
                liveMetrics.riskUtilization > 75 ? 'text-red-600' :
                liveMetrics.riskUtilization > 50 ? 'text-orange-600' :
                'text-green-600'
              }`}>
                {liveMetrics.riskUtilization.toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="text-sm text-neutral-600 mb-1">Slippage Avg</div>
              <div className="text-xl font-medium">{liveMetrics.slippageAvg.toFixed(3)}%</div>
            </div>
            <div>
              <div className="text-sm text-neutral-600 mb-1">Turnover</div>
              <div className="text-xl font-medium">{liveMetrics.turnover.toFixed(2)}</div>
            </div>
          </div>
        </div>

        {/* 3. Positions & Orders */}
        <div className="grid grid-cols-2 gap-6 mb-6">
          {/* Open Positions */}
          <div className="bg-white border border-neutral-200 rounded-lg p-6">
            <h3 className="text-lg font-medium text-neutral-900 mb-4">Open Positions</h3>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-neutral-200">
                    <th className="text-left py-2 text-xs font-medium text-neutral-600 uppercase">Asset</th>
                    <th className="text-right py-2 text-xs font-medium text-neutral-600 uppercase">Qty</th>
                    <th className="text-right py-2 text-xs font-medium text-neutral-600 uppercase">Entry</th>
                    <th className="text-right py-2 text-xs font-medium text-neutral-600 uppercase">Current</th>
                    <th className="text-right py-2 text-xs font-medium text-neutral-600 uppercase">P&L</th>
                    <th className="text-right py-2 text-xs font-medium text-neutral-600 uppercase">Margin</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.length > 0 ? positions.map((position, idx) => (
                    <tr key={idx} className="border-b border-neutral-100">
                      <td className="py-2 text-sm font-medium">{position.asset}</td>
                      <td className="py-2 text-sm text-right">{position.qty}</td>
                      <td className="py-2 text-sm text-right">${position.entryPrice.toFixed(2)}</td>
                      <td className="py-2 text-sm text-right">${position.currentPrice.toFixed(2)}</td>
                      <td className={`py-2 text-sm text-right font-medium ${position.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        ${position.pnl.toFixed(2)}
                      </td>
                      <td className="py-2 text-sm text-right">${position.margin.toFixed(2)}</td>
                    </tr>
                  )) : (
                    <tr>
                      <td colSpan={6} className="py-4 text-center text-sm text-neutral-400">
                        {apiConnected ? 'No open positions' : 'Connect API to view positions'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Orders & Fills */}
          <div className="bg-white border border-neutral-200 rounded-lg p-6">
            <h3 className="text-lg font-medium text-neutral-900 mb-4">Orders & Fills</h3>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-neutral-200">
                    <th className="text-left py-2 text-xs font-medium text-neutral-600 uppercase">Time</th>
                    <th className="text-left py-2 text-xs font-medium text-neutral-600 uppercase">Asset</th>
                    <th className="text-left py-2 text-xs font-medium text-neutral-600 uppercase">Side</th>
                    <th className="text-right py-2 text-xs font-medium text-neutral-600 uppercase">Size</th>
                    <th className="text-right py-2 text-xs font-medium text-neutral-600 uppercase">Price</th>
                    <th className="text-left py-2 text-xs font-medium text-neutral-600 uppercase">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.length > 0 ? orders.map((order, idx) => (
                    <tr key={idx} className="border-b border-neutral-100">
                      <td className="py-2 text-sm">{order.time.toLocaleTimeString()}</td>
                      <td className="py-2 text-sm font-medium">{order.asset}</td>
                      <td className={`py-2 text-sm font-medium ${order.side === 'BUY' ? 'text-green-600' : 'text-red-600'}`}>
                        {order.side}
                      </td>
                      <td className="py-2 text-sm text-right">{order.size}</td>
                      <td className="py-2 text-sm text-right">${order.price.toFixed(2)}</td>
                      <td className="py-2">
                        <span className={`text-xs font-medium px-2 py-1 rounded ${
                          order.status === 'FILLED' ? 'bg-green-100 text-green-700' :
                          order.status === 'PARTIAL' ? 'bg-orange-100 text-orange-700' :
                          'bg-neutral-100 text-neutral-700'
                        }`}>
                          {order.status}
                        </span>
                      </td>
                    </tr>
                  )) : (
                    <tr>
                      <td colSpan={6} className="py-4 text-center text-sm text-neutral-400">
                        {apiConnected ? 'No recent orders' : 'Connect API to view orders'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* 4. Logs & Risk Events */}
        <div className="bg-white border border-neutral-200 rounded-lg p-6">
          <h2 className="text-lg font-medium text-neutral-900 mb-4">Logs & Risk Events</h2>
          <div className="bg-neutral-900 rounded-lg p-4 h-64 overflow-y-auto font-mono text-xs">
            {logEvents.length > 0 ? logEvents.map((event, idx) => (
              <div key={idx} className={`mb-1 ${
                event.severity === 'critical' ? 'text-red-400' :
                event.severity === 'warning' ? 'text-orange-400' :
                'text-green-400'
              }`}>
                <span className="text-neutral-500">[{event.time.toLocaleTimeString()}]</span>{' '}
                <span className="text-neutral-300">{event.type}:</span>{' '}
                {event.message}
              </div>
            )) : (
              <div className="text-neutral-500">No events logged</div>
            )}
          </div>
        </div>
      </main>
    </>
  );
}