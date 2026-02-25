import formidable from 'formidable';
import fs from 'fs';
import path from 'path';

// Store EC2 connections in memory (in production, use Redis or database)
global.ec2Connections = global.ec2Connections || new Map();

export const config = {
    api: {
        bodyParser: false,
    },
};

export default async function handler(req, res) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    const form = new formidable.IncomingForm({
        uploadDir: '/tmp',
        keepExtensions: true,
    });

    form.parse(req, async (err, fields, files) => {
        if (err) {
            return res.status(500).json({ error: 'Failed to parse form data' });
        }

        try {
            const { host, username = 'ubuntu', instanceId } = fields;
            const keyFile = files.keyFile;

            if (!host || !keyFile) {
                return res.status(400).json({ error: 'Host and key file are required' });
            }

            // Read the private key
            const privateKey = fs.readFileSync(keyFile.filepath, 'utf8');

            // Create SSH connection
            const { Client } = require('ssh2');
            const conn = new Client();

            await new Promise((resolve, reject) => {
                conn.on('ready', () => {
                    console.log(`Connected to EC2: ${host}`);

                    // Store connection
                    global.ec2Connections.set(instanceId || host, {
                        connection: conn,
                        host,
                        username,
                        connectedAt: new Date(),
                        logs: []
                    });

                    resolve();
                });

                conn.on('error', reject);

                conn.connect({
                    host,
                    port: 22,
                    username,
                    privateKey
                });
            });

            // Start monitoring logs
            startLogStream(conn, instanceId || host);

            res.status(200).json({
                success: true,
                message: 'Connected to EC2 instance',
                instanceId: instanceId || host
            });

        } catch (error) {
            console.error('Connection error:', error);
            res.status(500).json({
                error: 'Failed to connect',
                message: error.message
            });
        }
    });
}

function startLogStream(conn, instanceId) {
    // Stream logs from the Python script
    conn.exec('tail -f ~/stat-arb-platform/trading.log 2>&1 || python3 ~/stat-arb-platform/src/enhanced_strategy_executor.py 2>&1', (err, stream) => {
        if (err) {
            console.error('Error starting log stream:', err);
            return;
        }

        stream.on('data', (data) => {
            const logLine = data.toString();
            const ec2Data = global.ec2Connections.get(instanceId);

            if (ec2Data) {
                // Store log
                ec2Data.logs.push({
                    timestamp: new Date().toISOString(),
                    message: logLine,
                    type: detectLogType(logLine)
                });

                // Keep only last 1000 lines
                if (ec2Data.logs.length > 1000) {
                    ec2Data.logs.shift();
                }
            }
        });
    });
}

function detectLogType(logLine) {
    if (logLine.includes('ERROR') || logLine.includes('❌')) return 'error';
    if (logLine.includes('WARNING') || logLine.includes('⚠️')) return 'warning';
    if (logLine.includes('BUY') || logLine.includes('🟢')) return 'buy';
    if (logLine.includes('SELL') || logLine.includes('🔴')) return 'sell';
    if (logLine.includes('PROFIT') || logLine.includes('💰')) return 'profit';
    if (logLine.includes('LOSS') || logLine.includes('⛔')) return 'loss';
    return 'info';
}