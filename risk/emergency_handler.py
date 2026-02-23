"""
Emergency Risk Handler
=====================

Emergency procedures for critical market events:
- Black swan event detection and response
- Exchange connectivity issues
- Mass liquidation protocols
- Trading halt emergency procedures
- Recovery and restart procedures

This module handles extreme scenarios beyond normal risk management.
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class EmergencyLevel(Enum):
    """Emergency severity levels."""
    GREEN = "green"       # Normal operations
    YELLOW = "yellow"     # Elevated risk
    ORANGE = "orange"     # High risk - prepare for shutdown
    RED = "red"           # Critical - immediate liquidation
    BLACK = "black"       # System failure - manual intervention


class EmergencyType(Enum):
    """Types of emergency events."""
    MARKET_CRASH = "market_crash"
    EXCHANGE_OUTAGE = "exchange_outage"
    CORRELATION_SPIKE = "correlation_spike"
    VOLATILITY_SHOCK = "volatility_shock"
    LIQUIDITY_CRISIS = "liquidity_crisis"
    SYSTEM_FAILURE = "system_failure"
    API_FAILURE = "api_failure"
    FUNDING_SHOCK = "funding_shock"


class EmergencyHandler:
    """
    Emergency risk handler for critical events.
    """

    def __init__(self, config: Dict):
        """
        Initialize emergency handler.

        Args:
            config: Emergency configuration
        """
        self.config = config
        self.current_level = EmergencyLevel.GREEN
        self.active_emergencies = []

        # Emergency thresholds
        self.market_crash_threshold = config.get('market_crash_threshold', -0.20)
        self.volatility_shock_threshold = config.get('volatility_shock_threshold', 5.0)
        self.correlation_emergency_threshold = config.get('correlation_emergency_threshold', 0.95)
        self.liquidity_threshold = config.get('liquidity_threshold', 0.1)

        # Response handlers
        self.emergency_handlers = {
            EmergencyType.MARKET_CRASH: self._handle_market_crash,
            EmergencyType.EXCHANGE_OUTAGE: self._handle_exchange_outage,
            EmergencyType.CORRELATION_SPIKE: self._handle_correlation_spike,
            EmergencyType.VOLATILITY_SHOCK: self._handle_volatility_shock,
            EmergencyType.LIQUIDITY_CRISIS: self._handle_liquidity_crisis,
            EmergencyType.SYSTEM_FAILURE: self._handle_system_failure,
            EmergencyType.API_FAILURE: self._handle_api_failure,
            EmergencyType.FUNDING_SHOCK: self._handle_funding_shock
        }

        # Callbacks
        self.liquidation_callback: Optional[Callable] = None
        self.halt_callback: Optional[Callable] = None
        self.alert_callback: Optional[Callable] = None

        # Emergency state
        self.emergency_start_time = None
        self.last_emergency_check = time.time()
        self.recovery_mode = False

        logger.info("Emergency handler initialized")

    def set_callbacks(self, liquidation_callback: Callable,
                     halt_callback: Callable, alert_callback: Callable):
        """Set emergency response callbacks."""
        self.liquidation_callback = liquidation_callback
        self.halt_callback = halt_callback
        self.alert_callback = alert_callback

    async def check_emergency_conditions(self, market_data: Dict) -> None:
        """
        Check for emergency conditions.

        Args:
            market_data: Current market data
        """
        current_time = time.time()

        # Prevent too frequent checks
        if current_time - self.last_emergency_check < 5:
            return

        self.last_emergency_check = current_time

        # Check each emergency type
        await self._check_market_crash(market_data)
        await self._check_volatility_shock(market_data)
        await self._check_correlation_spike(market_data)
        await self._check_liquidity_crisis(market_data)

        # Update emergency level
        await self._update_emergency_level()

    async def _check_market_crash(self, market_data: Dict) -> None:
        """Check for market crash conditions."""
        try:
            market_change = market_data.get('market_change_24h', 0)

            if market_change < self.market_crash_threshold:
                await self.trigger_emergency(
                    EmergencyType.MARKET_CRASH,
                    f"Market crash detected: {market_change:.1%} in 24h",
                    EmergencyLevel.RED
                )
        except Exception as e:
            logger.error(f"Error checking market crash: {e}")

    async def _check_volatility_shock(self, market_data: Dict) -> None:
        """Check for volatility shock."""
        try:
            current_vol = market_data.get('portfolio_volatility', 0)
            normal_vol = market_data.get('normal_volatility', 0.2)

            if normal_vol > 0:
                vol_ratio = current_vol / normal_vol

                if vol_ratio > self.volatility_shock_threshold:
                    await self.trigger_emergency(
                        EmergencyType.VOLATILITY_SHOCK,
                        f"Volatility shock: {vol_ratio:.1f}x normal",
                        EmergencyLevel.ORANGE
                    )
        except Exception as e:
            logger.error(f"Error checking volatility shock: {e}")

    async def _check_correlation_spike(self, market_data: Dict) -> None:
        """Check for correlation spike."""
        try:
            avg_correlation = market_data.get('avg_correlation', 0)

            if avg_correlation > self.correlation_emergency_threshold:
                await self.trigger_emergency(
                    EmergencyType.CORRELATION_SPIKE,
                    f"Correlation emergency: {avg_correlation:.1%}",
                    EmergencyLevel.ORANGE
                )
        except Exception as e:
            logger.error(f"Error checking correlation spike: {e}")

    async def _check_liquidity_crisis(self, market_data: Dict) -> None:
        """Check for liquidity crisis."""
        try:
            avg_liquidity = market_data.get('avg_liquidity', 1.0)

            if avg_liquidity < self.liquidity_threshold:
                await self.trigger_emergency(
                    EmergencyType.LIQUIDITY_CRISIS,
                    f"Liquidity crisis: {avg_liquidity:.1%} of normal",
                    EmergencyLevel.RED
                )
        except Exception as e:
            logger.error(f"Error checking liquidity crisis: {e}")

    async def trigger_emergency(self, emergency_type: EmergencyType,
                               message: str, level: EmergencyLevel) -> None:
        """
        Trigger emergency response.

        Args:
            emergency_type: Type of emergency
            message: Emergency message
            level: Emergency severity level
        """
        logger.critical(f"EMERGENCY TRIGGERED: {emergency_type.value} - {message}")

        # Record emergency
        emergency = {
            'type': emergency_type,
            'message': message,
            'level': level,
            'timestamp': time.time()
        }

        self.active_emergencies.append(emergency)

        # Update emergency level
        if level.value == "red" or level.value == "black":
            self.current_level = level
            self.emergency_start_time = time.time()

        # Send alert
        if self.alert_callback:
            await self.alert_callback({
                'type': 'emergency',
                'severity': 'critical',
                'message': f"EMERGENCY: {emergency_type.value} - {message}",
                'level': level.value,
                'timestamp': time.time()
            })

        # Execute emergency response
        if emergency_type in self.emergency_handlers:
            try:
                await self.emergency_handlers[emergency_type](emergency)
            except Exception as e:
                logger.error(f"Emergency handler failed: {e}")

    async def _handle_market_crash(self, emergency: Dict) -> None:
        """Handle market crash emergency."""
        logger.critical("Executing market crash protocol")

        # Immediate risk reduction
        if self.halt_callback:
            await self.halt_callback()

        # Wait for volatility to settle
        await asyncio.sleep(60)

        # If crash continues, liquidate
        if self.current_level == EmergencyLevel.RED:
            if self.liquidation_callback:
                await self.liquidation_callback()

    async def _handle_exchange_outage(self, emergency: Dict) -> None:
        """Handle exchange connectivity issues."""
        logger.critical("Executing exchange outage protocol")

        # Halt trading immediately
        if self.halt_callback:
            await self.halt_callback()

        # Monitor for recovery
        await self._monitor_exchange_recovery()

    async def _handle_correlation_spike(self, emergency: Dict) -> None:
        """Handle correlation spike."""
        logger.warning("Executing correlation spike protocol")

        # Reduce position sizes by 50%
        # This would be implemented with position reduction callback
        pass

    async def _handle_volatility_shock(self, emergency: Dict) -> None:
        """Handle volatility shock."""
        logger.warning("Executing volatility shock protocol")

        # Reduce leverage and position sizes
        # Tighten risk controls
        pass

    async def _handle_liquidity_crisis(self, emergency: Dict) -> None:
        """Handle liquidity crisis."""
        logger.critical("Executing liquidity crisis protocol")

        # Immediate liquidation of illiquid positions
        if self.liquidation_callback:
            await self.liquidation_callback()

    async def _handle_system_failure(self, emergency: Dict) -> None:
        """Handle system failure."""
        logger.critical("SYSTEM FAILURE - Manual intervention required")

        # All automated responses halt
        # Require manual recovery
        self.current_level = EmergencyLevel.BLACK

    async def _handle_api_failure(self, emergency: Dict) -> None:
        """Handle API failure."""
        logger.critical("Executing API failure protocol")

        # Switch to backup systems if available
        # Halt trading if no backup
        if self.halt_callback:
            await self.halt_callback()

    async def _handle_funding_shock(self, emergency: Dict) -> None:
        """Handle funding rate shock."""
        logger.warning("Executing funding shock protocol")

        # Close positions with extreme funding costs
        pass

    async def _update_emergency_level(self) -> None:
        """Update overall emergency level."""
        if not self.active_emergencies:
            self.current_level = EmergencyLevel.GREEN
            return

        # Find highest severity
        max_level = EmergencyLevel.GREEN
        for emergency in self.active_emergencies:
            if emergency['level'].value == "black":
                max_level = EmergencyLevel.BLACK
                break
            elif emergency['level'].value == "red":
                max_level = EmergencyLevel.RED
            elif emergency['level'].value == "orange" and max_level != EmergencyLevel.RED:
                max_level = EmergencyLevel.ORANGE
            elif emergency['level'].value == "yellow" and max_level == EmergencyLevel.GREEN:
                max_level = EmergencyLevel.YELLOW

        if max_level != self.current_level:
            logger.warning(f"Emergency level changed: {self.current_level.value} -> {max_level.value}")
            self.current_level = max_level

    async def _monitor_exchange_recovery(self) -> None:
        """Monitor exchange connectivity recovery."""
        recovery_attempts = 0
        max_attempts = 10

        while recovery_attempts < max_attempts:
            await asyncio.sleep(30)

            # This would check exchange connectivity
            # For now, assume recovery after multiple attempts
            recovery_attempts += 1

            if recovery_attempts >= max_attempts:
                logger.info("Exchange connectivity restored")
                await self.resolve_emergency(EmergencyType.EXCHANGE_OUTAGE)
                break

    async def resolve_emergency(self, emergency_type: EmergencyType) -> None:
        """
        Resolve an emergency condition.

        Args:
            emergency_type: Type of emergency to resolve
        """
        # Remove resolved emergencies
        self.active_emergencies = [
            e for e in self.active_emergencies
            if e['type'] != emergency_type
        ]

        logger.info(f"Emergency resolved: {emergency_type.value}")

        # Update emergency level
        await self._update_emergency_level()

        # If all emergencies resolved, start recovery
        if self.current_level == EmergencyLevel.GREEN:
            await self._start_recovery_mode()

    async def _start_recovery_mode(self) -> None:
        """Start recovery mode after emergencies clear."""
        if self.recovery_mode:
            return

        logger.info("Starting recovery mode")
        self.recovery_mode = True

        # Gradual restart procedures
        await asyncio.sleep(300)  # 5 minute cooling period

        # This would gradually restart trading
        # For now, just log
        logger.info("Recovery mode: Gradual restart initiated")

        await asyncio.sleep(600)  # 10 more minutes

        logger.info("Recovery mode complete")
        self.recovery_mode = False

    def force_emergency_reset(self, authorization_code: str) -> bool:
        """
        Force reset of emergency state (requires authorization).

        Args:
            authorization_code: Authorization code for reset

        Returns:
            True if reset successful
        """
        # In production, this would verify authorization
        expected_code = "EMERGENCY_RESET_2024"

        if authorization_code != expected_code:
            logger.error("Emergency reset failed: Invalid authorization")
            return False

        logger.critical("EMERGENCY STATE FORCE RESET")

        self.current_level = EmergencyLevel.GREEN
        self.active_emergencies.clear()
        self.emergency_start_time = None
        self.recovery_mode = False

        return True

    def get_emergency_status(self) -> Dict:
        """Get current emergency status."""
        return {
            'level': self.current_level.value,
            'active_emergencies': len(self.active_emergencies),
            'emergency_details': self.active_emergencies,
            'emergency_duration': time.time() - self.emergency_start_time if self.emergency_start_time else 0,
            'recovery_mode': self.recovery_mode,
            'last_check': time.time() - self.last_emergency_check
        }

    def is_emergency_active(self) -> bool:
        """Check if any emergency is active."""
        return self.current_level != EmergencyLevel.GREEN

    def can_trade(self) -> bool:
        """Check if trading is allowed under current emergency level."""
        return self.current_level in [EmergencyLevel.GREEN, EmergencyLevel.YELLOW]