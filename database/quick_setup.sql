-- Quick setup script that can be executed in Supabase SQL Editor
-- Copy and paste this entire script into your Supabase SQL Editor and run it

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table for authentication and user management
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    username TEXT UNIQUE,
    full_name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- Strategy Deployments table
CREATE TABLE IF NOT EXISTS strategy_deployments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    process_id TEXT UNIQUE NOT NULL,
    strategy_name TEXT NOT NULL,
    trading_mode TEXT NOT NULL CHECK (trading_mode IN ('paper', 'live')),
    status TEXT DEFAULT 'running' CHECK (status IN ('running', 'stopped', 'paused', 'error')),

    -- Strategy Parameters
    symbol_1 TEXT NOT NULL,
    symbol_2 TEXT NOT NULL,
    entry_z_score DECIMAL(5,2) DEFAULT 2.0,
    exit_z_score DECIMAL(5,2) DEFAULT 0.5,
    position_size DECIMAL(15,2) DEFAULT 1000,
    max_positions INTEGER DEFAULT 3,

    -- Execution Details
    deployed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    stopped_at TIMESTAMP WITH TIME ZONE,
    total_trades INTEGER DEFAULT 0,
    total_pnl DECIMAL(15,2) DEFAULT 0
);

-- Positions table for tracking trades
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deployment_id UUID REFERENCES strategy_deployments(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,

    -- Position Details
    position_id TEXT NOT NULL,
    symbol_1 TEXT NOT NULL,
    symbol_2 TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'closed')),

    -- Entry Information
    entry_price_1 DECIMAL(15,6) NOT NULL,
    entry_price_2 DECIMAL(15,6) NOT NULL,
    entry_z_score DECIMAL(8,4) NOT NULL,
    position_size DECIMAL(15,2) NOT NULL,
    entry_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Exit Information
    exit_price_1 DECIMAL(15,6),
    exit_price_2 DECIMAL(15,6),
    exit_z_score DECIMAL(8,4),
    exit_time TIMESTAMP WITH TIME ZONE,
    exit_reason TEXT,

    -- P&L Tracking
    realized_pnl DECIMAL(15,2) DEFAULT 0,
    net_pnl DECIMAL(15,2) DEFAULT 0,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(deployment_id, position_id)
);

-- Trades table for detailed execution history
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deployment_id UUID REFERENCES strategy_deployments(id) ON DELETE CASCADE,
    position_id UUID REFERENCES positions(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,

    -- Trade Details
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity DECIMAL(15,6) NOT NULL,
    price DECIMAL(15,6) NOT NULL,
    commission DECIMAL(15,6) DEFAULT 0,

    -- Timing
    execution_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    realized_pnl DECIMAL(15,2) DEFAULT 0,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- System Logs table
CREATE TABLE IF NOT EXISTS system_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deployment_id UUID REFERENCES strategy_deployments(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,

    log_level TEXT DEFAULT 'info',
    log_type TEXT DEFAULT 'strategy',
    message TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_strategy_deployments_user_id ON strategy_deployments(user_id);
CREATE INDEX IF NOT EXISTS idx_positions_deployment_id ON positions(deployment_id);
CREATE INDEX IF NOT EXISTS idx_trades_deployment_id ON trades(deployment_id);

-- Enable RLS on tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategy_deployments ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_logs ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
CREATE POLICY "Users can manage own data" ON users FOR ALL USING (auth.uid() = id);
CREATE POLICY "Users can manage own deployments" ON strategy_deployments FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users can view own positions" ON positions FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users can view own trades" ON trades FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users can view own logs" ON system_logs FOR ALL USING (auth.uid() = user_id);

-- Insert sample user for testing
INSERT INTO users (email, username, full_name)
VALUES ('demo@statarib.com', 'demo_user', 'Demo User')
ON CONFLICT (email) DO NOTHING;

-- Success message
SELECT 'Database setup completed successfully! All tables and policies created.' as status;