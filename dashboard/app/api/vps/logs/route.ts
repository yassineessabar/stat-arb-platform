import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const deploymentId = searchParams.get('deploymentId');
    const limit = parseInt(searchParams.get('limit') || '50');

    if (!deploymentId) {
      return NextResponse.json({ error: 'deploymentId parameter required' }, { status: 400 });
    }

    // Get logs from database
    const { data: logs, error } = await supabase
      .from('system_logs')
      .select('*')
      .eq('deployment_id', deploymentId)
      .order('timestamp', { ascending: false })
      .limit(limit);

    if (error) {
      console.error('Supabase error:', error);
      return NextResponse.json({ error: 'Database error' }, { status: 500 });
    }

    // Format logs for display
    const formattedLogs = logs?.map(log => ({
      id: log.id,
      timestamp: log.timestamp,
      level: log.level,
      message: log.message,
      eventType: log.event_type,
      details: log.details
    })) || [];

    return NextResponse.json({
      success: true,
      deploymentId,
      logs: formattedLogs,
      count: formattedLogs.length,
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    console.error('Error fetching VPS logs:', error);
    return NextResponse.json({
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
}

// Get all active VPS deployments
export async function POST(request: NextRequest) {
  try {
    // Get active deployments
    const { data: deployments, error } = await supabase
      .from('strategy_deployments')
      .select('*')
      .eq('status', 'active')
      .order('created_at', { ascending: false });

    if (error) {
      console.error('Supabase error:', error);
      return NextResponse.json({ error: 'Database error' }, { status: 500 });
    }

    // Get recent logs for each deployment
    const deploymentsWithLogs = await Promise.all(
      (deployments || []).map(async (deployment) => {
        const { data: recentLogs } = await supabase
          .from('system_logs')
          .select('timestamp, level, message')
          .eq('deployment_id', deployment.deployment_id)
          .order('timestamp', { ascending: false })
          .limit(5);

        return {
          ...deployment,
          recentLogs: recentLogs || [],
          lastActivity: recentLogs?.[0]?.timestamp || deployment.updated_at
        };
      })
    );

    return NextResponse.json({
      success: true,
      deployments: deploymentsWithLogs,
      count: deploymentsWithLogs.length,
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    console.error('Error fetching VPS deployments:', error);
    return NextResponse.json({
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
}