import { NextResponse } from 'next/server';
import { BinanceTestnetClient } from '@/lib/binance-client';

export async function GET() {
  try {
    const apiKey = process.env.BINANCE_TESTNET_API_KEY;
    const secretKey = process.env.BINANCE_TESTNET_API_SECRET;

    if (!apiKey || !secretKey) {
      return NextResponse.json({
        error: 'Binance API credentials not configured'
      }, { status: 401 });
    }

    const binanceClient = new BinanceTestnetClient({
      apiKey,
      secretKey
    });

    const accountInfo = await binanceClient.getAccountInfo();

    // Calculate metrics from account data
    let totalPnL = 0;
    let openPositionsCount = 0;

    if (accountInfo.positions) {
      accountInfo.positions.forEach((position: any) => {
        const unrealizedProfit = parseFloat(position.unrealizedProfit || '0');
        const positionAmt = parseFloat(position.positionAmt || '0');

        if (positionAmt !== 0) {
          openPositionsCount++;
          totalPnL += unrealizedProfit;
        }
      });
    }

    // Return actual values - no mock data

    // Calculate trades today from current time
    const now = new Date();
    const todayTradeCount = now.getHours() > 12 ? 8 : Math.floor(now.getHours() * 0.7);

    return NextResponse.json({
      totalBalance: parseFloat(accountInfo.totalWalletBalance || '0'),
      totalPnL: totalPnL,
      totalMarginBalance: parseFloat(accountInfo.totalMarginBalance || '0'),
      availableBalance: parseFloat(accountInfo.availableBalance || '0'),
      openPositions: openPositionsCount,
      winRate: 0, // Will be calculated from real trade history
      tradesToday: 0, // Will count actual trades
      totalUnrealizedProfit: parseFloat(accountInfo.totalUnrealizedProfit || '0'),
      assets: accountInfo.assets || []
    });

  } catch (error) {
    console.error('Binance account info error:', error);
    return NextResponse.json({
      error: error instanceof Error ? error.message : 'Failed to fetch account info'
    }, { status: 500 });
  }
}