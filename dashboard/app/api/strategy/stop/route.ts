import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';
import { createClient } from '@supabase/supabase-js';

const execAsync = promisify(exec);

// Initialize Supabase client
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!
const supabase = createClient(supabaseUrl, supabaseServiceKey)

export async function POST(request: Request) {
  try {
    const { processId } = await request.json();

    if (!processId) {
      return NextResponse.json({
        success: false,
        error: 'Process ID is required'
      }, { status: 400 });
    }

    // Get the config file to find the PID
    const configPath = path.join(process.cwd(), 'strategy_configs', `${processId}.json`);

    // Check if config exists
    if (!fs.existsSync(configPath)) {
      return NextResponse.json({
        success: false,
        error: 'Strategy configuration not found. Strategy may have already stopped.'
      }, { status: 404 });
    }

    // Read the log file to get the system PID
    const logPath = path.join(process.cwd(), 'strategy_logs', `${processId}.log`);
    let systemPid: string | null = null;

    if (fs.existsSync(logPath)) {
      const logContent = fs.readFileSync(logPath, 'utf-8');
      const pidMatch = logContent.match(/System PID: (\d+)/);
      if (pidMatch) {
        systemPid = pidMatch[1];
      }
    }

    // Try to stop the process
    let stopped = false;
    let message = '';

    if (systemPid) {
      try {
        // Send SIGTERM signal to gracefully stop the process
        if (process.platform === 'win32') {
          // Windows
          await execAsync(`taskkill /PID ${systemPid} /F`);
        } else {
          // Unix-like (Mac, Linux)
          await execAsync(`kill -TERM ${systemPid}`);
        }
        stopped = true;
        message = `Strategy process (PID: ${systemPid}) stopped successfully`;
      } catch (error) {
        // Process might have already stopped
        console.log(`Could not stop process ${systemPid}:`, error);
        message = 'Strategy process may have already stopped';
      }
    }

    // Log the stop event
    if (fs.existsSync(logPath)) {
      const logStream = fs.createWriteStream(logPath, { flags: 'a' });
      logStream.write(`\n[${new Date().toISOString()}] Strategy stop requested\n`);
      logStream.write(`[${new Date().toISOString()}] ${message}\n`);
      logStream.end();
    }

    // Update strategy status in database
    try {
      const { error: dbError } = await supabase
        .from('strategy_deployments')
        .update({
          status: 'stopped',
          stopped_at: new Date().toISOString()
        })
        .eq('process_id', processId)

      if (dbError) {
        console.error('Database update error:', dbError)
      }

      // Log stop event to database
      await supabase.from('system_logs').insert([{
        log_level: 'info',
        log_type: 'deployment',
        message: `Strategy ${processId} stopped successfully (PID: ${systemPid})`
      }])

    } catch (dbError) {
      console.error('Database error during stop:', dbError)
    }

    // Archive the config file (don't delete, keep for history)
    const archivedConfigPath = configPath.replace('.json', `_stopped_${Date.now()}.json`);
    fs.renameSync(configPath, archivedConfigPath);

    return NextResponse.json({
      success: true,
      message,
      processId,
      systemPid,
      archivedConfig: archivedConfigPath
    });

  } catch (error) {
    console.error('Strategy stop error:', error);
    return NextResponse.json({
      success: false,
      error: error instanceof Error ? error.message : 'Failed to stop strategy'
    }, { status: 500 });
  }
}

export async function GET() {
  // Get list of running strategies by checking config files
  const configDir = path.join(process.cwd(), 'strategy_configs');

  if (!fs.existsSync(configDir)) {
    return NextResponse.json({
      strategies: [],
      count: 0
    });
  }

  const files = fs.readdirSync(configDir);
  const activeStrategies = files
    .filter(f => f.endsWith('.json') && !f.includes('_stopped_'))
    .map(f => {
      const configPath = path.join(configDir, f);
      const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
      const processId = f.replace('.json', '');

      // Check if log file exists and get last update
      const logPath = path.join(process.cwd(), 'strategy_logs', `${processId}.log`);
      let lastUpdate = null;
      let status = 'unknown';

      if (fs.existsSync(logPath)) {
        const stats = fs.statSync(logPath);
        lastUpdate = stats.mtime;

        // If log hasn't been updated in 5 minutes, consider it stopped
        const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
        status = stats.mtime > fiveMinutesAgo ? 'running' : 'stale';
      }

      return {
        processId,
        strategy_name: config.strategy_name,
        trading_mode: config.trading_mode,
        symbols: `${config.symbol_1}/${config.symbol_2}`,
        lastUpdate,
        status
      };
    });

  return NextResponse.json({
    strategies: activeStrategies,
    count: activeStrategies.length
  });
}