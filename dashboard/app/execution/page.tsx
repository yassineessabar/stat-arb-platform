"use client";

import { useState, useEffect } from "react";
import { NavHeader } from "@/components/layout/nav-header";
import { DatabaseService, StrategyDeployment, Position, Trade } from "@/lib/supabase";
import DeploymentModal from "@/components/DeploymentModal";
// EC2Monitor removed - replaced with real-time log streaming

type Environment = 'paper' | 'live';
type StrategyStatus = 'stopped' | 'running' | 'paused' | 'error';

interface ApiCredentials {
  apiKey: string;
  secretKey: string;
  testnet: boolean;
}

interface LiveMetrics {
  marginBalance: number;
  unrealizedPnL: number;
  realizedPnL: number;
  dailyPnL: number;
  currentExposure: number; // Position notional value
  grossLeverage: number;
  riskUtilization: number;
  slippageAvg: number;
  turnover: number;
}

interface BinancePosition {
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
  use_v6_engine?: boolean;
  universe?: string[];
  portfolio_value?: number;
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
    marginBalance: 0,
    unrealizedPnL: 0,
    realizedPnL: 0,
    dailyPnL: 0,
    currentExposure: 0,
    grossLeverage: 0,
    riskUtilization: 0,
    slippageAvg: 0,
    turnover: 0
  });

  const [positions, setPositions] = useState<BinancePosition[]>([]);
  const [dbPositions, setDbPositions] = useState<Position[]>([]);
  const [activeDeployments, setActiveDeployments] = useState<StrategyDeployment[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [logEvents, setLogEvents] = useState<LogEvent[]>([]);
  const [strategyLogs, setStrategyLogs] = useState<any[]>([]);
  const [ec2Logs, setEc2Logs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [showServerDeployModal, setShowServerDeployModal] = useState(false);
  const [vpsDeployments, setVpsDeployments] = useState<any[]>([]);

  const [strategyParams, setStrategyParams] = useState<StrategyParameters>({
    strategy_name: 'StatArb_v6_Multi',
    trading_mode: 'paper',
    use_v6_engine: true,  // Use backtest engine by default
    universe: ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT', 'ADAUSDT', 'AVAXUSDT', 'DOGEUSDT'],
    portfolio_value: 10000,
    symbol_1: 'ETHUSDT',
    symbol_2: 'BTCUSDT',
    lookback_period: 180,  // v6 default
    entry_z_score: 1.0,    // v6 parameter
    exit_z_score: 0.2,     // v6 parameter
    stop_loss_z_score: 3.5, // v6 parameter
    position_size: 1000,
    max_positions: 30,     // v6 allows up to 30 pairs
    rebalance_frequency: 5
  });

  // Load credentials from localStorage on mount and fetch database data
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

    // Load active deployments from database
    loadActiveDeployments();

    // Load initial EC2 logs
    loadEc2Logs();
  }, []);

  // Load active deployments from database and get latest running strategy from files
  const loadActiveDeployments = async () => {
    try {
      // First check for currently running strategies from the file system
      const response = await fetch('/api/strategy/stop');
      const fileData = await response.json();

      // Find the latest running strategy (not stale)
      const runningStrategies = fileData.strategies?.filter((s: any) => s.status === 'running') || [];

      if (runningStrategies.length > 0) {
        // Sort by processId to get the most recent (they contain timestamps)
        const latestStrategy = runningStrategies.sort((a: any, b: any) =>
          b.processId.localeCompare(a.processId)
        )[0];

        // Only update if it's a different strategy to avoid loops
        if (deploymentProcessId !== latestStrategy.processId) {
          setDeploymentProcessId(latestStrategy.processId);
          setStrategyStatus('running');
          setEnvironment(latestStrategy.trading_mode);
          addLog('DEPLOYMENT', `Loaded running strategy: ${latestStrategy.strategy_name} (${latestStrategy.processId})`, 'info');

          // Load strategy logs for this deployment
          setTimeout(() => loadStrategyLogs(), 500);
        }
      } else {
        // No running strategies found, show stopped state
        if (strategyStatus === 'running') {
          setStrategyStatus('stopped');
          setDeploymentProcessId(null);
          addLog('DEPLOYMENT', 'No active strategies found', 'info');
        }
      }

      // Also load database deployments for position data
      const { data, error } = await DatabaseService.getActiveDeployments();
      if (!error && data) {
        setActiveDeployments(data);

        // Load positions for the first deployment if available
        if (data.length > 0) {
          loadPositionsForDeployment(data[0].id);
        }
      }
    } catch (error) {
      addLog('ERROR', `Deployment load error: ${error}`, 'critical');
    }
  };

  // Load positions from database for a deployment
  const loadPositionsForDeployment = async (deploymentId: string) => {
    try {
      const { data, error } = await DatabaseService.getOpenPositions(deploymentId);
      if (error) {
        addLog('ERROR', `Failed to load positions: ${error.message}`, 'warning');
        return;
      }

      setDbPositions(data || []);
      addLog('STRATEGY', `Loaded ${data?.length || 0} positions from database`, 'info');
    } catch (error) {
      addLog('ERROR', `Position load error: ${error}`, 'warning');
    }
  };

  // Load strategy logs from database first, fallback to files, then EC2 live logs
  const loadStrategyLogs = async () => {
    // Use the current deploymentProcessId
    const processId = deploymentProcessId;

    if (!processId) {
      setStrategyLogs([]);
      // Still load EC2 logs to show live data even without local strategy
      loadEc2Logs();
      return;
    }

    try {
      // Try VPS logs first (for VPS deployments)
      if (processId.startsWith('vps_')) {
        console.log('📡 Loading VPS logs for deployment:', processId);
        const vpsResponse = await fetch(`/api/vps/logs?deploymentId=${processId}&limit=50`);
        const vpsResult = await vpsResponse.json();

        if (vpsResult.success && vpsResult.logs && vpsResult.logs.length > 0) {
          console.log('📡 VPS logs loaded:', vpsResult.logs.length, 'entries');
          setStrategyLogs(vpsResult.logs.map((log: any) => ({
            timestamp: log.timestamp,
            level: log.level,
            message: log.message,
            event_type: log.eventType,
            details: log.details
          })));
          return;
        }
      }

      // Try local database logs (for local deployments)
      const dbResponse = await fetch(`/api/strategy/db-logs?processId=${processId}&limit=50`);
      const dbResult = await dbResponse.json();

      if (dbResult.success && dbResult.logs && dbResult.logs.length > 0) {
        console.log('📊 Database logs loaded:', dbResult.logs.length, 'entries');
        setStrategyLogs(dbResult.logs);
        return;
      }

      // Fallback to file-based logs if database logs are not available
      console.log('📁 Falling back to file-based logs');
      const fileResponse = await fetch(`/api/strategy/logs?processId=${processId}&lines=50`);
      const fileResult = await fileResponse.json();

      if (fileResult.success && fileResult.logs) {
        console.log('📁 File logs loaded:', fileResult.logs.length, 'entries');
        setStrategyLogs(fileResult.logs);
      } else {
        // Log file might not exist yet for new deployments
        if (!fileResult.error?.includes('Log file not found')) {
          console.warn('Failed to load strategy logs:', fileResult.error);
        }
        setStrategyLogs([]);
        // Load EC2 live logs as fallback
        loadEc2Logs();
      }
    } catch (error) {
      console.warn('Error fetching strategy logs:', error);
      setStrategyLogs([]);
      // Load EC2 live logs as fallback
      loadEc2Logs();
    }
  };

  // Load live EC2-style logs (simulated terminal output)
  const loadEc2Logs = async () => {
    try {
      const response = await fetch('/api/logs/ec2');
      const result = await response.json();

      if (result.success && result.logs) {
        setEc2Logs(result.logs);
      }
    } catch (error) {
      console.warn('Error fetching EC2 logs:', error);
      setEc2Logs([]);
    }
  };

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
      // Use environment to determine API mode: 'paper' uses testnet, 'live' uses live API
      const apiMode = environment; // 'paper' or 'live'
      const response = await fetch(`/api/binance/test?mode=${apiMode}`);

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
      // Use testnet API for paper trading, live API for live trading
      const apiMode = environment; // 'paper' or 'live'
      const [accountRes, positionsRes, tradesRes] = await Promise.all([
        fetch(`/api/binance/account?mode=${apiMode}`),
        fetch(`/api/binance/positions?mode=${apiMode}`),
        fetch(`/api/binance/trades?mode=${apiMode}`)
      ]);

      if (accountRes.ok) {
        const account = await accountRes.json();

        // Use real Binance Futures account data
        const marginBalance = parseFloat(account.marginBalance || '0');
        const unrealized = parseFloat(account.totalUnrealizedProfit || '0');
        const totalInitialMargin = parseFloat(account.totalInitialMargin || '0');
        const positionNotional = parseFloat(account.positionNotional || '0');

        setLiveMetrics({
          marginBalance: marginBalance,
          unrealizedPnL: unrealized,
          realizedPnL: parseFloat(account.totalPnL || '0'),
          dailyPnL: 0, // Would need historical data to calculate daily P&L
          currentExposure: positionNotional,
          grossLeverage: marginBalance > 0 ? positionNotional / marginBalance : 0,
          riskUtilization: marginBalance > 0 ? (totalInitialMargin / marginBalance) * 100 : 0,
          slippageAvg: 0.05, // Would need trade data to calculate real slippage
          turnover: 0.12 // Would need trade data to calculate real turnover
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

  // Fetch data on interval and update database positions
  useEffect(() => {
    if (apiConnected) {
      fetchExecutionData();
      const interval = setInterval(() => {
        fetchExecutionData();
        // Refresh database data and strategy logs every 10 seconds
        if (Date.now() % 10000 < 2000) {
          loadActiveDeployments();
          loadStrategyLogs();
        }
        // Refresh EC2 logs more frequently (every 5 seconds)
        if (Date.now() % 5000 < 2000) {
          loadEc2Logs();
        }
      }, 2000);
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

        // Refresh deployments from database and start loading logs
        setTimeout(() => {
          loadActiveDeployments();
          loadStrategyLogs();
        }, 1000);
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

        // Refresh deployments from database
        setTimeout(() => loadActiveDeployments(), 1000);
        setDbPositions([]); // Clear positions
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
                {/* Engine Selection */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="text-sm font-medium text-blue-900">Strategy Engine</h4>
                    <label className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={strategyParams.use_v6_engine}
                        onChange={(e) => {
                          const useV6 = e.target.checked;
                          setStrategyParams({
                            ...strategyParams,
                            use_v6_engine: useV6,
                            entry_z_score: useV6 ? 1.0 : 2.0,
                            exit_z_score: useV6 ? 0.2 : 0.5,
                            stop_loss_z_score: useV6 ? 3.5 : 3.0,
                            max_positions: useV6 ? 30 : 3,
                            lookback_period: useV6 ? 180 : 24
                          });
                        }}
                        className="rounded"
                      />
                      <span className="text-sm font-medium text-blue-900">Use v6 Backtest Engine</span>
                    </label>
                  </div>
                  {strategyParams.use_v6_engine ? (
                    <div className="text-xs text-blue-700">
                      ✅ Using exact backtest strategy with Kalman filter, regime detection, and multi-pair trading.
                      <br />Parameters: Entry Z={strategyParams.entry_z_score}, Exit Z={strategyParams.exit_z_score}, Max {strategyParams.max_positions} pairs
                    </div>
                  ) : (
                    <div className="text-xs text-gray-600">
                      Using simple single-pair strategy with basic z-score signals.
                    </div>
                  )}
                </div>

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

                {/* Trading Pairs or Universe */}
                {strategyParams.use_v6_engine ? (
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 mb-1">
                      Trading Universe (comma-separated)
                    </label>
                    <textarea
                      value={strategyParams.universe?.join(', ') || ''}
                      onChange={(e) => {
                        const universe = e.target.value.split(',').map(s => s.trim().toUpperCase()).filter(s => s);
                        setStrategyParams({...strategyParams, universe});
                      }}
                      className="w-full px-3 py-2 border border-neutral-300 rounded-md text-sm"
                      rows={2}
                      placeholder="BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT"
                    />
                    <div className="text-xs text-gray-500 mt-1">
                      Strategy will automatically find best pairs from these assets
                    </div>
                  </div>
                ) : (
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
                )}

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
                <span className="text-sm font-medium">
                  {activeDeployments.length > 0 ? activeDeployments[0].strategy_name : 'No Strategy Running'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-neutral-600">Process ID:</span>
                <span className="text-sm font-mono">
                  {deploymentProcessId || 'None'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-neutral-600">Capital:</span>
                <span className="text-sm font-medium">
                  ${liveMetrics.marginBalance.toLocaleString()}
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
              <>
                <button
                  onClick={handleDeploy}
                  disabled={!apiConnected}
                  className={`px-4 py-2 text-sm font-medium rounded-md ${
                    apiConnected
                      ? 'bg-green-600 text-white hover:bg-green-700'
                      : 'bg-neutral-200 text-neutral-400 cursor-not-allowed'
                  }`}
                >
                  Deploy Locally
                </button>
                <button
                  onClick={() => setShowServerDeployModal(true)}
                  disabled={!apiConnected}
                  className={`px-4 py-2 text-sm font-medium rounded-md ${
                    apiConnected
                      ? 'bg-blue-600 text-white hover:bg-blue-700'
                      : 'bg-neutral-200 text-neutral-400 cursor-not-allowed'
                  }`}
                >
                  Deploy to Server (24/7)
                </button>
              </>
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
              <div className="text-sm text-neutral-600 mb-1">Margin Balance</div>
              <div className="text-2xl font-medium">${liveMetrics.marginBalance.toFixed(2)}</div>
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
              <div className="text-sm text-neutral-600 mb-1">Position Notional</div>
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

        {/* EC2 Monitor section removed - logs now shown in Strategy Logs section */}

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
                  {/* Show database positions first, then Binance positions */}
                  {dbPositions.length > 0 ? dbPositions.map((position, idx) => (
                    <tr key={`db-${idx}`} className="border-b border-neutral-100 bg-blue-50">
                      <td className="py-2 text-sm font-medium">
                        {position.symbol_1}/{position.symbol_2}
                        <div className="text-xs text-blue-600">Strategy Position</div>
                      </td>
                      <td className="py-2 text-sm text-right">{position.position_size}</td>
                      <td className="py-2 text-sm text-right">${position.entry_price_1.toFixed(2)}</td>
                      <td className="py-2 text-sm text-right">-</td>
                      <td className={`py-2 text-sm text-right font-medium ${position.realized_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        ${position.realized_pnl.toFixed(2)}
                      </td>
                      <td className="py-2 text-sm text-right">-</td>
                    </tr>
                  )) : null}

                  {/* Binance API positions */}
                  {positions.length > 0 ? positions.map((position, idx) => (
                    <tr key={`binance-${idx}`} className="border-b border-neutral-100">
                      <td className="py-2 text-sm font-medium">
                        {position.asset}
                        <div className="text-xs text-neutral-500">Binance Position</div>
                      </td>
                      <td className="py-2 text-sm text-right">{position.qty}</td>
                      <td className="py-2 text-sm text-right">${position.entryPrice.toFixed(2)}</td>
                      <td className="py-2 text-sm text-right">${position.currentPrice.toFixed(2)}</td>
                      <td className={`py-2 text-sm text-right font-medium ${position.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        ${position.pnl.toFixed(2)}
                      </td>
                      <td className="py-2 text-sm text-right">${position.margin.toFixed(2)}</td>
                    </tr>
                  )) : null}

                  {/* Show message if no positions */}
                  {dbPositions.length === 0 && positions.length === 0 && (
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

        {/* 4. Real-Time Strategy Logs (Live from EC2) */}
        <div className="bg-white border border-neutral-200 rounded-lg p-6">
          <h2 className="text-lg font-medium text-neutral-900 mb-4">
            Real-Time Strategy Logs (Live from EC2)
            {deploymentProcessId && (
              <span className="ml-2 text-sm text-neutral-500 font-normal">
                (Process: {deploymentProcessId.split('_')[1]})
              </span>
            )}
            {!deploymentProcessId && ec2Logs.length > 0 && (
              <span className="ml-2 text-sm text-green-500 font-normal">
                (Live EC2 Terminal)
              </span>
            )}
          </h2>
          <div className="bg-neutral-900 rounded-lg p-4 h-64 overflow-y-auto font-mono text-xs">
            {strategyLogs.length > 0 ? (() => {
              // Group signal analysis logs together
              const signalGroups: any[] = [];
              let currentGroup: any[] = [];

              strategyLogs.forEach((log) => {
                const isSignalLog = log.message.includes('SIGNAL CHECK') ||
                                   log.message.includes('ENTRY CRITERIA') ||
                                   log.message.includes('NO ENTRY') ||
                                   log.message.includes('ENTRY SIGNAL TRIGGERED') ||
                                   log.message.includes('EXIT CHECK');

                if (isSignalLog) {
                  if (log.message.includes('SIGNAL CHECK')) {
                    // Start new group
                    if (currentGroup.length > 0) {
                      signalGroups.push(currentGroup);
                    }
                    currentGroup = [log];
                  } else {
                    currentGroup.push(log);
                  }
                } else {
                  // Non-signal log - close current group and show individual log
                  if (currentGroup.length > 0) {
                    signalGroups.push(currentGroup);
                    currentGroup = [];
                  }
                  signalGroups.push([log]);
                }
              });

              if (currentGroup.length > 0) {
                signalGroups.push(currentGroup);
              }

              return signalGroups.map((group, groupIndex) => {
                const isSignalGroup = group.some((log: any) =>
                  log.message.includes('SIGNAL CHECK') ||
                  log.message.includes('ENTRY CRITERIA') ||
                  log.message.includes('NO ENTRY') ||
                  log.message.includes('EXIT CHECK')
                );

                if (isSignalGroup && group.length > 1) {
                  // Signal analysis group - format as card
                  const timestamp = new Date(group[0].timestamp).toLocaleTimeString();
                  return (
                    <div key={groupIndex} className="mb-3 p-2 bg-neutral-800/30 rounded border border-neutral-700/50">
                      <div className="text-blue-400 font-semibold text-xs mb-1">
                        🔍 Signal Analysis - {timestamp}
                      </div>
                      {group.map((log: any, logIndex: number) => (
                        <div key={logIndex} className={`text-xs ml-2 ${
                          log.message.includes('SIGNAL CHECK') ? 'text-blue-300' :
                          log.message.includes('ENTRY CRITERIA') ? 'text-cyan-300' :
                          log.message.includes('✅') ? 'text-green-400 font-medium' :
                          log.message.includes('❌') ? 'text-yellow-400' :
                          log.message.includes('EXIT CHECK') ? 'text-purple-300' :
                          'text-neutral-300'
                        }`}>
                          {log.message.includes('SIGNAL CHECK') && '📊 '}
                          {log.message.includes('ENTRY CRITERIA') && '🎯 '}
                          {log.message.includes('❌') && '⚠️ '}
                          {log.message.includes('✅') && '✅ '}
                          {log.message.includes('EXIT CHECK') && '🚪 '}
                          {log.message.replace(/^(SIGNAL CHECK|ENTRY CRITERIA|EXIT CHECK) - /, '')}
                        </div>
                      ))}
                    </div>
                  );
                } else {
                  // Individual log entries
                  return group.map((log: any, logIndex: number) => (
                    <div key={`${groupIndex}-${logIndex}`} className={`mb-1 text-xs ${
                      log.level === 'error' ? 'text-red-400' :
                      log.level === 'warning' ? 'text-orange-400' :
                      log.message.includes('Connected') ? 'text-green-400' :
                      log.message.includes('Starting') ? 'text-blue-400' :
                      log.message.includes('Status') ? 'text-cyan-300' :
                      'text-neutral-400'
                    }`}>
                      <span className="text-neutral-500">[{new Date(log.timestamp).toLocaleTimeString()}]</span>{' '}
                      {log.message}
                    </div>
                  ));
                }
              });
            })() : ec2Logs.length > 0 ? (
              // Show EC2 live logs as primary fallback
              ec2Logs.map((log, idx) => (
                <div key={idx} className={`mb-1 text-xs ${
                  log.level === 'SUCCESS' ? 'text-green-400' :
                  log.level === 'ERROR' ? 'text-red-400' :
                  log.level === 'WARNING' ? 'text-orange-400' :
                  log.message.includes('🔄 ITERATION') ? 'text-blue-400 font-semibold' :
                  log.message.includes('📊 MARKET ANALYSIS') ? 'text-cyan-400 font-medium' :
                  log.message.includes('OPEN POSITIONS') ? 'text-purple-300 font-medium' :
                  log.message.includes('BTC/USDT') ? 'text-yellow-300' :
                  log.message.includes('ETH/USDT') ? 'text-blue-300' :
                  log.message.includes('BNB/USDT') ? 'text-amber-300' :
                  log.message.includes('ORDER EXECUTED') ? 'text-green-400 font-semibold' :
                  log.message.includes('----') ? 'text-neutral-600' :
                  'text-neutral-400'
                }`}>
                  <span className="text-neutral-500">[{new Date(log.timestamp).toLocaleTimeString()}]</span>{' '}
                  {log.message}
                </div>
              ))
            ) : logEvents.length > 0 ? (
              // Fallback to frontend events if no EC2 logs available
              logEvents.map((event, idx) => (
                <div key={idx} className={`mb-1 ${
                  event.severity === 'critical' ? 'text-red-400' :
                  event.severity === 'warning' ? 'text-orange-400' :
                  'text-green-400'
                }`}>
                  <span className="text-neutral-500">[{event.time.toLocaleTimeString()}]</span>{' '}
                  <span className="text-neutral-300">{event.type}:</span>{' '}
                  {event.message}
                </div>
              ))
            ) : (
              <div className="text-neutral-500">
                {deploymentProcessId ? 'Loading strategy logs...' : 'Loading live EC2 terminal data...'}
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Server Deployment Modal */}
      <DeploymentModal
        isOpen={showServerDeployModal}
        onClose={() => setShowServerDeployModal(false)}
        strategyConfig={{
          ...strategyParams,
          api_key: apiCredentials.apiKey,
          api_secret: apiCredentials.secretKey,
          testnet: apiCredentials.testnet
        }}
        onDeploy={async (deploymentConfig) => {
          try {
            setLoading(true);
            addLog('DEPLOYMENT', 'Initiating server deployment...', 'info');

            const response = await fetch('/api/deploy-server', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(deploymentConfig)
            });

            if (!response.ok) {
              const error = await response.json();
              throw new Error(error.details || 'Deployment failed');
            }

            const result = await response.json();
            addLog('DEPLOYMENT', `Deployment successful! ID: ${result.deploymentId}`, 'info');
            setShowServerDeployModal(false);

            // Show success notification
            alert(`✅ Strategy deployed successfully!\n\nDeployment ID: ${result.deploymentId}\nServer: ${result.details.host}\nPath: ${result.details.deploymentPath}\n\nYour strategy is now running 24/7 on the server.`);
          } catch (error: any) {
            console.error('Deployment error:', error);
            addLog('ERROR', `Deployment failed: ${error.message}`, 'critical');
            alert(`❌ Deployment failed: ${error.message}`);
          } finally {
            setLoading(false);
          }
        }}
      />
    </>
  );
}