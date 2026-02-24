import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const runId = searchParams.get('runId');
    const jobName = searchParams.get('jobName') || 'execute-strategy';

    if (!runId) {
      return NextResponse.json({ error: 'runId parameter required' }, { status: 400 });
    }

    // GitHub API endpoint for workflow logs
    const owner = 'yassineessabar';
    const repo = 'stat-arb-platform';

    // First, get the job ID
    const jobsResponse = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/actions/runs/${runId}/jobs`,
      {
        headers: {
          'Authorization': `token ${process.env.GITHUB_TOKEN}`,
          'Accept': 'application/vnd.github.v3+json',
          'User-Agent': 'StatArb-Platform'
        }
      }
    );

    if (!jobsResponse.ok) {
      return NextResponse.json({
        error: 'Failed to fetch jobs',
        status: jobsResponse.status,
        message: 'Make sure GITHUB_TOKEN is configured in environment variables'
      }, { status: 500 });
    }

    const jobsData = await jobsResponse.json();
    const targetJob = jobsData.jobs.find((job: any) =>
      job.name.toLowerCase().includes(jobName.toLowerCase())
    );

    if (!targetJob) {
      return NextResponse.json({
        error: `Job '${jobName}' not found`,
        availableJobs: jobsData.jobs.map((job: any) => job.name)
      }, { status: 404 });
    }

    // Get the logs for the specific job
    const logsResponse = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/actions/jobs/${targetJob.id}/logs`,
      {
        headers: {
          'Authorization': `token ${process.env.GITHUB_TOKEN}`,
          'Accept': 'application/vnd.github.v3+json',
          'User-Agent': 'StatArb-Platform'
        }
      }
    );

    if (!logsResponse.ok) {
      return NextResponse.json({
        error: 'Failed to fetch logs',
        status: logsResponse.status
      }, { status: 500 });
    }

    const logs = await logsResponse.text();

    // Extract relevant signal analysis logs
    const logLines = logs.split('\n');
    const signalLogs = logLines.filter(line =>
      line.includes('Signal Analysis') ||
      line.includes('Current z-score') ||
      line.includes('Z-score threshold') ||
      line.includes('NO ENTRY') ||
      line.includes('ENTRY SIGNAL') ||
      line.includes('Checking') ||
      line.includes('EXIT SIGNAL') ||
      line.includes('HOLD POSITION') ||
      line.includes('STOP LOSS') ||
      line.includes('🚀') ||
      line.includes('📊') ||
      line.includes('🎯') ||
      line.includes('⚠️') ||
      line.includes('✅') ||
      line.includes('❌') ||
      line.includes('🚪') ||
      line.includes('🛑') ||
      line.includes('➤')
    );

    return NextResponse.json({
      success: true,
      runId,
      jobId: targetJob.id,
      jobName: targetJob.name,
      status: targetJob.status,
      conclusion: targetJob.conclusion,
      signalLogs: signalLogs.slice(-50), // Last 50 signal-related logs
      fullLogs: logs,
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    console.error('Error fetching GitHub workflow logs:', error);
    return NextResponse.json({
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
}

// Get latest workflow run logs
export async function POST(request: NextRequest) {
  try {
    const owner = 'yassineessabar';
    const repo = 'stat-arb-platform';

    // Get the latest workflow runs
    const runsResponse = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/actions/runs?per_page=5`,
      {
        headers: {
          'Authorization': `token ${process.env.GITHUB_TOKEN}`,
          'Accept': 'application/vnd.github.v3+json',
          'User-Agent': 'StatArb-Platform'
        }
      }
    );

    if (!runsResponse.ok) {
      return NextResponse.json({
        error: 'Failed to fetch workflow runs',
        status: runsResponse.status
      }, { status: 500 });
    }

    const runsData = await runsResponse.json();
    const latestRun = runsData.workflow_runs[0];

    if (!latestRun) {
      return NextResponse.json({
        error: 'No workflow runs found'
      }, { status: 404 });
    }

    return NextResponse.json({
      success: true,
      latestRun: {
        id: latestRun.id,
        status: latestRun.status,
        conclusion: latestRun.conclusion,
        created_at: latestRun.created_at,
        updated_at: latestRun.updated_at,
        html_url: latestRun.html_url,
        workflow_name: latestRun.name
      },
      allRuns: runsData.workflow_runs.slice(0, 5).map((run: any) => ({
        id: run.id,
        status: run.status,
        conclusion: run.conclusion,
        created_at: run.created_at,
        html_url: run.html_url
      }))
    });

  } catch (error) {
    console.error('Error fetching latest workflow runs:', error);
    return NextResponse.json({
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
}