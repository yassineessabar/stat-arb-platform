import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';
import fs from 'fs/promises';

const execAsync = promisify(exec);

export async function POST(req: NextRequest) {
  try {
    const { startDate, endDate } = await req.json();

    // Path to Python script
    const scriptPath = path.join(process.cwd(), '..', 'scripts', 'run_backtest.py');

    // Run backtest Python script
    const command = `python3 ${scriptPath} --start-date ${startDate} --end-date ${endDate}`;

    const { stdout, stderr } = await execAsync(command);

    if (stderr) {
      console.error('Backtest stderr:', stderr);
    }

    // Parse results from stdout or read from saved file
    const resultsPattern = /Results saved to: (.+\.pkl)/;
    const match = stdout.match(resultsPattern);

    if (match) {
      const resultsFile = match[1];
      // Read and parse results (would need Python service to convert pickle)
      return NextResponse.json({
        success: true,
        message: 'Backtest completed',
        resultsFile,
        output: stdout
      });
    }

    return NextResponse.json({
      success: true,
      output: stdout
    });

  } catch (error) {
    console.error('Backtest error:', error);
    return NextResponse.json(
      { error: 'Failed to run backtest' },
      { status: 500 }
    );
  }
}

export async function GET(req: NextRequest) {
  try {
    // List available backtest results
    const resultsDir = path.join(process.cwd(), '..');
    const files = await fs.readdir(resultsDir);

    const backtestFiles = files
      .filter(f => f.startsWith('backtest_results_') && f.endsWith('.pkl'))
      .sort()
      .reverse();

    return NextResponse.json({
      success: true,
      files: backtestFiles
    });

  } catch (error) {
    console.error('Error listing backtests:', error);
    return NextResponse.json(
      { error: 'Failed to list backtests' },
      { status: 500 }
    );
  }
}