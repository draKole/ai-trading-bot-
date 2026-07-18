"""Session Engine — configurable trading session definitions.

Supports Asia, London, New York AM, New York PM with timezone-aware
boundary detection and daylight saving handling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class SessionName(str, Enum):
    ASIA = "asia"
    LONDON = "london"
    NY_AM = "ny_am"
    NY_PM = "ny_pm"


# Default session times in US Eastern (ET)
# Asia: 20:00–02:00 ET (Tokyo 9:00–15:00 JST → 20:00–02:00 ET previous day)
# London: 03:00–11:00 ET (London 8:00–16:00 GMT → 03:00–11:00 ET)
# NY AM: 09:30–12:00 ET
# NY PM: 12:00–16:00 ET

DEFAULT_SESSION_TIMES: dict[SessionName, tuple[time, time]] = {
    SessionName.ASIA: (time(20, 0), time(2, 0)),     # overnight
    SessionName.LONDON: (time(3, 0), time(11, 0)),
    SessionName.NY_AM: (time(9, 30), time(12, 0)),
    SessionName.NY_PM: (time(12, 0), time(16, 0)),
}

# Session display order for chronological sorting
SESSION_ORDER = [SessionName.ASIA, SessionName.LONDON, SessionName.NY_AM, SessionName.NY_PM]


@dataclass
class SessionConfig:
    """Configuration for trading sessions.

    Attributes:
        timezone: IANA timezone string (e.g. "America/New_York").
        session_times: Mapping of session name to (start, end) times in the
            configured timezone.
        use_dst: Whether to respect DST transitions (default True).
    """
    timezone: str = "America/New_York"
    session_times: dict[SessionName, tuple[time, time]] = field(
        default_factory=lambda: dict(DEFAULT_SESSION_TIMES)
    )
    use_dst: bool = True

    def get_tz(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            raise ValueError(f"Unknown timezone: {self.timezone}")

    def to_dict(self) -> dict:
        return {
            "timezone": self.timezone,
            "session_times": {
                k.value: (v[0].isoformat(), v[1].isoformat())
                for k, v in self.session_times.items()
            },
            "use_dst": self.use_dst,
        }

    @classmethod
    def from_dict(cls, d: dict) -> SessionConfig:
        session_times = {}
        for k, v in d.get("session_times", {}).items():
            start_parts = v[0].split(":")
            end_parts = v[1].split(":")
            session_times[SessionName(k)] = (
                time(int(start_parts[0]), int(start_parts[1])),
                time(int(end_parts[0]), int(end_parts[1])),
            )
        return cls(
            timezone=d.get("timezone", "America/New_York"),
            session_times=session_times or dict(DEFAULT_SESSION_TIMES),
            use_dst=d.get("use_dst", True),
        )


@dataclass
class SessionBoundary:
    """A detected session start/end boundary."""
    session: SessionName
    start_utc: datetime
    end_utc: datetime
    start_local: datetime
    end_local: datetime


class SessionEngine:
    """Determines which session(s) a bar belongs to and computes session boundaries."""

    def __init__(self, config: SessionConfig | None = None):
        self.config = config or SessionConfig()
        self._tz = self.config.get_tz()

    def get_session(self, utc_dt: datetime) -> SessionName | None:
        """Return the session a UTC timestamp belongs to, or None.

        When sessions overlap (e.g., London + NY AM 9:30–11:00 ET),
        the later-starting session takes priority.
        """
        local_dt = utc_dt.astimezone(self._tz)
        local_t = local_dt.time()

        active = []
        for session in SESSION_ORDER:
            start_t, end_t = self.config.session_times[session]
            if _time_in_range(local_t, start_t, end_t):
                active.append(session)

        if not active:
            return None
        # Return the last (latest-starting) active session
        return active[-1]

    def get_active_sessions(self, utc_dt: datetime) -> list[SessionName]:
        """Return all sessions active at a given UTC timestamp (usually 0–1)."""
        session = self.get_session(utc_dt)
        return [session] if session else []

    def compute_session_boundary(
        self, session: SessionName, reference_date_utc: datetime,
    ) -> SessionBoundary:
        """Compute the UTC start/end of a session for a given reference day.

        The reference date is converted to local time, then the session
        start/end are applied. Handles overnight sessions correctly.
        """
        local_dt = reference_date_utc.astimezone(self._tz)
        local_date = local_dt.date()
        start_t, end_t = self.config.session_times[session]

        # Start: combine local_date + start_t
        start_local = datetime.combine(local_date, start_t, tzinfo=self._tz)

        # End: if end_t <= start_t, it's an overnight session (ends next day)
        if end_t <= start_t:
            end_local = datetime.combine(
                local_date + timedelta(days=1), end_t, tzinfo=self._tz,
            )
        else:
            end_local = datetime.combine(local_date, end_t, tzinfo=self._tz)

        return SessionBoundary(
            session=session,
            start_utc=start_local.astimezone(ZoneInfo("UTC")),
            end_utc=end_local.astimezone(ZoneInfo("UTC")),
            start_local=start_local,
            end_local=end_local,
        )

    def get_session_boundaries(
        self, utc_dt: datetime,
    ) -> dict[SessionName, SessionBoundary]:
        """Get all session boundaries that contain or precede the given time."""
        boundaries = {}
        for session in SESSION_ORDER:
            boundary = self.compute_session_boundary(session, utc_dt)
            # If the session hasn't started yet for this date, use previous
            if boundary.start_utc > utc_dt:
                prev_day = utc_dt - timedelta(days=1)
                boundary = self.compute_session_boundary(session, prev_day)
            boundaries[session] = boundary
        return boundaries

    def get_session_for_bar(
        self, bar_timestamp_utc: datetime,
    ) -> dict[SessionName, SessionBoundary]:
        """Return the session boundaries that apply to a bar.

        For a given bar timestamp, returns the boundaries of the session
        the bar belongs to, plus the previous completed session for
        computing previous session highs/lows.
        """
        current_session = self.get_session(bar_timestamp_utc)
        all_boundaries = self.get_session_boundaries(bar_timestamp_utc)

        if current_session is None:
            # Between sessions — return the last completed session
            for session in reversed(SESSION_ORDER):
                boundary = all_boundaries[session]
                if boundary.end_utc <= bar_timestamp_utc:
                    return {session: boundary}
            return {}

        return {current_session: all_boundaries[current_session]}


def _time_in_range(t: time, start: time, end: time) -> bool:
    """Check if time t is in [start, end), handling overnight ranges."""
    if start <= end:
        return start <= t < end
    else:
        # Overnight: e.g. 20:00–02:00
        return t >= start or t < end
