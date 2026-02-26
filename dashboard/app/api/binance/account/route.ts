import { NextResponse, NextRequest } from 'next/server';
import { BinanceTestnetClient } from '@/lib/binance-client';

export async function GET(request: NextRequest) {
  try {
    // Check query parameter for trading mode (paper = testnet, live = live API)
    const { searchParams } = new URL(request.url);
    const tradingMode = searchParams.get('mode') || 'paper';
    const isLive = tradingMode === 'live';

    const apiKey = isLive
      ? process.env.BINANCE_LIVE_API_KEY
      : process.env.BINANCE_TESTNET_API_KEY;
    const secretKey = isLive
      ? process.env.BINANCE_LIVE_API_SECRET
      : process.env.BINANCE_TESTNET_API_SECRET;

    if (!apiKey || !secretKey) {
      return NextResponse.json({
        error: `Binance ${isLive ? 'Live' : 'Testnet'} API credentials not configured`
      }, { status: 401 });
    }

    console.log(`🔗 Using Binance ${isLive ? 'Live' : 'Testnet'} API`);

    const binanceClient = new BinanceTestnetClient({
      apiKey,
      secretKey,
      isLive
    });

    const accountInfo = await binanceClient.getAccountInfo();

    // Debug: Log raw Binance response to understand the structure
    console.log('🔍 Raw Binance Account Info - Key fields:');
    console.log('  totalWalletBalance:', accountInfo.totalWalletBalance);
    console.log('  totalMarginBalance:', accountInfo.totalMarginBalance);
    console.log('  totalCrossWalletBalance:', accountInfo.totalCrossWalletBalance);
    console.log('  totalCrossUnPnl:', accountInfo.totalCrossUnPnl);
    console.log('  availableBalance:', accountInfo.availableBalance);
    console.log('  totalUnrealizedProfit:', accountInfo.totalUnrealizedProfit);

    // Calculate real metrics from Binance Futures account data
    // IMPORTANT: Sum up ALL assets to get correct wallet balance
    let totalWalletBalanceAllAssets = 0;
    let totalMarginBalanceAllAssets = 0;
    let totalUnrealizedProfitAllAssets = 0;

    if (accountInfo.assets) {
      accountInfo.assets.forEach((asset: any) => {
        const walletBalance = parseFloat(asset.walletBalance || '0');
        const marginBalance = parseFloat(asset.marginBalance || '0');
        const unrealizedProfit = parseFloat(asset.unrealizedProfit || '0');

        // Convert BTC to USDT equivalent (assuming BTC price ~68000)
        let usdtEquivalent = walletBalance;
        if (asset.asset === 'BTC' && walletBalance > 0) {
          usdtEquivalent = walletBalance * 68000; // Approximate BTC price
        }

        // Add USDT and USDC directly (both are 1:1 with USD)
        if (asset.asset === 'USDT' || asset.asset === 'USDC' || asset.asset === 'BTC') {
          totalWalletBalanceAllAssets += usdtEquivalent;
          totalMarginBalanceAllAssets += (asset.asset === 'BTC' ? marginBalance * 68000 : marginBalance);
          totalUnrealizedProfitAllAssets += unrealizedProfit;
        }
      });
    }

    console.log('💰 Calculated totals from all assets:');
    console.log('  Total Wallet Balance (All Assets):', totalWalletBalanceAllAssets);
    console.log('  Total Margin Balance (All Assets):', totalMarginBalanceAllAssets);

    let totalPnL = 0;
    let openPositionsCount = 0;
    let positionNotional = 0;

    if (accountInfo.positions) {
      accountInfo.positions.forEach((position: any) => {
        const unrealizedProfit = parseFloat(position.unrealizedProfit || '0');
        const positionAmt = parseFloat(position.positionAmt || '0');
        const markPrice = parseFloat(position.markPrice || '0');

        if (positionAmt !== 0) {
          openPositionsCount++;
          totalPnL += unrealizedProfit;
          positionNotional += Math.abs(positionAmt * markPrice);
        }
      });
    }

    // Get recent trades to calculate win rate and trades today
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    // For now, we'll set these to 0 until we implement trade history tracking
    const tradesToday = 0;
    const winRate = 0;

    return NextResponse.json({
      // Real Binance Futures account data - Using calculated totals from ALL assets
      marginBalance: totalMarginBalanceAllAssets,
      totalPnL: totalUnrealizedProfitAllAssets,
      availableBalance: parseFloat(accountInfo.availableBalance || '0'),
      totalUnrealizedProfit: totalUnrealizedProfitAllAssets,
      totalWalletBalance: totalWalletBalanceAllAssets,
      totalInitialMargin: parseFloat(accountInfo.totalInitialMargin || '0'),
      totalMaintMargin: parseFloat(accountInfo.totalMaintMargin || '0'),

      // Calculated metrics
      openPositions: openPositionsCount,
      positionNotional: positionNotional,
      winRate: winRate,
      tradesToday: tradesToday,

      // Raw data for detailed view
      positions: accountInfo.positions || [],
      assets: accountInfo.assets || []
    });

  } catch (error) {
    console.error('Binance account info error:', error);
    return NextResponse.json({
      error: error instanceof Error ? error.message : 'Failed to fetch account info'
    }, { status: 500 });
  }
}