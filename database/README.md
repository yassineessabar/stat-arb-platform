# Database Setup for Statistical Arbitrage Platform

This directory contains the database schema and setup scripts for the Statistical Arbitrage Trading Platform using Supabase.

## 📋 Quick Setup

### Method 1: Manual Setup (Recommended)

1. **Open Supabase SQL Editor**
   - Go to [Supabase Dashboard](https://supabase.com/dashboard)
   - Navigate to your project: `hfmcbyqdibxdbimwkcwi`
   - Click on "SQL Editor" in the left sidebar

2. **Execute Schema**
   - Copy the contents of `quick_setup.sql`
   - Paste into the SQL Editor
   - Click "Run" to execute

3. **Verify Setup**
   - Go to "Table Editor" to see your new tables
   - Check "Authentication" -> "Users" for the demo user

### Method 2: Command Line Setup

If you have `psql` installed:

```bash
cd database
chmod +x run_setup.sh
./run_setup.sh
```

## 📊 Database Schema Overview

### Core Tables

**`users`** - User management and authentication
- Stores user profiles and account information
- Integrates with Supabase Auth

**`strategy_deployments`** - Active strategy tracking
- Records all deployed strategies with parameters
- Tracks performance metrics and status
- Links to positions and trades

**`positions`** - Trading position management
- Open and closed positions with entry/exit details
- P&L tracking and z-score information
- Links trades to specific positions

**`trades`** - Detailed execution history
- Individual trade records with prices and quantities
- Commission tracking and timing information
- Supports trade analysis and reporting

**`system_logs`** - Platform monitoring
- Strategy execution logs and errors
- API calls and system events
- Debugging and audit trail

### Database Features

✅ **Row Level Security (RLS)** - Users can only access their own data
✅ **Foreign Key Constraints** - Data integrity and relationships
✅ **Indexes** - Optimized query performance
✅ **Triggers** - Auto-updating timestamps
✅ **UUID Primary Keys** - Secure, scalable identifiers

## 🔧 Environment Configuration

Make sure your `.env.local` file contains:

```env
# Supabase Configuration
NEXT_PUBLIC_SUPABASE_URL=https://hfmcbyqdibxdbimwkcwi.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## 🔒 Security Features

### Row Level Security Policies

- **Users**: Can only view/edit their own profile
- **Deployments**: Users can only see their own strategies
- **Positions**: Users can only access their own trading positions
- **Trades**: Users can only view their own trade history
- **Logs**: Users can only see logs from their strategies

### Data Encryption

- API keys are stored encrypted using PostgreSQL's `pgcrypto`
- Sensitive data is protected with proper access controls
- Service role key required for system operations

## 📈 Usage Examples

### Creating a Strategy Deployment

```typescript
import { DatabaseService } from '@/lib/supabase'

const deployment = await DatabaseService.createDeployment({
  process_id: 'strategy_12345',
  strategy_name: 'MeanReversion_ETHBTC',
  trading_mode: 'paper',
  status: 'running',
  symbol_1: 'ETHUSDT',
  symbol_2: 'BTCUSDT',
  entry_z_score: 2.0,
  exit_z_score: 0.5,
  position_size: 1000,
  max_positions: 3
})
```

### Recording a Position

```typescript
const position = await DatabaseService.createPosition({
  deployment_id: deployment.id,
  position_id: 'LONG_1771834110',
  symbol_1: 'ETHUSDT',
  symbol_2: 'BTCUSDT',
  direction: 'LONG',
  status: 'open',
  entry_price_1: 1882.31,
  entry_price_2: 65730.10,
  entry_z_score: 0.85,
  position_size: 1000
})
```

### Getting Performance Metrics

```typescript
const metrics = await DatabaseService.getPerformanceMetrics(deploymentId)
console.log('Win Rate:', metrics.winRate)
console.log('Total P&L:', metrics.totalPnl)
```

## 🛠️ Maintenance

### Backup Strategy
- Supabase provides automatic backups
- Export critical data regularly for additional safety
- Monitor database size and performance

### Monitoring
- Check system logs for errors
- Monitor query performance
- Review RLS policy effectiveness

### Scaling Considerations
- Partition large tables by date if needed
- Add indexes for frequently queried columns
- Consider archiving old trade data

## 🐛 Troubleshooting

### Common Issues

**RLS Policies Blocking Access**
- Ensure user is authenticated
- Check if policies are correctly configured
- Verify user ownership of records

**Connection Issues**
- Verify Supabase URL and keys
- Check network connectivity
- Ensure project is active

**Query Performance**
- Add indexes for slow queries
- Consider query optimization
- Monitor database metrics

### Support

For issues with the database setup:
1. Check Supabase dashboard for errors
2. Review the logs in the platform
3. Verify all environment variables are set correctly

---

🔥 **Database powered by Supabase** - The open source Firebase alternative