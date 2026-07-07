"""Shared period-boundary helpers for dashboard/report filtering.

All stored timestamps are naive UTC (SQLite drops tzinfo on write), while the
farm operates on the server's local timezone (SAST). Period boundaries are
therefore defined in FARM-LOCAL terms and converted for comparison:

    today  = local midnight this morning
    week   = local midnight, 7 days ago
    season = Jan 1 of the current year, local
             (a true Nov-Feb litchi-season boundary via SystemSetting is a
             possible future refinement)

Use period_start_utc() against naive-UTC datetime columns and
period_start_date() against local-date columns (e.g. PalletRecord.date).
"""
from datetime import date, datetime, time, timedelta, timezone


def _local_tz():
    return datetime.now().astimezone().tzinfo


def period_start_local(period: str) -> datetime:
    """Aware datetime of the farm-local period start."""
    midnight = datetime.combine(date.today(), time.min).replace(tzinfo=_local_tz())
    if period == "week":
        return midnight - timedelta(days=7)
    if period == "season":
        return midnight.replace(month=1, day=1)
    return midnight  # "today"


def period_start_utc(period: str) -> datetime:
    """Naive-UTC boundary comparable to stored naive-UTC datetime columns."""
    return period_start_local(period).astimezone(timezone.utc).replace(tzinfo=None)


def period_start_date(period: str) -> date:
    """Local date boundary for local-date columns (e.g. PalletRecord.date)."""
    return period_start_local(period).date()
