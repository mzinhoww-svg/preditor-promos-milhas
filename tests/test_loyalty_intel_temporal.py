from datetime import datetime, timezone

import pytest

from preditor.loyalty_intel.temporal import CampaignClock, TimeInterval, definitely_precedes


def dt(hour: int) -> datetime:
    return datetime(2026, 11, 23, hour, tzinfo=timezone.utc)


def test_interval_rejects_inverted_bounds():
    with pytest.raises(ValueError):
        TimeInterval(dt(11), dt(10), "interval")


def test_interval_rejects_naive_datetime():
    with pytest.raises(ValueError):
        TimeInterval(datetime(2026, 11, 23), dt(10), "day")


def test_unknown_time_is_not_fabricated():
    assert definitely_precedes(TimeInterval(None, None), TimeInterval(dt(11), dt(12))) is None


def test_article_publication_is_not_campaign_start():
    clocks = CampaignClock(
        announcement=TimeInterval(dt(9), dt(10), "hour"),
        effective_start=TimeInterval(dt(8), dt(8), "minute"),
        discovery=TimeInterval(dt(13), dt(13), "minute"),
    )
    assert clocks.announcement.t_min != clocks.effective_start.t_min
    assert definitely_precedes(clocks.announcement, clocks.discovery) is True
