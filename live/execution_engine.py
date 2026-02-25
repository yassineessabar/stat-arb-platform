"""
Execution Engine
===============

Converts strategy target positions into actual market orders.
Handles order management, position reconciliation, and execution monitoring.

Key Features:
- Target position → order conversion
- Smart order routing (limit vs market)
- Position drift monitoring and correction
- Order retry logic and error handling
- Real-time execution metrics

This is the bridge between strategy signals and actual trading.
"""

import asyncio
import time
from typing import Dict, List, Optional, Tuple
import logging
import pandas as pd
import numpy as np

from live.binance_client import BinanceClient
from risk.position_risk import PositionRiskManager
from monitoring.metrics import ExecutionMetrics

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """
    Execution engine for converting target positions to market orders.
    """

    def __init__(self, client: BinanceClient, risk_manager: PositionRiskManager,
                 config: Dict):
        """
        Initialize execution engine.

        Args:
            client: Binance client for order execution
            risk_manager: Risk manager for position validation
            config: Configuration dictionary
        """
        self.client = client
        self.risk_manager = risk_manager
        self.config = config

        # Execution parameters
        self.max_slippage_bps = config['trading']['execution']['max_slippage_bps']
        self.order_timeout = config['trading']['execution']['order_timeout_seconds']
        self.retry_attempts = config['trading']['execution']['retry_attempts']
        self.min_order_value = config['trading']['execution']['min_order_value_usdt']

        # Position tracking
        self.current_positions = {}
        self.target_positions = {}
        self.pending_orders = {}

        # Metrics
        self.metrics = ExecutionMetrics()

        # Order management
        self.order_queue = asyncio.Queue()
        self.execution_lock = asyncio.Lock()

        logger.info("Execution engine initialized")

    async def set_target_positions(self, targets: Dict[str, float]) -> None:
        """
        Set new target positions.

        Args:
            targets: Dictionary mapping symbols to target position sizes (USD)
        """
        async with self.execution_lock:
            self.target_positions = targets.copy()

            logger.info(f"Updated target positions: {len(targets)} symbols")

            # Queue position updates
            await self._queue_position_updates()

    async def _queue_position_updates(self) -> None:
        """Queue orders to reach target positions."""

        # Get current positions
        await self._update_current_positions()

        # Calculate required trades
        required_trades = self._calculate_required_trades()

        # Validate trades with risk manager
        validated_trades = []
        for trade in required_trades:
            if await self.risk_manager.validate_trade(trade):
                validated_trades.append(trade)
            else:
                logger.warning(f"Trade blocked by risk manager: {trade}")

        # Queue validated trades
        for trade in validated_trades:
            await self.order_queue.put(trade)

        logger.info(f"Queued {len(validated_trades)} trades")

    async def _update_current_positions(self) -> None:
        """Update current position tracking."""
        try:
            positions = await self.client.get_position_risk()

            self.current_positions.clear()

            for pos in positions:
                symbol = pos['symbol']
                position_amt = float(pos['positionAmt'])

                if abs(position_amt) > 1e-8:  # Only track non-zero positions
                    # Convert to USD value (approximate)
                    mark_price = float(pos['markPrice'])
                    usd_value = position_amt * mark_price

                    self.current_positions[symbol] = {
                        'quantity': position_amt,
                        'usd_value': usd_value,
                        'entry_price': float(pos['entryPrice']),
                        'mark_price': mark_price,
                        'unrealized_pnl': float(pos['unRealizedPnL'])
                    }

            logger.debug(f"Updated positions: {len(self.current_positions)} active")

        except Exception as e:
            logger.error(f"Failed to update positions: {e}")

    def _calculate_required_trades(self) -> List[Dict]:
        """Calculate trades needed to reach target positions."""
        required_trades = []

        # Check all target positions
        for symbol, target_usd in self.target_positions.items():
            current_usd = self.current_positions.get(symbol, {}).get('usd_value', 0.0)

            position_diff = target_usd - current_usd

            # Only trade if difference is meaningful
            if abs(position_diff) > self.min_order_value:
                trade = {
                    'symbol': symbol,
                    'target_usd': target_usd,
                    'current_usd': current_usd,
                    'difference_usd': position_diff,
                    'side': 'BUY' if position_diff > 0 else 'SELL',
                    'priority': abs(position_diff)  # Larger differences first
                }
                required_trades.append(trade)

        # Check for positions to close (not in targets)
        for symbol, position in self.current_positions.items():
            if symbol not in self.target_positions:
                if abs(position['usd_value']) > self.min_order_value:
                    trade = {
                        'symbol': symbol,
                        'target_usd': 0.0,
                        'current_usd': position['usd_value'],
                        'difference_usd': -position['usd_value'],
                        'side': 'SELL' if position['usd_value'] > 0 else 'BUY',
                        'priority': abs(position['usd_value']),
                        'close_only': True
                    }
                    required_trades.append(trade)

        # Sort by priority (largest differences first)
        required_trades.sort(key=lambda x: x['priority'], reverse=True)

        return required_trades

    async def process_orders(self) -> None:
        """Process queued orders."""
        while True:
            try:
                # Get order from queue (blocks if empty)
                trade = await asyncio.wait_for(self.order_queue.get(), timeout=1.0)

                # Execute trade
                await self._execute_trade(trade)

                # Mark task done
                self.order_queue.task_done()

            except asyncio.TimeoutError:
                # No orders in queue, continue
                continue
            except Exception as e:
                logger.error(f"Error processing orders: {e}")
                await asyncio.sleep(1)

    async def _execute_trade(self, trade: Dict) -> Optional[Dict]:
        """
        Execute a single trade.

        Args:
            trade: Trade dictionary with execution details

        Returns:
            Order result or None if failed
        """
        symbol = trade['symbol']
        difference_usd = trade['difference_usd']
        side = trade['side']

        logger.info(f"Executing trade: {side} {abs(difference_usd):.2f} USD of {symbol}")

        try:
            # Get current price for quantity calculation
            ticker = await self.client.get_ticker_24hr(symbol)
            current_price = float(ticker['lastPrice'])

            # Validate price
            if current_price <= 0:
                logger.error(f"Invalid price received for {symbol}: {current_price}")
                return None

            # Calculate quantity
            quantity = abs(difference_usd) / current_price

            # Round to appropriate precision for testnet
            quantity = self._round_quantity(symbol, quantity)

            # Ensure minimum notional value of $100 for Futures
            notional_value = quantity * current_price
            if notional_value < 100:
                quantity = 100 / current_price
                quantity = self._round_quantity(symbol, quantity)
                logger.info(f"Adjusting {symbol} quantity to meet $100 minimum: {quantity} (notional: ${quantity * current_price:.2f})")

            if quantity == 0:
                logger.warning(f"Quantity rounded to zero for {symbol}")
                return None

            # Determine order type and price
            order_type, order_price = await self._get_order_params(symbol, side, current_price)

            # Place order with retries
            for attempt in range(self.retry_attempts):
                try:
                    order = await self.client.place_order(
                        symbol=symbol,
                        side=side,
                        order_type=order_type,
                        quantity=quantity,
                        price=order_price,
                        time_in_force="GTC"
                    )

                    # Track order
                    order_id = order['orderId']
                    order_status = order.get('status', 'NEW')

                    logger.info(f"✅ ORDER PLACED: {order_id} {side} {quantity} {symbol} - Status: {order_status}")

                    # If order is immediately filled (common on testnet), return success
                    if order_status in ['FILLED', 'PARTIALLY_FILLED']:
                        logger.info(f"🎯 ORDER IMMEDIATELY FILLED: {order_id}")
                        self.metrics.record_execution(symbol, side, quantity, current_price, order_price)
                        return order

                    # Otherwise, track for monitoring
                    self.pending_orders[order_id] = {
                        'symbol': symbol,
                        'side': side,
                        'quantity': quantity,
                        'price': order_price,
                        'timestamp': time.time()
                    }

                    # Monitor order execution (with shorter timeout for testnet)
                    try:
                        await self._monitor_order(order_id)
                    except Exception as e:
                        logger.warning(f"Order monitoring failed (order may be filled): {e}")

                    # Record metrics
                    self.metrics.record_execution(symbol, side, quantity, current_price, order_price)

                    logger.info(f"Order processed: {order_id} {side} {quantity} {symbol}")
                    return order

                except Exception as e:
                    logger.warning(f"Order attempt {attempt + 1} failed: {e}")
                    if attempt < self.retry_attempts - 1:
                        await asyncio.sleep(1)
                    else:
                        logger.error(f"All order attempts failed for {symbol}")
                        self.metrics.record_execution_failure(symbol, str(e))

        except Exception as e:
            logger.error(f"Trade execution failed for {symbol}: {e}")
            self.metrics.record_execution_failure(symbol, str(e))

        return None

    async def _get_order_params(self, symbol: str, side: str,
                               current_price: float) -> Tuple[str, Optional[float]]:
        """
        Determine order type and price based on market conditions.

        Args:
            symbol: Trading symbol
            side: Order side (BUY/SELL)
            current_price: Current market price

        Returns:
            Tuple of (order_type, order_price)
        """
        # For now, use market orders for simplicity and guaranteed execution
        # In production, could implement smart routing based on spread, urgency, etc.

        order_type = "MARKET"
        order_price = None  # Market orders don't need price

        # Could implement limit order logic here:
        # if spread_is_tight and not_urgent:
        #     order_type = "LIMIT"
        #     if side == "BUY":
        #         order_price = current_price * 0.999  # Slight discount
        #     else:
        #         order_price = current_price * 1.001  # Slight premium

        return order_type, order_price

    def _round_quantity(self, symbol: str, quantity: float) -> float:
        """Round quantity to appropriate precision for symbol."""
        # Use conservative precision for Binance Futures testnet
        if 'BTC' in symbol:
            return round(quantity, 3)  # BTC: 3 decimal places for futures
        elif 'ETH' in symbol:
            return round(quantity, 3)  # ETH: 3 decimal places for futures
        elif 'BNB' in symbol:
            return round(quantity, 2)  # BNB: 2 decimal places for futures
        else:
            return round(quantity, 2)  # Default: 2 decimal places

    async def _monitor_order(self, order_id: int) -> None:
        """Monitor order until filled or timeout."""
        order_info = self.pending_orders.get(order_id, {})
        symbol = order_info.get('symbol')
        start_time = time.time()

        while time.time() - start_time < self.order_timeout:
            try:
                status = await self.client.get_order_status(symbol, order_id)
                order_status = status['status']

                if order_status in ['FILLED', 'PARTIALLY_FILLED']:
                    # Order filled
                    if order_id in self.pending_orders:
                        del self.pending_orders[order_id]

                    logger.debug(f"Order {order_id} filled")
                    return

                elif order_status in ['CANCELED', 'REJECTED', 'EXPIRED']:
                    # Order failed
                    logger.warning(f"Order {order_id} failed: {order_status}")
                    if order_id in self.pending_orders:
                        del self.pending_orders[order_id]
                    return

                # Still pending, wait
                await asyncio.sleep(1)

            except Exception as e:
                logger.warning(f"Error monitoring order {order_id}: {e}")
                await asyncio.sleep(1)

        # Timeout reached
        logger.warning(f"Order {order_id} timeout, attempting to cancel")
        try:
            await self.client.cancel_order(symbol, order_id)
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")

        if order_id in self.pending_orders:
            del self.pending_orders[order_id]

    async def reconcile_positions(self) -> None:
        """Reconcile actual vs target positions."""
        await self._update_current_positions()

        position_drifts = []

        for symbol, target_usd in self.target_positions.items():
            current_usd = self.current_positions.get(symbol, {}).get('usd_value', 0.0)
            drift = abs(target_usd - current_usd)

            if drift > self.min_order_value:
                position_drifts.append({
                    'symbol': symbol,
                    'target': target_usd,
                    'current': current_usd,
                    'drift': drift,
                    'drift_pct': drift / max(abs(target_usd), 1)
                })

        if position_drifts:
            logger.warning(f"Position drifts detected: {len(position_drifts)} symbols")

            # Re-queue corrections for large drifts
            large_drifts = [d for d in position_drifts if d['drift_pct'] > 0.05]
            if large_drifts:
                await self._queue_position_updates()

    async def emergency_liquidate(self) -> None:
        """Emergency liquidation of all positions."""
        logger.critical("Emergency liquidation initiated")

        try:
            await self._update_current_positions()

            liquidation_orders = []
            for symbol, position in self.current_positions.items():
                quantity = abs(position['quantity'])
                side = 'SELL' if position['quantity'] > 0 else 'BUY'

                try:
                    order = await self.client.place_order(
                        symbol=symbol,
                        side=side,
                        order_type="MARKET",
                        quantity=quantity,
                        reduce_only=True
                    )
                    liquidation_orders.append(order)

                    logger.warning(f"Emergency liquidation: {symbol} {side} {quantity}")

                except Exception as e:
                    logger.error(f"Failed to liquidate {symbol}: {e}")

            # Clear all targets
            self.target_positions.clear()

            logger.critical(f"Emergency liquidation completed: {len(liquidation_orders)} orders")

        except Exception as e:
            logger.critical(f"Emergency liquidation failed: {e}")

    def get_execution_status(self) -> Dict:
        """Get current execution engine status."""
        return {
            'current_positions': len(self.current_positions),
            'target_positions': len(self.target_positions),
            'pending_orders': len(self.pending_orders),
            'queue_size': self.order_queue.qsize(),
            'metrics': self.metrics.get_summary()
        }

    async def shutdown(self) -> None:
        """Gracefully shutdown execution engine."""
        logger.info("Shutting down execution engine")

        # Wait for pending orders to complete
        await self.order_queue.join()

        # Cancel any remaining orders
        for order_id, order_info in self.pending_orders.items():
            try:
                await self.client.cancel_order(order_info['symbol'], order_id)
            except Exception:
                pass

        logger.info("Execution engine shutdown complete")