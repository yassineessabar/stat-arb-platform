# EC2 Live Log Integration Setup

This guide explains how to connect your dashboard to your EC2 instance to display real-time logs from `enhanced_strategy_executor_fixed.py`.

## Prerequisites

1. **EC2 Instance**: Running with your strategy script
2. **SSH Access**: Private key file (.pem) with proper permissions
3. **Strategy Logs**: The script should output logs to a file

## Setup Steps

### 1. Configure Environment Variables

Edit the `.env.local` file in the dashboard directory and update these values:

```bash
# Your EC2 instance public IP or DNS name
EC2_HOST=ec2-52-14-123-45.us-east-2.compute.amazonaws.com

# Username (usually 'ubuntu' for Ubuntu instances)
EC2_USER=ubuntu

# Path to your private key file
EC2_KEY_PATH=/Users/yourusername/.ssh/your-ec2-key.pem

# Project directory on EC2
EC2_PROJECT_PATH=/home/ubuntu/stat-arb-platform
```

### 2. Ensure SSH Key Permissions

```bash
chmod 400 /path/to/your-ec2-key.pem
```

### 3. Verify SSH Access

Test that you can connect to your EC2 instance:

```bash
ssh -i /path/to/your-ec2-key.pem ubuntu@your-ec2-host
```

### 4. Strategy Log File

Ensure your `enhanced_strategy_executor_fixed.py` outputs logs to a file. Add logging configuration:

```python
import logging

# Configure logging to file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('strategy_logs.txt'),
        logging.StreamHandler()  # Also output to console
    ]
)

# In your strategy loop:
logging.info("🔄 ITERATION #%d - %s", iteration, datetime.now().strftime("%H:%M:%S"))
logging.info("📊 MARKET ANALYSIS (V6 PARAMETERS)")
# ... other log messages
```

### 5. Test the Connection

Once configured, the dashboard will:

1. **Try to connect** to your EC2 instance via SSH
2. **Check if the strategy is running** using `ps aux | grep enhanced_strategy_executor_fixed.py`
3. **Fetch recent logs** from `strategy_logs.txt`
4. **Parse and display** the logs in real-time
5. **Fall back to simulated logs** if the connection fails

### 6. Verify It's Working

1. Open the dashboard: `http://localhost:3002/execution`
2. Check the "Real-Time Strategy Logs (Live from EC2)" section
3. Look for logs without "(SIMULATED)" in the messages

## Troubleshooting

### Connection Issues

1. **Check SSH key permissions**: `ls -la /path/to/your-key.pem` should show `-r--------`
2. **Verify EC2 security group**: Ensure SSH (port 22) is open from your IP
3. **Test manual SSH**: `ssh -i /path/to/key.pem ubuntu@your-ec2-host`

### Log File Issues

1. **Check if log file exists**: `ls -la strategy_logs.txt` on EC2
2. **Verify file permissions**: The file should be readable
3. **Check strategy process**: `ps aux | grep enhanced_strategy_executor_fixed.py`

### Dashboard Shows Simulated Logs

This happens when:
- EC2 connection fails (wrong credentials, network issues)
- Strategy is not currently running
- Log file doesn't exist or is empty

Check the browser console for SSH connection error details.

## Security Notes

- Never commit your private key to git
- Use restrictive permissions on key files (400)
- Consider using AWS Systems Manager Session Manager instead of SSH for enhanced security
- Monitor EC2 access logs

## Alternative: CloudWatch Integration

For production deployments, consider using AWS CloudWatch logs instead of SSH:

```typescript
// Future enhancement - CloudWatch integration
import { CloudWatchLogsClient, GetLogEventsCommand } from '@aws-sdk/client-cloudwatch-logs';

const client = new CloudWatchLogsClient({ region: 'us-east-1' });
const command = new GetLogEventsCommand({
  logGroupName: '/aws/ec2/strategy-logs',
  logStreamName: 'enhanced-strategy-executor'
});
```

This approach is more secure and scalable for production use.