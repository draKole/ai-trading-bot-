"""Security Monitor — brute-force detection, anomaly detection."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SecurityAlert:
    """Generated security alert."""
    alert_id: str = ""
    alert_type: str = ""
    detail: str = ""
    severity: str = "warning"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id, "alert_type": self.alert_type,
            "detail": self.detail, "severity": self.severity,
            "timestamp": self.timestamp.isoformat(),
        }


class SecurityMonitor:
    """Detects security anomalies: brute force, excessive requests, etc."""

    def __init__(self):
        self._login_attempts: dict[str, int] = defaultdict(int)
        self._request_counts: dict[str, int] = defaultdict(int)
        self._alerts: list[SecurityAlert] = []
        self._blocked: set[str] = set()

    def record_login_attempt(self, username: str, success: bool) -> None:
        if not success:
            self._login_attempts[username] += 1

    def check_brute_force(self, username: str, threshold: int = 5) -> bool:
        """Check if brute force threshold exceeded."""
        return self._login_attempts.get(username, 0) >= threshold

    def block_ip(self, ip: str) -> None:
        self._blocked.add(ip)

    def is_blocked(self, ip: str) -> bool:
        return ip in self._blocked

    def record_request(self, ip: str) -> None:
        self._request_counts[ip] += 1

    def check_rate_limit(self, ip: str, max_requests: int = 100) -> bool:
        """Check if rate limit exceeded."""
        return self._request_counts.get(ip, 0) > max_requests

    def add_alert(self, alert_type: str, detail: str,
                  severity: str = "warning") -> SecurityAlert:
        import uuid
        alert = SecurityAlert(
            alert_id=str(uuid.uuid4()),
            alert_type=alert_type, detail=detail, severity=severity,
        )
        self._alerts.append(alert)
        return alert

    def get_alerts(self, severity: str | None = None) -> list[dict]:
        alerts = self._alerts
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return [a.to_dict() for a in alerts]

    def get_summary(self) -> dict:
        critical = sum(1 for a in self._alerts if a.severity == "critical")
        return {
            "total_alerts": len(self._alerts),
            "critical": critical,
            "blocked_ips": len(self._blocked),
        }
