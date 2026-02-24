import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const processId = searchParams.get('processId');
    const lines = parseInt(searchParams.get('lines') || '100');

    if (!processId) {
      return NextResponse.json({
        success: false,
        error: 'Process ID is required'
      }, { status: 400 });
    }

    // Get the log file path
    const logPath = path.join(process.cwd(), 'strategy_logs', `${processId}.log`);

    if (!fs.existsSync(logPath)) {
      return NextResponse.json({
        success: false,
        error: 'Log file not found'
      }, { status: 404 });
    }

    // Read the log file
    const logContent = fs.readFileSync(logPath, 'utf-8');
    const logLines = logContent.split('\n').filter(line => line.trim().length > 0);

    // Get the last N lines
    const recentLines = logLines.slice(-lines);

    // Parse log lines into structured format
    const parsedLogs = recentLines.map(line => {
      // Parse timestamp and log level from Python logging format
      // Example: "2026-02-23 20:50:57,189 - __main__ - INFO - SIGNAL CHECK - Current z-score: 0.39"
      const match = line.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - .* - (\w+) - (.*)$/);

      if (match) {
        const [, timestamp, level, message] = match;
        return {
          timestamp: new Date(timestamp.replace(',', '.')), // Convert Python timestamp format
          level: level.toLowerCase(),
          message: message.trim(),
          raw: line
        };
      }

      // Fallback for lines that don't match the pattern
      return {
        timestamp: new Date(),
        level: 'info',
        message: line.trim(),
        raw: line
      };
    });

    return NextResponse.json({
      success: true,
      logs: parsedLogs,
      totalLines: logLines.length,
      processId
    });

  } catch (error) {
    console.error('Error reading strategy logs:', error);
    return NextResponse.json({
      success: false,
      error: error instanceof Error ? error.message : 'Failed to read logs'
    }, { status: 500 });
  }
}