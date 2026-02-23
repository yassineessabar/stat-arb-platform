#!/usr/bin/env node

// Test script to place a small trade on Binance Futures Testnet
// This will open a small BTCUSDT position to test the system

async function placeTestTrade() {
  try {
    console.log('🚀 Placing test trade on Binance Futures Testnet...\n');

    // Place a BTC futures order (minimum $100 notional)
    // BTC price ~$100,000, so 0.002 BTC = ~$200 notional
    const orderData = {
      symbol: 'BTCUSDT',
      side: 'BUY',      // Going LONG
      type: 'MARKET',   // Market order for immediate execution
      quantity: 0.002   // 0.002 BTC (~$200 notional at $100k BTC)
    };

    console.log('Order Details:');
    console.log(`  Symbol: ${orderData.symbol}`);
    console.log(`  Side: ${orderData.side} (Going LONG)`);
    console.log(`  Type: ${orderData.type}`);
    console.log(`  Quantity: ${orderData.quantity} BTC\n`);

    // Send order to API
    const response = await fetch('http://localhost:3000/api/binance/order', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(orderData)
    });

    const result = await response.json();

    if (response.ok) {
      console.log('✅ Trade placed successfully!');
      console.log('\nOrder Response:');
      console.log(JSON.stringify(result.order, null, 2));

      console.log('\n📊 Check your execution page to see:');
      console.log('   - Updated P&L');
      console.log('   - Open position for BTCUSDT');
      console.log('   - Trade in recent trades list');
      console.log('\n🔗 http://localhost:3000/execution');
    } else {
      console.error('❌ Failed to place trade:', result.error);

      if (result.error.includes('MIN_NOTIONAL')) {
        console.log('\n💡 Try increasing the quantity. Minimum notional value not met.');
      }
    }

    // Wait 2 seconds then fetch account info to show position
    console.log('\n⏳ Fetching updated account info...');
    await new Promise(resolve => setTimeout(resolve, 2000));

    const accountResponse = await fetch('http://localhost:3000/api/binance/account');
    const accountData = await accountResponse.json();

    console.log('\n📈 Account Status:');
    console.log(`  Total P&L: $${accountData.totalPnL?.toFixed(2) || '0.00'}`);
    console.log(`  Open Positions: ${accountData.openPositions || 0}`);
    console.log(`  Balance: $${accountData.totalBalance?.toFixed(2) || '0.00'}`);

  } catch (error) {
    console.error('❌ Error:', error.message);
    console.log('\n💡 Make sure the Next.js server is running on port 3000');
  }
}

// Run the test
placeTestTrade();