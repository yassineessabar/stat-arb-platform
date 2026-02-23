#!/usr/bin/env node

// Emergency Stop Test Script
// This will close all open positions on Binance Futures Testnet

async function testEmergencyStop() {
  try {
    console.log('🚨 EMERGENCY STOP TEST');
    console.log('=' .repeat(50));
    console.log('\nThis will close ALL open positions at market price.');
    console.log('Testing the emergency stop functionality...\n');

    // First, check current positions
    console.log('📊 Checking current positions...');
    const positionsRes = await fetch('http://localhost:3000/api/binance/positions');
    const positionsData = await positionsRes.json();

    if (positionsData.positions && positionsData.positions.length > 0) {
      console.log(`\nFound ${positionsData.positions.length} open position(s):`);
      positionsData.positions.forEach(pos => {
        console.log(`  - ${pos.symbol}: ${pos.side} ${pos.size} units (P&L: $${pos.pnl?.toFixed(2) || '0.00'})`);
      });

      console.log('\n🔴 Executing EMERGENCY STOP...\n');

      // Execute emergency stop
      const response = await fetch('http://localhost:3000/api/binance/emergency-stop', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      const result = await response.json();

      if (result.success) {
        console.log('✅ EMERGENCY STOP SUCCESSFUL!\n');
        console.log(result.message);

        if (result.closedPositions?.length > 0) {
          console.log('\n📝 Closed Positions:');
          result.closedPositions.forEach(pos => {
            console.log(`  ✓ ${pos.symbol}: Closed ${pos.side} position of ${pos.amount} units`);
            console.log(`    Order ID: ${pos.orderId}`);
          });
        }

        if (result.cancelledOrders?.length > 0) {
          console.log(`\n🚫 Cancelled ${result.cancelledOrders.length} pending order(s)`);
        }

        // Verify all positions are closed
        console.log('\n⏳ Verifying positions are closed...');
        await new Promise(resolve => setTimeout(resolve, 2000));

        const verifyRes = await fetch('http://localhost:3000/api/binance/positions');
        const verifyData = await verifyRes.json();

        if (verifyData.positions?.length === 0) {
          console.log('✅ Confirmed: All positions closed successfully!');
        } else {
          console.log(`⚠️  Warning: ${verifyData.positions.length} position(s) still open`);
        }

      } else {
        console.error('❌ EMERGENCY STOP FAILED!');
        console.error('Error:', result.error || result.message);

        if (result.failedPositions?.length > 0) {
          console.log('\n❌ Failed to close:');
          result.failedPositions.forEach(pos => {
            console.log(`  - ${pos.symbol}: ${pos.error}`);
          });
        }
      }

      // Check final account status
      console.log('\n📊 Final Account Status:');
      const accountRes = await fetch('http://localhost:3000/api/binance/account');
      const accountData = await accountRes.json();

      console.log(`  Balance: $${accountData.totalBalance?.toFixed(2) || '0.00'}`);
      console.log(`  Open Positions: ${accountData.openPositions || 0}`);
      console.log(`  Total P&L: $${accountData.totalPnL?.toFixed(2) || '0.00'}`);

    } else {
      console.log('\n⚠️  No open positions to close.');
      console.log('💡 Use "node test-trade.js" to open a test position first.');
    }

  } catch (error) {
    console.error('\n❌ Error:', error.message);
    console.log('\n💡 Make sure:');
    console.log('   1. Next.js server is running (npm run dev)');
    console.log('   2. You have open positions to close');
  }
}

// Run the test
console.log('\n🚨 EMERGENCY STOP SYSTEM TEST\n');
testEmergencyStop();