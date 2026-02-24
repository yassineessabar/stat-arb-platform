import { NextResponse } from 'next/server';
import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';
import { createClient } from '@supabase/supabase-js';

interface StrategyConfig {
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
  api_key: string;
  api_secret: string;
  testnet: boolean;
}

// Store active strategy processes
const activeStrategies = new Map<string, any>();

// Initialize Supabase client
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!
const supabase = createClient(supabaseUrl, supabaseServiceKey)

export async function POST(request: Request) {
  try {
    const config: StrategyConfig = await request.json();

    // Validate configuration
    if (!config.api_key || !config.api_secret) {
      return NextResponse.json({
        success: false,
        error: 'API credentials are required'
      }, { status: 400 });
    }

    if (!config.symbol_1 || !config.symbol_2) {
      return NextResponse.json({
        success: false,
        error: 'Trading symbols are required'
      }, { status: 400 });
    }

    // Generate unique process ID
    const processId = `strategy_${Date.now()}_${Math.random().toString(36).substring(7)}`;

    // Create config file for the strategy
    const configDir = path.join(process.cwd(), 'strategy_configs');
    if (!fs.existsSync(configDir)) {
      fs.mkdirSync(configDir, { recursive: true });
    }

    const configPath = path.join(configDir, `${processId}.json`);
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2));

    // Get the Python executable path
    const pythonPath = process.platform === 'win32' ? 'python' : 'python3';

    // Path to the strategy executor script
    const scriptPath = path.join(process.cwd(), 'strategy_executor.py');

    // Check if script exists
    if (!fs.existsSync(scriptPath)) {
      return NextResponse.json({
        success: false,
        error: 'Strategy executor script not found. Please ensure strategy_executor.py is in the project root.'
      }, { status: 500 });
    }

    // Spawn the Python process with process ID for tracking
    const strategyProcess = spawn(pythonPath, [
      scriptPath,
      '--config', configPath,
      '--process-id', processId
    ], {
      detached: true,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    // Store process reference
    activeStrategies.set(processId, {
      process: strategyProcess,
      config: config,
      startTime: new Date(),
      pid: strategyProcess.pid
    });

    // Log output
    const logDir = path.join(process.cwd(), 'strategy_logs');
    if (!fs.existsSync(logDir)) {
      fs.mkdirSync(logDir, { recursive: true });
    }

    const logPath = path.join(logDir, `${processId}.log`);
    const logStream = fs.createWriteStream(logPath, { flags: 'a' });

    strategyProcess.stdout?.pipe(logStream);
    strategyProcess.stderr?.pipe(logStream);

    // Handle process events
    strategyProcess.on('error', (error) => {
      console.error(`Strategy process error: ${error}`);
      activeStrategies.delete(processId);
    });

    strategyProcess.on('exit', (code, signal) => {
      console.log(`Strategy process exited with code ${code} and signal ${signal}`);
      activeStrategies.delete(processId);
    });

    // Log initial deployment
    logStream.write(`[${new Date().toISOString()}] Strategy deployed: ${config.strategy_name}\n`);
    logStream.write(`[${new Date().toISOString()}] Mode: ${config.trading_mode}\n`);
    logStream.write(`[${new Date().toISOString()}] Engine: ${config.use_v6_engine ? 'v6 Backtest Engine' : 'Simple Strategy'}\n`);
    if (config.use_v6_engine && config.universe) {
      logStream.write(`[${new Date().toISOString()}] Universe: ${config.universe.join(', ')}\n`);
    } else {
      logStream.write(`[${new Date().toISOString()}] Symbols: ${config.symbol_1} / ${config.symbol_2}\n`);
    }
    logStream.write(`[${new Date().toISOString()}] Process ID: ${processId}\n`);
    logStream.write(`[${new Date().toISOString()}] System PID: ${strategyProcess.pid}\n`);

    // Save strategy deployment to database
    try {
      const { data: deployment, error: dbError } = await supabase
        .from('strategy_deployments')
        .insert([{
          user_id: null, // No user authentication for now
          process_id: processId,
          strategy_name: config.strategy_name,
          trading_mode: config.trading_mode,
          status: 'running',
          symbol_1: config.universe?.[0] || config.symbol_1 || 'MULTI',
          symbol_2: config.universe?.[1] || config.symbol_2 || 'PAIR',
          entry_z_score: 1.0,  // V6 default
          exit_z_score: 0.2,   // V6 default
          position_size: config.position_size || 1000,
          max_positions: 30,   // V6 default
          total_trades: 0,
          total_pnl: 0
        }])
        .select()

      if (dbError) {
        console.error('❌ Database save error:', JSON.stringify(dbError, null, 2))
        logStream.write(`[${new Date().toISOString()}] ❌ Database save error: ${JSON.stringify(dbError)}\n`)
        // Continue anyway - don't fail deployment for DB issues
      } else if (deployment && deployment.length > 0) {
        console.log('✅ Strategy saved to database with ID:', deployment[0].id)
        logStream.write(`[${new Date().toISOString()}] ✅ Strategy saved to database with ID: ${deployment[0].id}\n`)
      } else {
        console.error('❌ Database save failed: No data returned')
        logStream.write(`[${new Date().toISOString()}] ❌ Database save failed: No data returned\n`)
      }

      // Log deployment to database
      await supabase.from('system_logs').insert([{
        deployment_id: deployment?.[0]?.id,
        log_level: 'info',
        log_type: 'deployment',
        message: `Strategy ${config.strategy_name} deployed in ${config.trading_mode} mode (PID: ${strategyProcess.pid})`
      }])

    } catch (dbError) {
      console.error('Database error:', dbError)
      // Don't fail the deployment for database issues
    }

    // Don't wait for the subprocess (let it run in background)
    strategyProcess.unref();

    return NextResponse.json({
      success: true,
      processId: processId,
      pid: strategyProcess.pid,
      message: `Strategy deployed successfully in ${config.trading_mode} mode`,
      logFile: `strategy_logs/${processId}.log`,
      configFile: `strategy_configs/${processId}.json`
    });

  } catch (error) {
    console.error('Strategy deployment error:', error);
    return NextResponse.json({
      success: false,
      error: error instanceof Error ? error.message : 'Failed to deploy strategy'
    }, { status: 500 });
  }
}

export async function GET() {
  try {
    // Get list of active strategies from database
    const { data: strategies, error } = await supabase
      .from('strategy_deployments')
      .select('*')
      .order('deployed_at', { ascending: false })

    if (error) {
      console.error('Database fetch error:', error)
      return NextResponse.json({ error: 'Failed to fetch strategies' }, { status: 500 })
    }

    const formattedStrategies = strategies?.map(strategy => ({
      processId: strategy.process_id,
      pid: strategy.system_pid,
      strategy_name: strategy.strategy_name,
      trading_mode: strategy.trading_mode,
      symbols: `${strategy.symbol_1}/${strategy.symbol_2}`,
      startTime: strategy.deployed_at,
      status: strategy.status,
      totalTrades: strategy.total_trades,
      totalPnl: strategy.total_pnl
    })) || []

    return NextResponse.json({
      strategies: formattedStrategies,
      count: formattedStrategies.length
    });
  } catch (error) {
    console.error('Error fetching strategies:', error)
    return NextResponse.json({ error: 'Failed to fetch strategies' }, { status: 500 })
  }
}