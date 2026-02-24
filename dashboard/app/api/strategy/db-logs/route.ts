import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

// Initialize Supabase client
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;
const supabase = createClient(supabaseUrl, supabaseServiceKey);

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const processId = searchParams.get('processId');
    const limit = parseInt(searchParams.get('limit') || '50');

    if (!processId) {
      return NextResponse.json({
        success: false,
        error: 'Process ID is required'
      }, { status: 400 });
    }

    // First, get the deployment ID for this process
    const { data: deployment, error: deploymentError } = await supabase
      .from('strategy_deployments')
      .select('id')
      .eq('process_id', processId)
      .single();

    if (deploymentError || !deployment) {
      return NextResponse.json({
        success: false,
        error: 'Deployment not found for this process ID'
      }, { status: 404 });
    }

    // Get system logs for this deployment
    const { data: logs, error: logsError } = await supabase
      .from('system_logs')
      .select('*')
      .eq('deployment_id', deployment.id)
      .order('created_at', { ascending: false })
      .limit(limit);

    if (logsError) {
      return NextResponse.json({
        success: false,
        error: `Database error: ${logsError.message}`
      }, { status: 500 });
    }

    // Format logs for frontend consumption
    const formattedLogs = (logs || []).map(log => ({
      timestamp: new Date(log.created_at),
      level: log.log_level,
      type: log.log_type,
      message: log.message,
      raw: log.message
    })).reverse(); // Reverse to show oldest first

    return NextResponse.json({
      success: true,
      logs: formattedLogs,
      totalLogs: logs?.length || 0,
      processId,
      deploymentId: deployment.id
    });

  } catch (error) {
    console.error('Error fetching database logs:', error);
    return NextResponse.json({
      success: false,
      error: error instanceof Error ? error.message : 'Failed to fetch database logs'
    }, { status: 500 });
  }
}