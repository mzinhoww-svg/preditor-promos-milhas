"""Interval-based temporal evidence for Loyalty Intelligence v2.1.

Pure stdlib module: does not modify existing collector or persistence behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

Precision = Literal["minute", "hour", "day", "interval", "unknown"]


@dataclass(frozen=True)
class TimeInterval:
    t_min: datetime | None
    t_max: datetime | None
    precision: Precision = "unknown"

    def __post_init__(self) -> None:
        for value in (self.t_min, self.t_max):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError("Time evidence must be timezone-aware")
        if self.t_min is not None and self.t_max is not None and self.t_min > self.t_max:
            raise ValueError("t_min must be <= t_max")

    def as_utc(self) -> "TimeInterval":
        return TimeInterval(
            self.t_min.astimezone(timezone.utc) if self.t_min else None,
            self.t_max.astimezone(timezone.utc) if self.t_max else None,
            self.precision,
        )


@dataclass(frozen=True)
class CampaignClock:
    announcement: TimeInterval
    effective_start: TimeInterval
    discovery: TimeInterval

    def __post_init__(self) -> None:
        # Distinct clocks by design. Do not infer announcement from effective start.
        pass


def definitely_precedes(a: TimeInterval, b: TimeInterval) -> bool | None:
    """True only if A's latest possible time is earlier than B's earliest.

    False if B definitely precedes A or intervals overlap. None if bounds
    do not support a determination.
    """
    if a.t_max is None or b.t_min is None:
        return None
    return a.t_max < b.t_min
