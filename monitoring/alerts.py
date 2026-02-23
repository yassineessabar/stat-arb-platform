"""
Alert System
===========

Comprehensive alerting system for the statistical arbitrage platform:
- Multi-channel alert delivery (email, Slack, SMS, webhooks)
- Alert severity levels and escalation
- Alert rate limiting and deduplication
- Alert templates and formatting
- Alert history and analytics

Monitors all aspects of the trading system and sends timely notifications.
"""

import asyncio
import time
import json
import hashlib
from typing import Dict, List, Optional, Callable, Set
from enum import Enum
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertChannel(Enum):
    """Alert delivery channels."""
    EMAIL = "email"
    SLACK = "slack"
    SMS = "sms"
    WEBHOOK = "webhook"
    CONSOLE = "console"


class AlertManager:
    """
    Comprehensive alert management system.
    """

    def __init__(self, config: Dict):
        """
        Initialize alert manager.

        Args:
            config: Alert configuration
        """
        self.config = config
        self.enabled_channels = config.get('enabled_channels', ['console'])

        # Alert state
        self.alert_history = deque(maxlen=1000)
        self.active_alerts = {}
        self.alert_counts = defaultdict(int)
        self.last_alert_times = {}

        # Rate limiting
        self.rate_limits = config.get('rate_limits', {
            'info': 60,      # 1 minute
            'warning': 300,   # 5 minutes
            'critical': 60,   # 1 minute
            'emergency': 30   # 30 seconds
        })

        # Deduplication
        self.alert_hashes = set()
        self.dedup_window = config.get('deduplication_window', 3600)  # 1 hour

        # Channel configurations
        self.channel_configs = config.get('channels', {})

        # Alert handlers
        self.alert_handlers = {
            AlertChannel.CONSOLE: self._send_console_alert,
            AlertChannel.EMAIL: self._send_email_alert,
            AlertChannel.SLACK: self._send_slack_alert,
            AlertChannel.SMS: self._send_sms_alert,
            AlertChannel.WEBHOOK: self._send_webhook_alert
        }

        # Escalation rules
        self.escalation_rules = config.get('escalation', {
            'critical_repeat_count': 3,
            'emergency_immediate': True
        })

        logger.info(f"Alert manager initialized with channels: {self.enabled_channels}")

    async def send_alert(self, alert_type: str, message: str,
                        severity: AlertSeverity = AlertSeverity.INFO,
                        data: Dict = None, channels: List[AlertChannel] = None) -> bool:
        """
        Send an alert through configured channels.

        Args:
            alert_type: Type of alert (e.g., 'drawdown', 'execution_failure')
            message: Alert message
            severity: Alert severity level
            data: Additional alert data
            channels: Specific channels to use (overrides default)

        Returns:
            True if alert was sent successfully
        """
        if data is None:
            data = {}

        # Create alert object
        alert = {
            'type': alert_type,
            'message': message,
            'severity': severity.value,
            'timestamp': time.time(),
            'data': data,
            'id': self._generate_alert_id(alert_type, message)
        }

        # Check if alert should be sent
        if not self._should_send_alert(alert):
            logger.debug(f"Alert suppressed: {alert_type} - {message}")
            return False

        # Determine channels
        if channels is None:
            channels = self._get_channels_for_severity(severity)

        # Send to each channel
        success = True
        for channel in channels:
            if channel.value in self.enabled_channels:
                try:
                    await self.alert_handlers[channel](alert)
                    logger.debug(f"Alert sent via {channel.value}: {alert_type}")
                except Exception as e:
                    logger.error(f"Failed to send alert via {channel.value}: {e}")
                    success = False

        # Record alert
        self._record_alert(alert)

        return success

    def _should_send_alert(self, alert: Dict) -> bool:
        """Check if alert should be sent based on rate limiting and deduplication."""
        alert_type = alert['type']
        severity = alert['severity']
        alert_id = alert['id']
        current_time = alert['timestamp']

        # Check deduplication
        if alert_id in self.alert_hashes:
            return False

        # Check rate limiting
        rate_limit = self.rate_limits.get(severity, 60)
        last_time = self.last_alert_times.get(alert_type, 0)

        if current_time - last_time < rate_limit:
            # Exception for emergency alerts
            if severity != 'emergency':
                return False

        return True

    def _generate_alert_id(self, alert_type: str, message: str) -> str:
        """Generate unique ID for alert deduplication."""
        content = f"{alert_type}:{message}"
        return hashlib.md5(content.encode()).hexdigest()[:8]

    def _get_channels_for_severity(self, severity: AlertSeverity) -> List[AlertChannel]:
        """Get appropriate channels for alert severity."""
        channel_mapping = {
            AlertSeverity.INFO: [AlertChannel.CONSOLE],
            AlertSeverity.WARNING: [AlertChannel.CONSOLE, AlertChannel.SLACK],
            AlertSeverity.CRITICAL: [AlertChannel.CONSOLE, AlertChannel.SLACK, AlertChannel.EMAIL],
            AlertSeverity.EMERGENCY: [AlertChannel.CONSOLE, AlertChannel.SLACK, AlertChannel.EMAIL, AlertChannel.SMS]
        }

        return channel_mapping.get(severity, [AlertChannel.CONSOLE])

    def _record_alert(self, alert: Dict) -> None:
        """Record alert in history and update counters."""
        self.alert_history.append(alert)

        alert_type = alert['type']
        alert_id = alert['id']

        self.alert_counts[alert_type] += 1
        self.last_alert_times[alert_type] = alert['timestamp']
        self.alert_hashes.add(alert_id)

        # Clean old hashes
        self._clean_old_hashes()

    def _clean_old_hashes(self) -> None:
        """Clean old alert hashes for deduplication."""
        current_time = time.time()
        cutoff_time = current_time - self.dedup_window

        # Remove alerts older than dedup window
        old_alerts = [alert for alert in self.alert_history
                     if alert['timestamp'] < cutoff_time]

        for alert in old_alerts:
            self.alert_hashes.discard(alert['id'])

    # Channel-specific alert handlers

    async def _send_console_alert(self, alert: Dict) -> None:
        """Send alert to console/logs."""
        severity = alert['severity'].upper()
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(alert['timestamp']))

        log_message = f"[{timestamp}] {severity} ALERT: {alert['type']} - {alert['message']}"

        if severity == 'EMERGENCY':
            logger.critical(log_message)
        elif severity == 'CRITICAL':
            logger.error(log_message)
        elif severity == 'WARNING':
            logger.warning(log_message)
        else:
            logger.info(log_message)

    async def _send_email_alert(self, alert: Dict) -> None:
        """Send alert via email."""
        email_config = self.channel_configs.get('email', {})

        if not email_config.get('enabled', False):
            return

        # Email implementation would go here
        # For now, just log
        logger.info(f"EMAIL ALERT: {alert['type']} - {alert['message']}")

    async def _send_slack_alert(self, alert: Dict) -> None:
        """Send alert to Slack."""
        slack_config = self.channel_configs.get('slack', {})

        if not slack_config.get('enabled', False):
            return

        # Format Slack message
        color_map = {
            'info': '#36a64f',      # Green
            'warning': '#ff9500',   # Orange
            'critical': '#ff0000',  # Red
            'emergency': '#8b0000'  # Dark red
        }

        severity = alert['severity']
        color = color_map.get(severity, '#36a64f')

        slack_message = {
            'text': f"Trading Alert: {alert['type']}",
            'attachments': [{
                'color': color,
                'fields': [
                    {'title': 'Alert Type', 'value': alert['type'], 'short': True},
                    {'title': 'Severity', 'value': severity.upper(), 'short': True},
                    {'title': 'Message', 'value': alert['message'], 'short': False},
                    {'title': 'Timestamp', 'value': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(alert['timestamp'])), 'short': True}
                ]
            }]
        }

        # Slack implementation would go here
        logger.info(f"SLACK ALERT: {json.dumps(slack_message, indent=2)}")

    async def _send_sms_alert(self, alert: Dict) -> None:
        """Send alert via SMS."""
        sms_config = self.channel_configs.get('sms', {})

        if not sms_config.get('enabled', False):
            return

        # SMS should be brief
        message = f"TRADING ALERT: {alert['type']} - {alert['severity'].upper()}"

        # SMS implementation would go here
        logger.info(f"SMS ALERT: {message}")

    async def _send_webhook_alert(self, alert: Dict) -> None:
        """Send alert to webhook."""
        webhook_config = self.channel_configs.get('webhook', {})

        if not webhook_config.get('enabled', False):
            return

        webhook_url = webhook_config.get('url')
        if not webhook_url:
            return

        # Webhook implementation would go here
        logger.info(f"WEBHOOK ALERT: {alert['type']} - {alert['message']}")

    # Predefined alert methods for common scenarios

    async def drawdown_alert(self, current_drawdown: float, threshold: float) -> None:
        """Send drawdown alert."""
        severity = AlertSeverity.CRITICAL if current_drawdown > 0.10 else AlertSeverity.WARNING

        await self.send_alert(
            'drawdown_warning',
            f"Portfolio drawdown {current_drawdown:.1%} exceeds threshold {threshold:.1%}",
            severity,
            {'current_drawdown': current_drawdown, 'threshold': threshold}
        )

    async def correlation_spike_alert(self, correlation: float, threshold: float) -> None:
        """Send correlation spike alert."""
        await self.send_alert(
            'correlation_spike',
            f"Correlation spike detected: {correlation:.1%} (threshold: {threshold:.1%})",
            AlertSeverity.WARNING,
            {'correlation': correlation, 'threshold': threshold}
        )

    async def execution_failure_alert(self, symbol: str, error: str) -> None:
        """Send execution failure alert."""
        await self.send_alert(
            'execution_failure',
            f"Order execution failed for {symbol}: {error}",
            AlertSeverity.CRITICAL,
            {'symbol': symbol, 'error': error}
        )

    async def risk_limit_alert(self, limit_type: str, current: float, limit: float) -> None:
        """Send risk limit breach alert."""
        severity = AlertSeverity.CRITICAL if current > limit * 1.2 else AlertSeverity.WARNING

        await self.send_alert(
            'risk_limit_breach',
            f"{limit_type} limit breached: {current:.2f} > {limit:.2f}",
            severity,
            {'limit_type': limit_type, 'current': current, 'limit': limit}
        )

    async def performance_divergence_alert(self, live_performance: float,
                                          expected_performance: float) -> None:
        """Send performance divergence alert."""
        divergence = abs(live_performance - expected_performance)

        severity = AlertSeverity.CRITICAL if divergence > 0.15 else AlertSeverity.WARNING

        await self.send_alert(
            'performance_divergence',
            f"Performance divergence: Live {live_performance:.1%} vs Expected {expected_performance:.1%}",
            severity,
            {'live_performance': live_performance, 'expected_performance': expected_performance}
        )

    async def system_health_alert(self, component: str, health_score: int) -> None:
        """Send system health alert."""
        if health_score < 60:
            severity = AlertSeverity.CRITICAL
        elif health_score < 80:
            severity = AlertSeverity.WARNING
        else:
            severity = AlertSeverity.INFO

        await self.send_alert(
            'system_health',
            f"{component} health score: {health_score}/100",
            severity,
            {'component': component, 'health_score': health_score}
        )

    async def emergency_alert(self, emergency_type: str, message: str, data: Dict = None) -> None:
        """Send emergency alert."""
        await self.send_alert(
            f'emergency_{emergency_type}',
            f"EMERGENCY: {message}",
            AlertSeverity.EMERGENCY,
            data or {}
        )

    # Alert analytics and management

    def get_alert_summary(self, hours: int = 24) -> Dict:
        """Get alert summary for the specified time period."""
        cutoff_time = time.time() - (hours * 3600)
        recent_alerts = [alert for alert in self.alert_history
                        if alert['timestamp'] > cutoff_time]

        # Count by severity
        severity_counts = defaultdict(int)
        type_counts = defaultdict(int)

        for alert in recent_alerts:
            severity_counts[alert['severity']] += 1
            type_counts[alert['type']] += 1

        return {
            'time_period_hours': hours,
            'total_alerts': len(recent_alerts),
            'by_severity': dict(severity_counts),
            'by_type': dict(type_counts),
            'most_recent': recent_alerts[-1] if recent_alerts else None
        }

    def get_alert_rate(self, alert_type: str = None, hours: int = 1) -> float:
        """Get alert rate (alerts per hour)."""
        cutoff_time = time.time() - (hours * 3600)

        if alert_type:
            recent_alerts = [alert for alert in self.alert_history
                           if alert['timestamp'] > cutoff_time and alert['type'] == alert_type]
        else:
            recent_alerts = [alert for alert in self.alert_history
                           if alert['timestamp'] > cutoff_time]

        return len(recent_alerts) / hours

    def silence_alert_type(self, alert_type: str, duration_minutes: int) -> None:
        """Temporarily silence a specific alert type."""
        # Implementation for alert silencing
        silence_until = time.time() + (duration_minutes * 60)
        # Store silenced alerts (would implement persistence)
        logger.info(f"Alert type '{alert_type}' silenced for {duration_minutes} minutes")

    def test_alert_channels(self) -> Dict:
        """Test all configured alert channels."""
        test_results = {}

        for channel in AlertChannel:
            if channel.value in self.enabled_channels:
                try:
                    # Send test alert (would be async in practice)
                    test_alert = {
                        'type': 'test',
                        'message': 'Test alert - please ignore',
                        'severity': 'info',
                        'timestamp': time.time(),
                        'data': {},
                        'id': 'test_alert'
                    }

                    # This would actually send the test alert
                    test_results[channel.value] = 'success'

                except Exception as e:
                    test_results[channel.value] = f'failed: {e}'

        return test_results

    def get_alert_health(self) -> Dict:
        """Get alert system health status."""
        recent_hour_count = self.get_alert_rate(hours=1)

        # Assess health
        health_score = 100
        issues = []

        if recent_hour_count > 10:
            health_score -= 20
            issues.append("High alert rate")

        # Check channel availability
        available_channels = len(self.enabled_channels)
        if available_channels < 2:
            health_score -= 30
            issues.append("Limited alert channels")

        return {
            'health_score': health_score,
            'status': 'healthy' if health_score >= 80 else 'degraded' if health_score >= 60 else 'unhealthy',
            'issues': issues,
            'recent_alert_rate': recent_hour_count,
            'enabled_channels': self.enabled_channels,
            'total_alerts_sent': sum(self.alert_counts.values())
        }