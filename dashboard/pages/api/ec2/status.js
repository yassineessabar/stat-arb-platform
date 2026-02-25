export default async function handler(req, res) {
    const { instanceId } = req.query;

    if (!instanceId) {
        return res.status(400).json({ error: 'Instance ID is required' });
    }

    const ec2Data = global.ec2Connections?.get(instanceId);

    if (!ec2Data) {
        return res.status(404).json({ error: 'Instance not connected' });
    }

    const { connection } = ec2Data;

    try {
        // Check if bot is running
        const isRunning = await executeCommand(connection, 'ps aux | grep enhanced_strategy_executor | grep -v grep');

        // Get system stats
        const cpuInfo = await executeCommand(connection, 'top -bn1 | head -5');
        const memInfo = await executeCommand(connection, 'free -h');

        // Get last positions from log
        const lastTrade = ec2Data.logs
            .filter(log => log.type === 'buy' || log.type === 'sell')
            .slice(-1)[0];

        res.status(200).json({
            instanceId,
            connected: true,
            host: ec2Data.host,
            isRunning: isRunning.length > 0,
            systemInfo: {
                cpu: cpuInfo,
                memory: memInfo
            },
            lastTrade,
            logCount: ec2Data.logs.length
        });
    } catch (error) {
        res.status(500).json({
            error: 'Failed to get status',
            message: error.message
        });
    }
}

function executeCommand(conn, command) {
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