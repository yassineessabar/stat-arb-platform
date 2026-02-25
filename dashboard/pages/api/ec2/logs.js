export default async function handler(req, res) {
    const { instanceId, limit = 100 } = req.query;

    if (!instanceId) {
        return res.status(400).json({ error: 'Instance ID is required' });
    }

    const ec2Data = global.ec2Connections?.get(instanceId);

    if (!ec2Data) {
        return res.status(404).json({ error: 'Instance not connected' });
    }

    const logs = ec2Data.logs.slice(-limit);

    res.status(200).json({
        instanceId,
        connected: true,
        host: ec2Data.host,
        connectedAt: ec2Data.connectedAt,
        logs
    });
}