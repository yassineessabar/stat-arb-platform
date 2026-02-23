import { NextResponse } from 'next/server';
import { BinanceTestnetClient } from '@/lib/binance-client';

export async function POST() {
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

    console.log('EMERGENCY STOP INITIATED - Closing all positions...');

    // Get account info to find all open positions
    const accountInfo = await binanceClient.getAccountInfo();
    const closedPositions = [];
    const failedPositions = [];

    if (accountInfo.positions) {
      for (const position of accountInfo.positions) {
        const positionAmt = parseFloat(position.positionAmt || '0');

        if (positionAmt !== 0) {
          try {
            // Place market order in opposite direction to close position
            const closeOrder = await binanceClient.placeOrder({
              symbol: position.symbol,
              side: positionAmt > 0 ? 'SELL' : 'BUY',
              type: 'MARKET',
              quantity: Math.abs(positionAmt)
            });

            closedPositions.push({
              symbol: position.symbol,
              amount: Math.abs(positionAmt),
              side: positionAmt > 0 ? 'LONG' : 'SHORT',
              orderId: closeOrder.orderId,
              status: closeOrder.status
            });

            console.log(`Closed position: ${position.symbol} (${Math.abs(positionAmt)} units)`);
          } catch (error) {
            console.error(`Failed to close ${position.symbol}:`, error);
            failedPositions.push({
              symbol: position.symbol,
              amount: Math.abs(positionAmt),
              error: error instanceof Error ? error.message : 'Unknown error'
            });
          }
        }
      }
    }

    // Cancel all open orders
    let cancelledOrders = [];
    try {
      // Get all open orders for all symbols
      const openOrders = await binanceClient.getOpenOrders();

      for (const order of openOrders) {
        try {
          await binanceClient.makeRequest('/fapi/v1/order', {
            symbol: order.symbol,
            orderId: order.orderId
          }, 'DELETE');

          cancelledOrders.push({
            symbol: order.symbol,
            orderId: order.orderId
          });
        } catch (error) {
          console.error(`Failed to cancel order ${order.orderId}:`, error);
        }
      }
    } catch (error) {
      console.error('Error cancelling orders:', error);
    }

    const totalClosed = closedPositions.length;
    const totalFailed = failedPositions.length;
    const totalCancelled = cancelledOrders.length;

    return NextResponse.json({
      success: totalFailed === 0,
      message: `Emergency stop executed: ${totalClosed} positions closed, ${totalFailed} failed, ${totalCancelled} orders cancelled`,
      closedPositions,
      failedPositions,
      cancelledOrders,
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    console.error('Emergency stop error:', error);
    return NextResponse.json({
      success: false,
      error: error instanceof Error ? error.message : 'Emergency stop failed'
    }, { status: 500 });
  }
}