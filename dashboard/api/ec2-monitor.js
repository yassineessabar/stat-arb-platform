// EC2 SSH Connection and Monitoring API
const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

class EC2Monitor {
    constructor() {
        this.connections = new Map();
        this.logs = new Map();
    }

    async connect(instanceId, config) {
        return new Promise((resolve, reject) => {
            const conn = new Client();

            conn.on('ready', () => {
                console.log(`✅ Connected to EC2 instance: ${instanceId}`);
                this.connections.set(instanceId, conn);

                // Start monitoring logs
                this.startLogMonitoring(instanceId, conn);
                resolve({ success: true, instanceId });
            });

            conn.on('error', (err) => {
                console.error(`❌ Connection error for ${instanceId}:`, err);
                reject(err);
            });

            // Connect with SSH key
            const privateKey = fs.readFileSync(config.keyPath);

            conn.connect({
                host: config.host,
                port: 22,
                username: config.username || 'ubuntu',
                privateKey: privateKey
            });
        });
    }

    startLogMonitoring(instanceId, conn) {
        // Monitor the bot output
        conn.exec('tail -f ~/stat-arb-platform/trading.log 2>&1 || python3 ~/stat-arb-platform/src/enhanced_strategy_executor.py 2>&1', (err, stream) => {
            if (err) {
                console.error('Error starting log monitoring:', err);
                return;
            }

            let logBuffer = '';

            stream.on('data', (data) => {
                const logLine = data.toString();
                logBuffer += logLine;

                // Store logs
                if (!this.logs.has(instanceId)) {
                    this.logs.set(instanceId, []);
                }

                const logs = this.logs.get(instanceId);

                // Parse log line
                const timestamp = new Date().toISOString();
                logs.push({
                    timestamp,
                    message: logLine,
                    type: this.detectLogType(logLine)
                });

                // Keep only last 1000 log lines
                if (logs.length > 1000) {
                    logs.shift();
                }

                // Emit to connected clients via WebSocket
                this.emitLog(instanceId, {
                    timestamp,
                    message: logLine,
                    type: this.detectLogType(logLine)
                });
            });

            stream.on('close', () => {
                console.log(`Log stream closed for ${instanceId}`);
            });
        });
    }

    detectLogType(logLine) {
        if (logLine.includes('ERROR') || logLine.includes('❌')) return 'error';
        if (logLine.includes('WARNING') || logLine.includes('⚠️')) return 'warning';
        if (logLine.includes('BUY') || logLine.includes('🟢')) return 'buy';
        if (logLine.includes('SELL') || logLine.includes('🔴')) return 'sell';
        if (logLine.includes('PROFIT') || logLine.includes('💰')) return 'profit';
        if (logLine.includes('LOSS') || logLine.includes('⛔')) return 'loss';
        if (logLine.includes('Z-Score')) return 'signal';
        return 'info';
    }

    async executeCommand(instanceId, command) {
        const conn = this.connections.get(instanceId);
        if (!conn) {
            throw new Error(`No connection for instance ${instanceId}`);
        }

        return new Promise((resolve, reject) => {
            conn.exec(command, (err, stream) => {
                if (err) {
                    reject(err);
                    return;
                }

                let output = '';
                stream.on('data', (data) => {
                    output += data.toString();
                });

                stream.on('close', () => {
                    resolve(output);
                });
            });
        });
    }

    async getStatus(instanceId) {
        try {
            // Check if bot is running
            const psOutput = await this.executeCommand(instanceId, 'ps aux | grep enhanced_strategy_executor | grep -v grep');
            const isRunning = psOutput.length > 0;

            // Get system stats
            const cpuOutput = await this.executeCommand(instanceId, 'top -bn1 | grep "Cpu(s)" | head -1');
            const memOutput = await this.executeCommand(instanceId, 'free -h | grep Mem');

            // Get last trade info from logs
            const logs = this.logs.get(instanceId) || [];
            const lastTrade = logs.reverse().find(log =>
                log.type === 'buy' || log.type === 'sell'
            );

            return {
                instanceId,
                isRunning,
                cpu: this.parseCpuUsage(cpuOutput),
                memory: this.parseMemoryUsage(memOutput),
                lastTrade,
                logCount: logs.length
            };
        } catch (error) {
            console.error('Error getting status:', error);
            return {
                instanceId,
                isRunning: false,
                error: error.message
            };
        }
    }

    parseCpuUsage(output) {
        // Parse CPU usage from top output
        const match = output.match(/(\d+\.\d+)%us/);
        return match ? parseFloat(match[1]) : 0;
    }

    parseMemoryUsage(output) {
        // Parse memory usage from free output
        const parts = output.split(/\s+/);
        if (parts.length >= 3) {
            return {
                total: parts[1],
                used: parts[2],
                free: parts[3]
            };
        }
        return { total: '0', used: '0', free: '0' };
    }

    getLogs(instanceId, limit = 100) {
        const logs = this.logs.get(instanceId) || [];
        return logs.slice(-limit);
    }

    disconnect(instanceId) {
        const conn = this.connections.get(instanceId);
        if (conn) {
            conn.end();
            this.connections.delete(instanceId);
            this.logs.delete(instanceId);
        }
    }

    // WebSocket support
    emitLog(instanceId, log) {
        // This will be connected to WebSocket server
        if (this.wsEmitter) {
            this.wsEmitter.emit('ec2-log', { instanceId, log });
        }
    }

    setWebSocketEmitter(emitter) {
        this.wsEmitter = emitter;
    }
}

module.exports = EC2Monitor;