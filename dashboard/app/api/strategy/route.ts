import { NextRequest, NextResponse } from 'next/server';

export async function GET(req: NextRequest) {
  try {
    // In production, this would connect to Python backend
    // For now, return mock data matching your backtest results
    const strategyData = {
      status: 'active',
      pairs: [
        { pair: 'XLM-XRP', tier: 1, score: 95.2, adf_pvalue: 0.0001 },
        { pair: 'ETH-SOL', tier: 1, score: 86.3, adf_pvalue: 0.0012 },
        { pair: 'BCH-TRX', tier: 1, score: 85.9, adf_pvalue: 0.0015 }
      ],
      performance: {
        annual_return: 0.614,
        sharpe_ratio: 3.12,
        max_drawdown: -0.114,
        total_return: 0.931,
        hit_rate: 0.114
      },
      positions: []
    };

    return NextResponse.json(strategyData);

  } catch (error) {
    console.error('Strategy API error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch strategy data' },
      { status: 500 }
    );
  }
}

export async function POST(req: NextRequest) {
  try {
    const { action } = await req.json();

    switch (action) {
      case 'start':
        // Start trading
        return NextResponse.json({ success: true, message: 'Trading started' });

      case 'stop':
        // Stop trading
        return NextResponse.json({ success: true, message: 'Trading stopped' });

      case 'pause':
        // Pause trading
        return NextResponse.json({ success: true, message: 'Trading paused' });

      default:
        return NextResponse.json(
          { error: 'Invalid action' },
          { status: 400 }
        );
    }

  } catch (error) {
    console.error('Strategy control error:', error);
    return NextResponse.json(
      { error: 'Failed to control strategy' },
      { status: 500 }
    );
  }
}