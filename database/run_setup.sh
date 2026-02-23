#!/bin/bash

# Statistical Arbitrage Platform Database Setup
# This script executes the SQL files to set up the database schema

echo "🚀 Setting up Statistical Arbitrage Platform Database"
echo "============================================================"

# Supabase connection details
DB_URL="postgresql://postgres.hfmcbyqdibxdbimwkcwi:$(echo 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhmbWNieXFkaWJ4ZGJpbXdrY3dpIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTgzMDU3MCwiZXhwIjoyMDg3NDA2NTcwfQ.lAAU3d_wcZVOPMhFVZ80RizUJturvnKtXj2hX5nX8o0')@aws-0-us-west-1.pooler.supabase.com:6543/postgres"

echo ""
echo "🔄 Step 1: Creating database schema..."
psql "$DB_URL" -f 01_initial_schema.sql

if [ $? -eq 0 ]; then
    echo "✅ Database schema created successfully"
else
    echo "❌ Failed to create database schema"
    exit 1
fi

echo ""
echo "🔄 Step 2: Setting up Row Level Security..."
psql "$DB_URL" -f 02_rls_policies.sql

if [ $? -eq 0 ]; then
    echo "✅ RLS policies created successfully"
else
    echo "❌ Failed to create RLS policies"
    exit 1
fi

echo ""
echo "🔄 Step 3: Creating demo data..."
psql "$DB_URL" -c "SELECT insert_sample_user();"

if [ $? -eq 0 ]; then
    echo "✅ Demo user created successfully"
else
    echo "❌ Failed to create demo user"
fi

echo ""
echo "🎉 Database setup completed successfully!"
echo ""
echo "📋 Created Tables:"
echo "  • users - User authentication and profiles"
echo "  • api_keys - Encrypted Binance API credentials"
echo "  • strategy_deployments - Active strategy tracking"
echo "  • positions - Open and closed positions"
echo "  • trades - Detailed trade execution history"
echo "  • strategy_performance - Performance analytics"
echo "  • market_data - Price history (optional)"
echo "  • system_logs - Platform monitoring"
echo ""
echo "🔒 Security Features:"
echo "  • Row Level Security (RLS) enabled on all tables"
echo "  • Users can only access their own data"
echo "  • Encrypted API key storage"
echo "  • Service role permissions for system operations"
echo ""
echo "🔗 Next Steps:"
echo "  1. Update your .env.local with the Supabase credentials"
echo "  2. Install Supabase client: npm install @supabase/supabase-js"
echo "  3. Test the database connection in your application"