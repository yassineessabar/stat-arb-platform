"""
Execution Engine Tests
=====================

Tests for order execution, position management, and risk controls.
Validates proper conversion from signals to market orders.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from live.execution_engine import ExecutionEngine
from live.binance_client import BinanceClient, PaperTradingSimulator
from risk.position_risk import PositionRiskManager


@pytest.fixture
def mock_config():
    """Mock configuration for execution engine."""
    return {
        'trading': {
            'execution': {
                'max_slippage_bps': 10,
                'order_timeout_seconds': 30,
                'retry_attempts': 3,
                'min_order_value_usdt': 5
            }
        }
    }


@pytest.fixture
def mock_risk_manager():
    """Mock risk manager."""
    risk_manager = Mock(spec=PositionRiskManager)
    risk_manager.validate_trade = AsyncMock(return_value=True)
    return risk_manager


@pytest.fixture
def paper_binance_client():
    """Binance client in paper trading mode."""
    return BinanceClient(paper_trading=True)


class TestExecutionEngine:
    """Test execution engine functionality."""

    @pytest.mark.asyncio
    async def test_execution_engine_init(self, paper_binance_client, mock_risk_manager, mock_config):
        """Test execution engine initialization."""
        engine = ExecutionEngine(paper_binance_client, mock_risk_manager, mock_config)

        assert engine.client is paper_binance_client
        assert engine.risk_manager is mock_risk_manager
        assert engine.max_slippage_bps == 10
        assert engine.order_timeout == 30
        assert engine.retry_attempts == 3

    @pytest.mark.asyncio
    async def test_set_target_positions(self, paper_binance_client, mock_risk_manager, mock_config):
        """Test setting target positions."""
        engine = ExecutionEngine(paper_binance_client, mock_risk_manager, mock_config)

        targets = {
            'BTCUSDT': 1000.0,
            'ETHUSDT': -500.0
        }

        await engine.set_target_positions(targets)

        assert engine.target_positions == targets

    @pytest.mark.asyncio
    async def test_position_calculation(self, paper_binance_client, mock_risk_manager, mock_config):
        """Test calculation of required trades."""
        engine = ExecutionEngine(paper_binance_client, mock_risk_manager, mock_config)

        # Set current positions
        engine.current_positions = {
            'BTCUSDT': {'usd_value': 500.0}
        }

        # Set targets
        engine.target_positions = {
            'BTCUSDT': 1000.0,
            'ETHUSDT': -300.0
        }

        # Calculate required trades
        trades = engine._calculate_required_trades()

        assert len(trades) == 2  # BTC and ETH

        # Find BTC trade
        btc_trade = next(t for t in trades if t['symbol'] == 'BTCUSDT')
        assert btc_trade['difference_usd'] == 500.0  # 1000 - 500
        assert btc_trade['side'] == 'BUY'

        # Find ETH trade
        eth_trade = next(t for t in trades if t['symbol'] == 'ETHUSDT')
        assert eth_trade['difference_usd'] == -300.0
        assert eth_trade['side'] == 'SELL'

    @pytest.mark.asyncio
    async def test_order_execution(self, paper_binance_client, mock_risk_manager, mock_config):
        """Test order execution flow."""
        engine = ExecutionEngine(paper_binance_client, mock_risk_manager, mock_config)

        trade = {
            'symbol': 'BTCUSDT',
            'difference_usd': 1000.0,
            'side': 'BUY'
        }

        async with paper_binance_client:
            # Mock market price
            with patch.object(paper_binance_client, 'get_ticker_24hr',
                             return_value={'lastPrice': '50000.0'}):
                result = await engine._execute_trade(trade)

                assert result is not None
                assert result['symbol'] == 'BTCUSDT'
                assert result['side'] == 'BUY'

    @pytest.mark.asyncio
    async def test_risk_validation_blocking(self, paper_binance_client, mock_risk_manager, mock_config):
        """Test that risk manager can block trades."""
        # Configure risk manager to block trades
        mock_risk_manager.validate_trade = AsyncMock(return_value=False)

        engine = ExecutionEngine(paper_binance_client, mock_risk_manager, mock_config)

        targets = {'BTCUSDT': 10000.0}  # Large position

        await engine.set_target_positions(targets)

        # No orders should be queued due to risk block
        assert engine.order_queue.empty()

    @pytest.mark.asyncio
    async def test_emergency_liquidation(self, paper_binance_client, mock_risk_manager, mock_config):
        """Test emergency liquidation functionality."""
        engine = ExecutionEngine(paper_binance_client, mock_risk_manager, mock_config)

        # Set up positions to liquidate
        engine.current_positions = {
            'BTCUSDT': {'quantity': 0.1, 'usd_value': 5000.0},
            'ETHUSDT': {'quantity': -2.0, 'usd_value': -6000.0}
        }

        async with paper_binance_client:
            await engine.emergency_liquidate()

            # All target positions should be cleared
            assert len(engine.target_positions) == 0


class TestPaperTradingSimulator:
    """Test paper trading simulation."""

    def test_paper_simulator_init(self):
        """Test paper trading simulator initialization."""
        simulator = PaperTradingSimulator(100000)

        assert simulator.balance == 100000
        assert len(simulator.positions) == 0
        assert simulator.order_id_counter == 1

    def test_paper_account_info(self):
        """Test paper account info."""
        simulator = PaperTradingSimulator(50000)

        account_info = simulator.get_account_info()

        assert account_info['totalWalletBalance'] == '50000'
        assert len(account_info['assets']) == 1

    @pytest.mark.asyncio
    async def test_paper_order_execution(self):
        """Test paper order placement and execution."""
        simulator = PaperTradingSimulator(100000)

        order = await simulator.place_order(
            symbol='BTCUSDT',
            side='BUY',
            order_type='MARKET',
            quantity=0.1,
            price=None
        )

        assert order['status'] == 'FILLED'
        assert order['symbol'] == 'BTCUSDT'
        assert order['side'] == 'BUY'
        assert float(order['executedQty']) == 0.1

    def test_paper_position_update(self):
        """Test paper position tracking."""
        simulator = PaperTradingSimulator(100000)

        # Simulate position update
        simulator._update_position('BTCUSDT', 'BUY', 0.1, 50000)

        positions = simulator.get_position_risk('BTCUSDT')

        assert len(positions) == 1
        assert float(positions[0]['positionAmt']) == 0.1


class TestBinanceClient:
    """Test Binance client functionality."""

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client initialization in paper mode."""
        client = BinanceClient(paper_trading=True)

        assert client.paper_trading is True
        assert hasattr(client, 'paper_state')

    @pytest.mark.asyncio
    async def test_kline_data_conversion(self):
        """Test conversion of kline data to DataFrame."""
        client = BinanceClient()

        # Sample kline data
        sample_klines = [
            [1640995200000, '46000.0', '47000.0', '45500.0', '46500.0', '100.5',
             1641081599999, '4665000.0', 1500, '50.2', '2332500.0', '0'],
        ]

        df = client.klines_to_dataframe(sample_klines, 'BTCUSDT')

        assert 'open' in df.columns
        assert 'high' in df.columns
        assert 'low' in df.columns
        assert 'close' in df.columns
        assert 'volume' in df.columns
        assert len(df) == 1
        assert df.iloc[0]['close'] == 46500.0


class TestOrderManagement:
    """Test order management functionality."""

    @pytest.mark.asyncio
    async def test_order_queue_processing(self, paper_binance_client, mock_risk_manager, mock_config):
        """Test order queue processing."""
        engine = ExecutionEngine(paper_binance_client, mock_risk_manager, mock_config)

        # Add a trade to the queue
        trade = {
            'symbol': 'BTCUSDT',
            'difference_usd': 1000.0,
            'side': 'BUY',
            'priority': 1000.0
        }

        await engine.order_queue.put(trade)

        assert not engine.order_queue.empty()
        assert engine.order_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_position_reconciliation(self, paper_binance_client, mock_risk_manager, mock_config):
        """Test position reconciliation."""
        engine = ExecutionEngine(paper_binance_client, mock_risk_manager, mock_config)

        # Set targets
        engine.target_positions = {'BTCUSDT': 1000.0}

        async with paper_binance_client:
            await engine.reconcile_positions()

            # Should detect drift and queue corrections if needed


class TestRiskIntegration:
    """Test integration with risk management."""

    @pytest.mark.asyncio
    async def test_risk_manager_integration(self, paper_binance_client, mock_config):
        """Test risk manager integration."""
        # Create real risk manager with test config
        risk_config = {
            'portfolio': {
                'max_total_exposure_usdt': 50000,
                'max_leverage': 3.0,
                'drawdown_limits': {
                    'warning_level': 0.05,
                    'halt_level': 0.10,
                    'emergency_stop': 0.20
                }
            },
            'pair': {
                'max_pair_weight': 0.20,
                'max_position_value_usdt': 10000
            },
            'temporal': {
                'cool_down_periods': {
                    'after_halt_minutes': 30
                }
            }
        }

        risk_manager = PositionRiskManager(risk_config, 100000)
        engine = ExecutionEngine(paper_binance_client, risk_manager, mock_config)

        # Test trade validation
        trade = {
            'symbol': 'BTCUSDT',
            'difference_usd': 5000.0  # Within limits
        }

        is_valid = await risk_manager.validate_trade(trade)
        assert is_valid is True

        # Test oversized trade
        large_trade = {
            'symbol': 'BTCUSDT',
            'difference_usd': 100000.0  # Exceeds limits
        }

        is_valid = await risk_manager.validate_trade(large_trade)
        assert is_valid is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])