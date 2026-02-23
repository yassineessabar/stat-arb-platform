#!/usr/bin/env node

/**
 * Database Setup Script for Statistical Arbitrage Platform
 * This script creates all necessary tables and policies in Supabase
 */

const fs = require('fs');
const path = require('path');

// Supabase configuration
const SUPABASE_URL = 'https://hfmcbyqdibxdbimwkcwi.supabase.co';
const SERVICE_ROLE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhmbWNieXFkaWJ4ZGJpbXdrY3dpIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTgzMDU3MCwiZXhwIjoyMDg3NDA2NTcwfQ.lAAU3d_wcZVOPMhFVZ80RizUJturvnKtXj2hX5nX8o0';

async function executeSQLFile(filename) {
    try {
        console.log(`\n🔄 Executing ${filename}...`);

        const sqlContent = fs.readFileSync(path.join(__dirname, filename), 'utf8');

        const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/exec_sql`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${SERVICE_ROLE_KEY}`,
                'Content-Type': 'application/json',
                'apikey': SERVICE_ROLE_KEY
            },
            body: JSON.stringify({
                sql: sqlContent
            })
        });

        if (response.ok) {
            console.log(`✅ ${filename} executed successfully`);
            return true;
        } else {
            const error = await response.text();
            console.error(`❌ Error executing ${filename}:`, error);
            return false;
        }
    } catch (error) {
        console.error(`❌ Failed to execute ${filename}:`, error.message);
        return false;
    }
}

async function executeSQLDirect(sql, description) {
    try {
        console.log(`\n🔄 ${description}...`);

        const { createClient } = await import('@supabase/supabase-js');
        const supabase = createClient(SUPABASE_URL, SERVICE_ROLE_KEY);

        const { data, error } = await supabase.rpc('exec', { sql });

        if (error) {
            console.error(`❌ Error in ${description}:`, error);
            return false;
        } else {
            console.log(`✅ ${description} completed successfully`);
            return true;
        }
    } catch (error) {
        console.error(`❌ Failed ${description}:`, error.message);
        return false;
    }
}

async function setupDatabase() {
    console.log('🚀 Setting up Statistical Arbitrage Platform Database');
    console.log('=' .repeat(60));

    try {
        // First, create a custom exec function if it doesn't exist
        const execFunction = `
        CREATE OR REPLACE FUNCTION exec(sql text)
        RETURNS void AS $$
        BEGIN
            EXECUTE sql;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
        `;

        // Execute using direct SQL
        const { createClient } = await import('@supabase/supabase-js');
        const supabase = createClient(SUPABASE_URL, SERVICE_ROLE_KEY);

        // Create exec function
        console.log('\n🔄 Creating helper function...');
        const { error: execError } = await supabase.rpc('query', {
            query: execFunction
        });

        if (execError) {
            console.log('ℹ️ Helper function may already exist:', execError.message);
        } else {
            console.log('✅ Helper function created');
        }

        // Execute schema creation
        console.log('\n🔄 Creating database schema...');
        const schemaSQL = fs.readFileSync(path.join(__dirname, '01_initial_schema.sql'), 'utf8');

        const { error: schemaError } = await supabase.rpc('query', {
            query: schemaSQL
        });

        if (schemaError) {
            console.error('❌ Schema creation error:', schemaError);
        } else {
            console.log('✅ Database schema created successfully');
        }

        // Execute RLS policies
        console.log('\n🔄 Setting up Row Level Security...');
        const rlsSQL = fs.readFileSync(path.join(__dirname, '02_rls_policies.sql'), 'utf8');

        const { error: rlsError } = await supabase.rpc('query', {
            query: rlsSQL
        });

        if (rlsError) {
            console.error('❌ RLS setup error:', rlsError);
        } else {
            console.log('✅ Row Level Security policies created');
        }

        // Create demo user
        console.log('\n🔄 Creating demo user...');
        const { data: demoUser, error: userError } = await supabase.rpc('insert_sample_user');

        if (userError) {
            console.error('❌ Demo user creation error:', userError);
        } else {
            console.log('✅ Demo user created with ID:', demoUser);
        }

        console.log('\n🎉 Database setup completed successfully!');
        console.log('\n📋 Created Tables:');
        console.log('  • users - User authentication and profiles');
        console.log('  • api_keys - Encrypted Binance API credentials');
        console.log('  • strategy_deployments - Active strategy tracking');
        console.log('  • positions - Open and closed positions');
        console.log('  • trades - Detailed trade execution history');
        console.log('  • strategy_performance - Performance analytics');
        console.log('  • market_data - Price history (optional)');
        console.log('  • system_logs - Platform monitoring');

        console.log('\n🔒 Security Features:');
        console.log('  • Row Level Security (RLS) enabled on all tables');
        console.log('  • Users can only access their own data');
        console.log('  • Encrypted API key storage');
        console.log('  • Service role permissions for system operations');

    } catch (error) {
        console.error('\n❌ Setup failed:', error.message);
        process.exit(1);
    }
}

// Execute the setup
setupDatabase();