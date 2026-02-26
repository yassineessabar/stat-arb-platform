"use client";

import { useState, useEffect } from "react";
import { NavHeader } from "@/components/layout/nav-header";
import { DatabaseService, StrategyDeployment, Position, Trade } from "@/lib/supabase";
import { DailyPnLChart } from "@/components/DailyPnLChart";
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
  commission?: number;
  commissionAsset?: string;
  realizedPnl?: number;
  status: 'FILLED' | 'PARTIAL' | 'CANCELLED' | 'REJECTED' | 'RISK_BLOCKED';
  orderId?: string;
  positionSide?: string;
  maker?: boolean;
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
  const [strategyDeployed, setStrategyDeployed] = useState(false);
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
    // Always clear and use fresh credentials to ensure they work
    localStorage.removeItem('binance_paper_credentials');

    // Auto-load hardcoded testnet credentials for demo
    const envCreds = {
      apiKey: 'UigdoIwOPHWFIvkjhrGvL1aqJwd4p88J7IQhkfMVrD8zmvjBCD0rhXdWqlAjMr5I',
      secretKey: 'XMg47ARX09YFUel64EdMxngYcXSz2iuyi81uATO7jsshhos9NIh3XwvSRYwovvKN',
      testnet: true
    };
    setApiCredentials(envCreds);
    setTempCredentials(envCreds);
    addLog('API', 'Auto-loaded fresh testnet credentials', 'info');

    // Load active deployments from database
    loadActiveDeployments();

    // Load initial EC2 logs
    loadEc2Logs();

    // Trigger initial data fetch after a short delay
    setTimeout(async () => {
      console.log('🚀 Triggering initial data fetch...');
      // Directly fetch trades without waiting for API connection
      try {
        const tradesRes = await fetch('/api/binance/trades?mode=paper&limit=1000&all=true');
        if (tradesRes.ok) {
          const data = await tradesRes.json();
          console.log('✅ Direct fetch got', data.trades?.length || 0, 'trades');
          if (data.trades && data.trades.length > 0) {
            const mappedOrders = data.trades.map((t: any) => ({
              time: new Date(t.time || Date.now()),
              asset: t.symbol,
              side: t.side,
              size: parseFloat(t.qty || '0'),
              price: parseFloat(t.price || '0'),
              slippage: 0,
              commission: parseFloat(t.commission || '0'),
              commissionAsset: t.commissionAsset,
              realizedPnl: parseFloat(t.realizedPnl || '0'),
              status: 'FILLED' as const,
              orderId: t.orderId,
              positionSide: t.positionSide,
              maker: t.maker
            }));
            setOrders(mappedOrders);
            console.log('✅ Set', mappedOrders.length, 'orders directly');
          }
        }
      } catch (error) {
        console.error('Direct fetch error:', error);
      }

      // Also try regular fetch if API key exists
      if (envCreds.apiKey) {
        await fetchExecutionData();
      }
    }, 1500);
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

  // Helper function to escape CSV values
  const escapeCSV = (value: any): string => {
    if (value === null || value === undefined) return '';
    const str = value.toString();
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const testConnection = async () => {
    try {
      // Use environment to determine API mode: 'paper' uses testnet, 'live' uses live API
      const apiMode = environment; // 'paper' or 'live'
      const response = await fetch(`/api/binance/test`, {
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
        // Immediately fetch execution data after successful connection
        fetchExecutionData();
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
    // Allow fetching if we have credentials, even if not fully connected yet
    if (!apiCredentials.apiKey) {
      console.log('⚠️ No API key available for fetching data');
      return;
    }
    console.log('📊 Starting fetchExecutionData...');

    try {
      // Use testnet API for paper trading, live API for live trading
      const apiMode = environment; // 'paper' or 'live'
      const tradesUrl = `/api/binance/trades?mode=${apiMode}&limit=1000&all=true`;
      console.log('📡 Fetching trades from:', tradesUrl);

      const [accountRes, positionsRes, tradesRes] = await Promise.all([
        fetch(`/api/binance/account?mode=${apiMode}`),
        fetch(`/api/binance/positions?mode=${apiMode}`),
        fetch(tradesUrl) // Get all trade history
      ]);

      if (accountRes.ok) {
        const account = await accountRes.json();

        // Use real Binance Futures account data
        const marginBalance = parseFloat(account.marginBalance || account.totalWalletBalance || '0');
        const unrealized = parseFloat(account.totalUnrealizedProfit || '0');
        const totalInitialMargin = parseFloat(account.totalInitialMargin || '0');
        const totalMaintMargin = parseFloat(account.totalMaintMargin || '0');

        // Calculate position notional from actual positions
        let totalNotional = 0;
        if (account.positions && Array.isArray(account.positions)) {
          totalNotional = account.positions.reduce((sum: number, pos: any) => {
            const notional = Math.abs(parseFloat(pos.positionAmt || '0')) * parseFloat(pos.markPrice || '0');
            return sum + notional;
          }, 0);
        }

        // Calculate daily P&L from today's trades
        let dailyPnL = 0;
        let dailyVolume = 0;
        let slippageSum = 0;
        let slippageCount = 0;

        if (tradesRes.ok) {
          const tradesData = await tradesRes.json();
          const today = new Date();
          today.setHours(0, 0, 0, 0);

          if (tradesData.trades && Array.isArray(tradesData.trades)) {
            tradesData.trades.forEach((trade: any) => {
              const tradeTime = new Date(trade.time);

              // Calculate daily P&L from today's realized trades
              if (tradeTime >= today) {
                dailyPnL += parseFloat(trade.realizedPnl || '0');
                dailyVolume += Math.abs(parseFloat(trade.qty || '0')) * parseFloat(trade.price || '0');
              }

              // Calculate slippage if we have both executed price and expected price
              if (trade.price && trade.expectedPrice) {
                const slippage = Math.abs(parseFloat(trade.price) - parseFloat(trade.expectedPrice)) / parseFloat(trade.expectedPrice) * 100;
                slippageSum += slippage;
                slippageCount++;
              }
            });
          }
        }

        // Calculate gross leverage properly
        const grossLeverage = marginBalance > 0 ? Math.abs(totalNotional) / marginBalance : 0;

        // Calculate risk utilization based on margin usage
        const riskUtil = marginBalance > 0 ? (totalInitialMargin / marginBalance) * 100 : 0;

        // Calculate average slippage
        const avgSlippage = slippageCount > 0 ? slippageSum / slippageCount : 0.05;

        // Calculate turnover (daily volume / account balance)
        const turnover = marginBalance > 0 ? dailyVolume / marginBalance : 0;

        setLiveMetrics({
          marginBalance: marginBalance,
          unrealizedPnL: unrealized,
          realizedPnL: parseFloat(account.totalRealizedPnl || account.totalPnL || '0'),
          dailyPnL: dailyPnL,
          currentExposure: totalNotional,
          grossLeverage: grossLeverage,
          riskUtilization: riskUtil,
          slippageAvg: avgSlippage,
          turnover: turnover
        });
      }

      if (positionsRes.ok) {
        const data = await positionsRes.json();
        const binancePositions = data.positions?.map((p: any) => {
          const notional = Math.abs(parseFloat(p.size || p.positionAmt || '0')) * parseFloat(p.markPrice || p.entryPrice || '0');
          return {
            asset: p.symbol,
            qty: parseFloat(p.size || p.positionAmt || '0'),
            entryPrice: parseFloat(p.entryPrice || '0'),
            currentPrice: parseFloat(p.markPrice || p.entryPrice || '0'),
            pnl: parseFloat(p.pnl || p.unrealizedProfit || '0'),
            exposurePercent: liveMetrics.marginBalance > 0 ? (notional / liveMetrics.marginBalance) * 100 : 0,
            margin: parseFloat(p.margin || p.initialMargin || '0')
          };
        }) || [];
        setPositions(binancePositions);
      }

      if (tradesRes.ok) {
        const tradesData = await tradesRes.json();
        console.log('📊 Fetched trades:', tradesData.count || tradesData.trades?.length || 0);

        if (!tradesData.trades || !Array.isArray(tradesData.trades)) {
          console.warn('No trades array in response:', tradesData);
          setOrders([]);
        } else {

        const recentOrders = tradesData.trades.map((t: any) => {
          // Calculate actual slippage if we have order info
          let slippage = 0;
          if (t.expectedPrice && t.price) {
            slippage = Math.abs(parseFloat(t.price) - parseFloat(t.expectedPrice)) / parseFloat(t.expectedPrice) * 100;
          }

          return {
            time: new Date(t.time || Date.now()),
            asset: t.symbol,
            side: t.side,
            size: parseFloat(t.qty || t.quantity || '0'),
            price: parseFloat(t.price || '0'),
            slippage: slippage,
            commission: parseFloat(t.commission || '0'),
            commissionAsset: t.commissionAsset,
            realizedPnl: parseFloat(t.realizedPnl || '0'),
            status: 'FILLED' as const,
            orderId: t.orderId,
            positionSide: t.positionSide,
            maker: t.maker
          };
        });

        // Sort by time, most recent first
        recentOrders.sort((a: any, b: any) => b.time.getTime() - a.time.getTime());
        console.log('📈 Setting orders:', recentOrders.length);
        setOrders(recentOrders);

        if (recentOrders.length > 0) {
          addLog('TRADES', `Loaded ${recentOrders.length} trades from Binance`, 'info');
        }
        }
      } else {
        console.warn('Trades response not OK:', tradesRes.status);
        setOrders([]);
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
    if (confirm('KILL SWITCH: Stop strategy on EC2 server and close all positions immediately?')) {
      try {
        setLoading(true);

        // Stop strategy on EC2 server
        const response = await fetch('/api/ec2/stop-strategy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });

        const result = await response.json();

        if (result.success) {
          setStrategyStatus('stopped');
          setDeploymentProcessId(null);
          setApiConnected(false);
          setStrategyDeployed(false);
          addLog('RISK', 'KILL SWITCH ACTIVATED - Strategy stopped on EC2 server', 'critical');

          // If in live mode, also close positions
          if (environment === 'live' && positions.length > 0) {
            try {
              const emergencyResponse = await fetch('/api/binance/emergency-stop', {
                method: 'POST'
              });
              const emergencyResult = await emergencyResponse.json();
              if (emergencyResult.success) {
                addLog('RISK', `${emergencyResult.closedPositions?.length || 0} positions closed`, 'critical');
                setPositions([]);
              }
            } catch (error) {
              addLog('ERROR', `Position closure failed: ${error}`, 'critical');
            }
          }
        } else {
          addLog('ERROR', `Kill switch failed: ${result.error || 'Unknown error'}`, 'critical');
        }
      } catch (error) {
        addLog('ERROR', `Kill switch error: ${error}`, 'critical');
      } finally {
        setLoading(false);
      }
    }
  };

  const handleDeployToEC2 = async () => {
    if (confirm('Deploy strategy to EC2 server?')) {
      try {
        setLoading(true);
        addLog('DEPLOYMENT', 'Deploying strategy to EC2 server...', 'info');

        const deploymentConfig = {
          ...strategyParams,
          api_key: apiCredentials.apiKey,
          api_secret: apiCredentials.secretKey,
          testnet: apiCredentials.testnet
        };

        const response = await fetch('/api/ec2/deploy-strategy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(deploymentConfig)
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.error || 'Deployment failed');
        }

        const result = await response.json();
        setStrategyStatus('running');
        setApiConnected(true);
        setStrategyDeployed(true);
        addLog('DEPLOYMENT', 'Strategy deployed successfully on EC2!', 'info');

        alert(`✅ Strategy deployed successfully on EC2!\n\nProcess Running: ${result.processRunning ? 'Yes' : 'No'}\n\nYour strategy is now running 24/7 on the EC2 server.`);
      } catch (error: any) {
        console.error('EC2 deployment error:', error);
        addLog('ERROR', `EC2 deployment failed: ${error.message}`, 'critical');
        alert(`❌ EC2 deployment failed: ${error.message}`);
      } finally {
        setLoading(false);
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
              strategyDeployed
                ? 'bg-green-100 text-green-700'
                : 'bg-neutral-100 text-neutral-600'
            }`}>
              {strategyDeployed ? '● Connected' : '○ Disconnected'}
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
              onClick={strategyDeployed ? handleKillSwitch : handleDeployToEC2}
              className={`px-4 py-2 text-white text-sm font-medium rounded-md ml-auto ${
                strategyDeployed
                  ? 'bg-red-600 hover:bg-red-700'
                  : 'bg-green-600 hover:bg-green-700'
              }`}
            >
              {strategyDeployed ? 'Kill Switch' : 'Deploy'}
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

        {/* Daily P&L Chart */}
        <div className="mb-6">
          <DailyPnLChart
            mode={environment}
            onTradeClick={(trade) => {
              console.log('Trade clicked:', trade);
              addLog('STRATEGY', `Viewing trade: ${trade.symbol} ${trade.side} ${trade.quantity} @ ${trade.price}`, 'info');
            }}
          />
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

          {/* Transaction History */}
          <div className="bg-white border border-neutral-200 rounded-lg p-6">
            <div className="mb-4">
              <div className="flex justify-between items-center mb-3">
                <h3 className="text-lg font-medium text-neutral-900">Transaction History</h3>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">
                    {orders.length > 0 ? `${orders.length} total trades` : 'No trades yet'}
                  </span>
                  <button
                    onClick={async () => {
                      console.log('🔄 Manual refresh clicked');
                      setOrders([]); // Clear first
                      try {
                        const res = await fetch('/api/binance/trades?mode=paper&limit=1000&all=true');
                        if (res.ok) {
                          const data = await res.json();
                          console.log('✅ Manual refresh got', data.trades?.length || 0, 'trades');
                          if (data.trades && data.trades.length > 0) {
                            const mappedOrders = data.trades.map((t: any) => ({
                              time: new Date(t.time || Date.now()),
                              asset: t.symbol,
                              side: t.side,
                              size: parseFloat(t.qty || '0'),
                              price: parseFloat(t.price || '0'),
                              slippage: 0,
                              commission: parseFloat(t.commission || '0'),
                              commissionAsset: t.commissionAsset,
                              realizedPnl: parseFloat(t.realizedPnl || '0'),
                              status: 'FILLED' as const,
                              orderId: t.orderId,
                              positionSide: t.positionSide,
                              maker: t.maker
                            }));
                            setOrders(mappedOrders);
                            addLog('TRADES', `Loaded ${mappedOrders.length} trades`, 'info');
                          }
                        }
                      } catch (error) {
                        console.error('Refresh error:', error);
                        addLog('ERROR', `Failed to refresh trades: ${error}`, 'critical');
                      }
                    }}
                    className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded"
                  >
                    Refresh
                  </button>
                  {orders.length > 0 && (
                    <button
                      onClick={() => {
                        // Export to CSV
                        const csvHeaders = ['Date', 'Time', 'Symbol', 'Side', 'Quantity', 'Price', 'Value', 'Commission', 'Realized P&L', 'Order ID'];
                        const csvRows = orders.map(order => {
                          const value = order.size * order.price;
                          return [
                            escapeCSV(order.time.toLocaleDateString('en-US')),
                            escapeCSV(order.time.toLocaleTimeString('en-US', { hour12: false })),
                            escapeCSV(order.asset),
                            escapeCSV(order.side),
                            escapeCSV(order.size.toFixed(4)),
                            escapeCSV(order.price.toFixed(2)),
                            escapeCSV(value.toFixed(2)),
                            escapeCSV((order.commission || 0).toFixed(4)),
                            escapeCSV(((order as any).realizedPnl || 0).toFixed(2)),
                            escapeCSV(order.orderId || '')
                          ].join(',');
                        });

                        const csvContent = [csvHeaders.join(','), ...csvRows].join('\n');
                        const blob = new Blob([csvContent], { type: 'text/csv' });
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `trades_${new Date().toISOString().split('T')[0]}.csv`;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        window.URL.revokeObjectURL(url);

                        addLog('EXPORT', `Exported ${orders.length} trades to CSV`, 'info');
                      }}
                      className="text-xs px-2 py-1 bg-green-600 hover:bg-green-700 text-white rounded"
                    >
                      Export CSV
                    </button>
                  )}
                </div>
              </div>
              {orders.length > 10 && (
                <div className="flex items-center gap-4 px-2 py-1 bg-gray-50 rounded text-xs">
                  <div>
                    <span className="text-gray-600">24h P&L: </span>
                    <span className={`font-semibold ${
                      (() => {
                        const today = new Date();
                        today.setHours(0, 0, 0, 0);
                        return orders
                          .filter(o => o.time >= today)
                          .reduce((sum, o) => sum + ((o as any).realizedPnl || 0), 0);
                      })() >= 0
                        ? 'text-green-600'
                        : 'text-red-600'
                    }`}>
                      ${Math.abs((() => {
                        const today = new Date();
                        today.setHours(0, 0, 0, 0);
                        return orders
                          .filter(o => o.time >= today)
                          .reduce((sum, o) => sum + ((o as any).realizedPnl || 0), 0);
                      })()).toFixed(2)}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-600">Today: </span>
                    <span className="font-semibold">
                      {(() => {
                        const today = new Date();
                        today.setHours(0, 0, 0, 0);
                        return orders.filter(o => o.time >= today).length;
                      })()} trades
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-600">Avg Size: </span>
                    <span className="font-semibold">
                      ${(orders.reduce((sum, o) => sum + (o.size * o.price), 0) / Math.max(orders.length, 1)).toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0})}
                    </span>
                  </div>
                </div>
              )}
            </div>
            <div className="overflow-x-auto max-h-96">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-white">
                  <tr className="border-b border-neutral-200">
                    <th className="text-left py-2 text-xs font-medium text-neutral-600 uppercase">Time</th>
                    <th className="text-left py-2 text-xs font-medium text-neutral-600 uppercase">Symbol</th>
                    <th className="text-center py-2 text-xs font-medium text-neutral-600 uppercase">Side</th>
                    <th className="text-right py-2 text-xs font-medium text-neutral-600 uppercase">Qty</th>
                    <th className="text-right py-2 text-xs font-medium text-neutral-600 uppercase">Price</th>
                    <th className="text-right py-2 text-xs font-medium text-neutral-600 uppercase">Value</th>
                    <th className="text-right py-2 text-xs font-medium text-neutral-600 uppercase">Fee</th>
                    <th className="text-right py-2 text-xs font-medium text-neutral-600 uppercase">P&L</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {orders.length > 0 ? orders.slice(0, 200).map((order, idx) => {
                    const realizedPnl = (order as any).realizedPnl || 0;
                    const commission = (order as any).commission || 0;
                    const value = order.size * order.price;

                    return (
                      <tr key={idx} className="hover:bg-gray-50">
                        <td className="py-1.5">
                          <div className="text-xs">
                            {order.time.toLocaleDateString('en-US', {
                              month: 'short',
                              day: 'numeric'
                            })}
                          </div>
                          <div className="text-gray-500 text-xs">
                            {order.time.toLocaleTimeString('en-US', {
                              hour: '2-digit',
                              minute: '2-digit',
                              hour12: false
                            })}
                          </div>
                        </td>
                        <td className="py-1.5">
                          <div className="font-medium text-xs">{order.asset}</div>
                          {order.orderId && (
                            <div className="text-gray-400 text-xs">#{order.orderId.toString().slice(-8)}</div>
                          )}
                        </td>
                        <td className="py-1.5 text-center">
                          <span className={`inline-flex px-1.5 py-0.5 text-xs font-semibold rounded-full ${
                            order.side === 'BUY'
                              ? 'bg-green-100 text-green-800'
                              : 'bg-red-100 text-red-800'
                          }`}>
                            {order.side}
                          </span>
                        </td>
                        <td className="py-1.5 text-right font-mono text-xs">{order.size.toFixed(4)}</td>
                        <td className="py-1.5 text-right font-mono text-xs">${order.price.toFixed(2)}</td>
                        <td className="py-1.5 text-right font-mono text-xs">${value.toFixed(2)}</td>
                        <td className="py-1.5 text-right text-gray-500 text-xs">
                          ${commission.toFixed(2)}
                        </td>
                        <td className="py-1.5 text-right">
                          {realizedPnl !== 0 ? (
                            <span className={`font-semibold text-xs ${
                              realizedPnl >= 0 ? 'text-green-600' : 'text-red-600'
                            }`}>
                              {realizedPnl >= 0 ? '+' : ''}${Math.abs(realizedPnl).toFixed(2)}
                            </span>
                          ) : (
                            <span className="text-xs text-gray-400">-</span>
                          )}
                        </td>
                      </tr>
                    );
                  }) : (
                    <tr>
                      <td colSpan={8} className="py-8 text-center text-sm text-neutral-400">
                        {apiConnected ? (
                          <div>
                            <p className="mb-2">No transaction history available</p>
                            <p className="text-xs">Transactions will appear here once you start trading</p>
                          </div>
                        ) : (
                          'Connect API to view transaction history'
                        )}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Summary Stats */}
            {orders.length > 0 && (
              <div className="mt-4 pt-3 border-t border-gray-200">
                <div className="grid grid-cols-4 gap-4 text-xs">
                  <div>
                    <span className="text-gray-500">Total Trades: </span>
                    <span className="font-semibold">{orders.length}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Volume: </span>
                    <span className="font-semibold">
                      ${orders.reduce((sum, o) => sum + (o.size * o.price), 0).toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0})}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Total P&L: </span>
                    <span className={`font-semibold ${
                      orders.reduce((sum, o) => sum + ((o as any).realizedPnl || 0), 0) >= 0
                        ? 'text-green-600'
                        : 'text-red-600'
                    }`}>
                      ${Math.abs(orders.reduce((sum, o) => sum + ((o as any).realizedPnl || 0), 0)).toFixed(2)}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Win Rate: </span>
                    <span className="font-semibold">
                      {(() => {
                        const wins = orders.filter(o => ((o as any).realizedPnl || 0) > 0).length;
                        const total = orders.filter(o => ((o as any).realizedPnl || 0) !== 0).length;
                        return total > 0 ? `${((wins / total) * 100).toFixed(0)}%` : '-';
                      })()}
                    </span>
                  </div>
                </div>
                {orders.length > 200 && (
                  <div className="mt-2 text-center text-xs text-gray-500">
                    Showing first 200 of {orders.length} trades
                  </div>
                )}
              </div>
            )}
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

    </>
  );
}