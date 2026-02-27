import { NextResponse } from 'next/server';
import { Client } from 'ssh2';
import fs from 'fs';
import path from 'path';

export async function POST() {
  const conn = new Client();

  // EC2 connection details
  const EC2_HOST = process.env.EC2_HOST || '54.169.148.35';
  const EC2_USER = process.env.EC2_USER || 'ubuntu';
  const SSH_KEY_PATH = process.env.SSH_KEY_PATH || path.join(process.env.HOME || '/tmp', '.ssh', 'your-key.pem');

  return new Promise((resolve) => {
    let output = '';
    let errorOutput = '';

    conn.on('ready', () => {
      console.log('🔗 SSH Connection established');

      // Execute the kill script on EC2
      const killCommand = `
        cd /home/ubuntu/stat-arb-platform && \
        python3 scripts/kill_all_processes.py 2>&1
      `;

      conn.exec(killCommand, (err, stream) => {
        if (err) {
          conn.end();
          resolve(NextResponse.json({
            success: false,
            error: err.message
          }, { status: 500 }));
          return;
        }

        stream.on('close', (code: number) => {
          conn.end();

          if (code === 0) {
            resolve(NextResponse.json({
              success: true,
              message: 'All processes terminated successfully',
              output: output,
              terminatedCount: (output.match(/Successfully killed/g) || []).length
            }));
          } else {
            resolve(NextResponse.json({
              success: false,
              error: errorOutput || 'Failed to terminate processes',
              output: output
            }, { status: 500 }));
          }
        });

        stream.on('data', (data: Buffer) => {
          output += data.toString();
          console.log('EC2 Output:', data.toString());
        });

        stream.stderr.on('data', (data: Buffer) => {
          errorOutput += data.toString();
          console.error('EC2 Error:', data.toString());
        });
      });
    });

    conn.on('error', (err) => {
      console.error('SSH Connection error:', err);
      resolve(NextResponse.json({
        success: false,
        error: 'Failed to connect to EC2: ' + err.message
      }, { status: 500 }));
    });

    // Check if SSH key exists
    if (!fs.existsSync(SSH_KEY_PATH)) {
      resolve(NextResponse.json({
        success: false,
        error: 'SSH key not found. Please configure SSH_KEY_PATH environment variable.'
      }, { status: 500 }));
      return;
    }

    // Connect to EC2
    conn.connect({
      host: EC2_HOST,
      port: 22,
      username: EC2_USER,
      privateKey: fs.readFileSync(SSH_KEY_PATH),
      readyTimeout: 10000
    });
  });
}

// GET endpoint to check if any processes are running
export async function GET() {
  const conn = new Client();

  const EC2_HOST = process.env.EC2_HOST || '54.169.148.35';
  const EC2_USER = process.env.EC2_USER || 'ubuntu';
  const SSH_KEY_PATH = process.env.SSH_KEY_PATH || path.join(process.env.HOME || '/tmp', '.ssh', 'your-key.pem');

  return new Promise((resolve) => {
    let output = '';

    conn.on('ready', () => {
      // Check for running processes
      const checkCommand = `
        ps aux | grep -E 'python.*(strategy|executor|trading|binance)' | grep -v grep | wc -l
      `;

      conn.exec(checkCommand, (err, stream) => {
        if (err) {
          conn.end();
          resolve(NextResponse.json({
            success: false,
            error: err.message
          }, { status: 500 }));
          return;
        }

        stream.on('close', () => {
          conn.end();

          const processCount = parseInt(output.trim()) || 0;

          resolve(NextResponse.json({
            success: true,
            processCount: processCount,
            hasRunningProcesses: processCount > 0,
            message: processCount > 0
              ? `${processCount} trading processes are currently running`
              : 'No trading processes are running'
          }));
        });

        stream.on('data', (data: Buffer) => {
          output += data.toString();
        });
      });
    });

    conn.on('error', (err) => {
      resolve(NextResponse.json({
        success: false,
        error: 'Failed to connect to EC2: ' + err.message
      }, { status: 500 }));
    });

    if (!fs.existsSync(SSH_KEY_PATH)) {
      resolve(NextResponse.json({
        success: false,
        error: 'SSH key not found'
      }, { status: 500 }));
      return;
    }

    conn.connect({
      host: EC2_HOST,
      port: 22,
      username: EC2_USER,
      privateKey: fs.readFileSync(SSH_KEY_PATH),
      readyTimeout: 10000
    });
  });
}