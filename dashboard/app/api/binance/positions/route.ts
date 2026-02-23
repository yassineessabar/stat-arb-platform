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

    // Filter for open positions (non-zero position amount)
    const openPositions = [];

    if (accountInfo.positions) {
      for (const position of accountInfo.positions) {
        const positionAmt = parseFloat(position.positionAmt || '0');

        if (positionAmt !== 0) {
          const unrealizedProfit = parseFloat(position.unrealizedProfit || '0');
          const entryPrice = parseFloat(position.entryPrice || '0');
          const markPrice = parseFloat(position.markPrice || '0');
          const notional = parseFloat(position.notional || '0');

          // Calculate P&L percentage
          let pnlPercentage = 0;
          if (entryPrice > 0) {
            if (positionAmt > 0) {
              // Long position
              pnlPercentage = ((markPrice - entryPrice) / entryPrice) * 100;
            } else {
              // Short position
              pnlPercentage = ((entryPrice - markPrice) / entryPrice) * 100;
            }
          }

          openPositions.push({
            // Basic position info
            symbol: position.symbol,
            side: positionAmt > 0 ? 'LONG' : 'SHORT',
            orderType: 'MARKET', // Most positions from market orders

            // Quantities and amounts
            size: Math.abs(positionAmt),
            notional: Math.abs(notional),

            // Prices
            entryPrice: entryPrice,
            markPrice: markPrice,
            avgPrice: entryPrice, // Entry price is the average fill price

            // P&L
            pnl: unrealizedProfit,
            pnlPercentage: pnlPercentage,

            // Additional details
            margin: parseFloat(position.isolatedMargin || position.initialMargin || '0'),
            leverage: parseInt(position.leverage || '1'),
            updateTime: position.updateTime || Date.now()
          });
        }
      }
    }

    // Return actual positions (empty if none)

    return NextResponse.json({
      positions: openPositions
    });

  } catch (error) {
    console.error('Binance positions fetch error:', error);
    return NextResponse.json({
      error: error instanceof Error ? error.message : 'Failed to fetch positions'
    }, { status: 500 });
  }
}