import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export async function POST(request: NextRequest) {
  try {
    // EC2 connection details from environment variables
    const EC2_HOST = process.env.EC2_HOST;
    const EC2_USER = process.env.EC2_USER || 'ubuntu';
    const EC2_KEY_PATH = process.env.EC2_KEY_PATH;
    const EC2_PROJECT_PATH = process.env.EC2_PROJECT_PATH || 'stat-arb-platform';

    if (!EC2_HOST || !EC2_KEY_PATH) {
      return NextResponse.json({
        success: false,
        error: 'EC2 connection configuration not found in environment variables'
      }, { status: 400 });
    }

    // SSH command to stop the strategy on EC2
    const sshCommand = `ssh -i "${EC2_KEY_PATH}" -o ConnectTimeout=10 -o StrictHostKeyChecking=no ${EC2_USER}@${EC2_HOST}`;

    // Commands to stop the strategy process (with || true to avoid failure on no match)
    const stopCommands = [
      // Kill any existing Python strategy processes
      `pkill -f "python.*enhanced_strategy_executor" || true`,
      `pkill -f "python.*strategy_executor" || true`,
      `pkill -f "python.*stat.*arb" || true`,
      // Also check for any screen sessions and kill them
      `screen -wipe || true`,
      `pkill screen || true`,
      // Clean logs for fresh start
      `rm -f strategy_logs.txt || true`
    ].join(' && ');

    const fullCommand = `${sshCommand} 'cd ${EC2_PROJECT_PATH} && ${stopCommands}'`;

    console.log('🔴 Stopping strategy on EC2 server...');

    // Execute the stop command
    const { stdout, stderr } = await execAsync(fullCommand);

    console.log('✅ Strategy stop command executed');
    if (stdout) console.log('stdout:', stdout);
    if (stderr) console.log('stderr:', stderr);

    return NextResponse.json({
      success: true,
      message: 'Strategy stopped on EC2 server',
      output: stdout,
      errors: stderr
    });

  } catch (error) {
    console.error('❌ Error stopping strategy on EC2:', error);

    return NextResponse.json({
      success: false,
      error: error instanceof Error ? error.message : 'Failed to stop strategy on EC2',
      details: error instanceof Error ? error.stack : undefined
    }, { status: 500 });
  }
}