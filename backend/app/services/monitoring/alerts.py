"""Alert Engine — alert generation, severity, acknowledgement, resolution."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


@dataclass
class Alert:
    """A monitoring alert with lifecycle management."""
    alert_id: str = field(default_factory=lambda: str(uuid4()))
    alert_type: str = ""
    severity: str = "warning"
    message: str = ""
    status: str = "active"
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id, "alert_type": self.alert_type,
            "severity": self.severity, "message": self.message,
            "status": self.status,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "created_at": self.created_at.isoformat(),
        }


class AlertManager:
    """Manages alert lifecycle: creation, acknowledgement, resolution."""

    def __init__(self):
        self._alerts: list[Alert] = []

    @property
    def alerts(self) -> list[Alert]:
        return list(self._alerts)

    @property
    def active_alerts(self) -> list[Alert]:
        return [a for a in self._alerts if a.status == "active"]

    def create_alert(self, alert_type: str, message: str,
                     severity: str = "warning") -> Alert:
        """Create a new alert."""
        alert = Alert(
            alert_type=alert_type, severity=severity,
            message=message, status="active",
        )
        self._alerts.append(alert)
        return alert

    def acknowledge_alert(self, alert_id: str) -> Alert | None:
        """Acknowledge an active alert."""
        alert = self._find(alert_id)
        if alert and alert.status == "active":
            alert.status = "acknowledged"
            alert.acknowledged_at = datetime.now(timezone.utc)
        return alert

    def resolve_alert(self, alert_id: str) -> Alert | None:
        """Resolve an alert."""
        alert = self._find(alert_id)
        if alert and alert.status in ("active", "acknowledged"):
            alert.status = "resolved"
            alert.resolved_at = datetime.now(timezone.utc)
        return alert

    def get_alerts(self, status: str | None = None,
                   severity: str | None = None) -> list[dict]:
        """Get alerts with optional filters."""
        alerts = self._alerts
        if status:
            alerts = [a for a in alerts if a.status == status]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return [a.to_dict() for a in alerts]

    def get_summary(self) -> dict:
        """Alert summary by status and severity."""
        active = len(self.active_alerts)
        acknowledged = sum(1 for a in self._alerts if a.status == "acknowledged")
        resolved = sum(1 for a in self._alerts if a.status == "resolved")
        critical = sum(1 for a in self._alerts if a.severity == "critical" and a.status == "active")
        return {
            "total": len(self._alerts),
            "active": active,
            "acknowledged": acknowledged,
            "resolved": resolved,
            "active_critical": critical,
        }

    def _find(self, alert_id: str) -> Alert | None:
        for a in self._alerts:
            if a.alert_id == alert_id:
                return a
        return None
