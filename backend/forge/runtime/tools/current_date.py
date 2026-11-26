"""Today's date, for time-relative questions. FORGE_FIXED_DATE makes it reproducible in tests."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field

from forge.runtime.tools.base import Tool


class DateArgs(BaseModel):
    timezone: str = Field(default="UTC", description="IANA timezone name, e.g. 'Europe/Oslo'")
    offset_days: int = Field(default=0, ge=-3650, le=3650, description="Add this many days to today")


def today(tz: str = "UTC") -> date:
    fixed = os.environ.get("FORGE_FIXED_DATE")
    if fixed:
        return date.fromisoformat(fixed)
    try:
        return datetime.now(ZoneInfo(tz)).date()
    except ZoneInfoNotFoundError:
        return datetime.now(timezone.utc).date()


class CurrentDateTool(Tool):
    name = "current_date"
    description = "Get today's date (optionally shifted by offset_days). Use it for 'today', 'days until', 'still valid'."
    Args = DateArgs

    def _run(self, args: DateArgs):
        d = today(args.timezone) + timedelta(days=args.offset_days)
        return {"date": d.isoformat(), "weekday": d.strftime("%A"), "iso_week": d.isocalendar().week,
                "timezone": args.timezone, "offset_days": args.offset_days}
