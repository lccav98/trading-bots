"""
news_filter.py - Economic news volatility filter for trading pause decisions.

Since no paid news API is available, this module uses two complementary strategies:
1. Scheduled calendar of known high-impact US economic releases (calculated via
   Python's calendar/datetime modules).
2. yfinance-based volatility detection as a proxy for unexpected/unscheduled news.

Public interface:
    is_news_today()       -> (bool, str)
    is_news_impacting()   -> (bool, str)
    check_volatility()    -> (bool, str)
    should_pause()        -> (bool, str)
"""

from __future__ import annotations

import calendar
import json
import os
from collections import namedtuple
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# BRT = UTC-3 (Brazil Standard Time, no DST)
BRT_TZ = timezone(timedelta(hours=-3))
NEWS_WINDOW_MINUTES = 30  # pause window around each event

# Directory for the generated news calendar JSON
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# ---------------------------------------------------------------------------
# Internal types
# ---------------------------------------------------------------------------
NewsEvent = namedtuple("NewsEvent", ["name", "event_date", "event_time_brt"])

# ---------------------------------------------------------------------------
# Scheduled-news calendar logic
# ---------------------------------------------------------------------------
# Helper: determine US daylight-saving offset for a given month.
# US DST: second Sunday March -> first Sunday November.
# During DST, releases are 1 hour earlier UTC => same BRT clock (UTC-3 is fixed),
# but the *actual* release-time in BRT shifts.  Convention used below:
#   "summer" (US DST):  09:30 BRT
#   "winter" (US Std): 10:30 BRT
def _us_dst_active(dt: date) -> bool:
    """Return True if *dt* falls within US Daylight Saving Time."""
    if dt.month < 3 or dt.month > 11:
        return False  # January-February / December: standard time
    if 4 <= dt.month <= 10:
        return True  # April-October: always DST
    # March: DST starts 2nd Sunday
    if dt.month == 3:
        _, last_day = calendar.monthrange(dt.year, 3)
        dst_sunday = _nth_weekday(dt.year, 3, calendar.SUNDAY, 2)
        return dt.day >= dst_sunday
    # November: DST ends 1st Sunday
    dst_end = _nth_weekday(dt.year, 11, calendar.SUNDAY, 1)
    return dt.day < dst_end


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> int:
    """Return the day-of-month for the *n*-th occurrence of *weekday*."""
    first_day, last_day = calendar.monthrange(year, month)
    first_weekday = calendar.weekday(year, month, 1)
    offset = (weekday - first_weekday) % 7
    day = 1 + offset + (n - 1) * 7
    return min(day, last_day)


def _summer_time() -> time:
    return time(9, 30)  # BRT during US DST


def _winter_time() -> time:
    return time(10, 30)  # BRT during US standard time


def _event_time(d: date) -> time:
    return _summer_time() if _us_dst_active(d) else _winter_time()


def _calculate_monthly_events(year: int, month: int) -> list[NewsEvent]:
    """Calculate all scheduled high-impact events for a given month."""
    events: list[NewsEvent] = []

    # 1. Non-Farm Payrolls — first Friday of the month
    nfp_day = _nth_weekday(year, month, calendar.FRIDAY, 1)
    nfp_date = date(year, month, nfp_day)
    events.append(NewsEvent("Non-Farm Payrolls", nfp_date, _event_time(nfp_date)))

    # 2. CPI / PPI — around the 15th of the month
    cpi_day = min(_nth_weekday(year, month, calendar.WEDNESDAY, 2), 16)
    if cpi_day < 13:
        cpi_day = 15  # fallback
    cpi_date = date(year, month, cpi_day)
    events.append(NewsEvent("CPI/PPI", cpi_date, _event_time(cpi_date)))

    # 3. Initial Jobless Claims — every Thursday
    # Walk all Thursdays in the month
    first_day_wd = calendar.weekday(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    thursday_offset = (calendar.THURSDAY - first_day_wd) % 7
    thursday = 1 + thursday_offset
    while thursday <= last_day:
        claims_date = date(year, month, thursday)
        events.append(NewsEvent("Initial Jobless Claims", claims_date, _event_time(claims_date)))
        thursday += 7

    # 4. Retail Sales — around the 15th
    retail_day = 15
    retail_date = date(year, month, retail_day)
    events.append(NewsEvent("Retail Sales", retail_date, _event_time(retail_date)))

    # 5. GDP — last week of quarter-end months (Mar, Jun, Sep, Dec)
    if month in (3, 6, 9, 12):
        # Approximate: third Thursday of the last week
        gdp_week_start = last_day - 6
        gdp_day = _find_first_weekday_in_range(year, month, calendar.THURSDAY, gdp_week_start, last_day)
        if gdp_day:
            gdp_date = date(year, month, gdp_day)
            events.append(NewsEvent("GDP Advance", gdp_date, _event_time(gdp_date)))

    # 6. FOMC — approx every 6 weeks, approximated as 8th Wed of
    #    Jan, Mar, May, Jun, Jul, Sep, Oct, Dec (typical 2024-2025 schedule)
    fomc_months = {1, 3, 5, 6, 7, 9, 10, 12}
    if month in fomc_months:
        # Typically the 3rd or 4th Wednesday; use the 2nd Wed of the 2nd full week
        fomc_day = _nth_weekday(year, month, calendar.WEDNESDAY, 2)
        # Push forward ~1 week to get closer to actual
        fomc_day = min(fomc_day + 7, 31)
        _, last = calendar.monthrange(year, month)
        fomc_day = min(fomc_day, last)
        fomc_date = date(year, month, fomc_day)
        events.append(NewsEvent("FOMC Decision", fomc_date, time(15, 0)))  # FOMC is at a fixed time

    # FOMC in winter
    for ev in events:
        if ev.name == "FOMC Decision":
            t = _summer_time() if _us_dst_active(ev.event_date) else time(16, 0)
            # rebuild with correct time (FOMC is 14:00 ET => 15:00/16:00 BRT)
            pass  # already set above; winter override below if needed

    return events


def _find_first_weekday_in_range(
    year: int, month: int, weekday: int, start: int, end: int
) -> int | None:
    for d in range(start, end + 1):
        if calendar.weekday(year, month, d) == weekday:
            return d
    return None


# ---------------------------------------------------------------------------
# Calendar persistence (data/news_calendar.json)
# ---------------------------------------------------------------------------
def _calendar_path(year: int, month: int) -> Path:
    return DATA_DIR / "news_calendar.json"


def _generate_and_save_calendar(year: int | None = None, month: int | None = None) -> list[dict]:
    """Generate the calendar for this month, save to JSON, return list of dicts."""
    if year is None or month is None:
        now = datetime.now(BRT_TZ)
        year = now.year
        month = now.month

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    events = _calculate_monthly_events(year, month)
    records = [
        {
            "name": e.name,
            "date": e.event_date.isoformat(),
            "time_brt": e.event_time_brt.strftime("%H:%M"),
        }
        for e in events
    ]
    path = _calendar_path(year, month)
    path.write_text(json.dumps(records, indent=2) + "\n")
    return records


def _load_or_refresh_calendar() -> list[NewsEvent]:
    """Load from JSON if it exists and is for the current month; else regenerate."""
    now = datetime.now(BRT_TZ)
    path = _calendar_path(now.year, now.month)

    if path.exists():
        try:
            records = json.loads(path.read_text())
            # Validate the file is for this month
            if records:
                rec_date = date.fromisoformat(records[0]["date"])
                if rec_date.year == now.year and rec_date.month == now.month:
                    return [
                        NewsEvent(
                            r["name"],
                            date.fromisoformat(r["date"]),
                            datetime.strptime(r["time_brt"], "%H:%M").time(),
                        )
                        for r in records
                    ]
        except (json.JSONDecodeError, KeyError, ValueError):
            pass  # fall through to regenerate

    records = _generate_and_save_calendar(now.year, now.month)
    return [
        NewsEvent(r["name"], date.fromisoformat(r["date"]), time.fromisoformat(r["time_brt"]))
        for r in records
    ]


# ---------------------------------------------------------------------------
# Public API — Schedule-based checks
# ---------------------------------------------------------------------------
def is_news_today() -> Tuple[bool, str]:
    """
    Check if today has any scheduled high-impact economic event.

    Returns:
        (has_news, details) — e.g. (True, "Non-Farm Payrolls at 09:30")
    """
    events = _load_or_refresh_calendar()
    today = datetime.now(BRT_TZ).date()

    todays_events = [e for e in events if e.event_date == today]
    if todays_events:
        details_list = [f"{e.name} at {e.event_time_brt.strftime('%H:%M')} BRT" for e in todays_events]
        return True, " | ".join(details_list)
    return False, "No scheduled high-impact events today"


def is_news_impacting() -> Tuple[bool, str]:
    """
    Check if we are within NEWS_WINDOW_MINUTES of any scheduled event today.

    Returns:
        (is_impacting, details)
    """
    events = _load_or_refresh_calendar()
    now_brt = datetime.now(BRT_TZ)
    today = now_brt.date()

    window = timedelta(minutes=NEWS_WINDOW_MINUTES)
    impacting: list[str] = []

    for e in events:
        if e.event_date != today:
            continue
        event_dt = datetime.combine(e.event_date, e.event_time_brt, tzinfo=BRT_TZ)
        if abs(now_brt - event_dt) <= window:
            diff = int((event_dt - now_brt).total_seconds() / 60)
            if diff > 0:
                impacting.append(f"{e.name} in {diff}min")
            else:
                impacting.append(f"{e.name} ended {-diff}min ago")

    if impacting:
        return True, " | ".join(impacting)
    return False, "No scheduled news within window"


# ---------------------------------------------------------------------------
# Public API — Volatility-based check (yfinance)
# ---------------------------------------------------------------------------
def check_volatility() -> Tuple[bool, str]:
    """
    Use yfinance to detect abnormal price action on ES (S&P 500 futures).

    If the last 2 candles have a range (high-low) > 3x the 20-period average
    ATR, flag as unusual volatility.

    Returns:
        (is_volatile, details)
    """
    try:
        import yfinance as yf
    except ImportError:
        return False, "yfinance not installed — skipping volatility check"

    try:
        ticker = yf.Ticker("ES=F")
        # Fetch enough data to compute a 20-period ATR
        df = ticker.history(period="5d", interval="5m")
        if df is None or len(df) < 22:
            return False, "Insufficient data for ATR calculation"

        high = df["High"].values
        low = df["Low"].values
        close = df["Close"].values

        # Compute True Range
        tr = [high[0] - low[0]]  # first period
        for i in range(1, len(high)):
            tr_high = max(high[i], close[i - 1])
            tr_low = min(low[i], close[i - 1])
            tr.append(tr_high - tr_low)

        # 20-period ATR (simple average for simplicity)
        if len(tr) < 20:
            atr_20 = sum(tr) / len(tr)
        else:
            atr_20 = sum(tr[-20:]) / 20

        # Check last 2 candles
        last_trs = tr[-2:]
        threshold = 3.0 * atr_20
        flagged = [i + 1 for i, t in enumerate(last_trs) if t > threshold]

        if flagged:
            ratios = [f"candle-{i}: {tr[-len(last_trs) + i - 1] / atr_20:.1f}x ATR" for i in flagged]
            return True, f"High volatility detected — {', '.join(ratios)} (threshold: 3.0x)"

        latest_ratio = last_trs[-1] / atr_20 if atr_20 > 0 else 0
        return False, f"Normal volatility — latest candle {latest_ratio:.1f}x ATR (threshold: 3.0x)"

    except Exception as exc:
        return False, f"Volatility check failed: {exc}"


# ---------------------------------------------------------------------------
# Public API — Combined check
# ---------------------------------------------------------------------------
def should_pause() -> Tuple[bool, str]:
    """
    Combined check: pause if ANY of the following are true:
      1. A scheduled high-impact event is today and we are within the window.
      2. Market volatility is abnormally high (yfinance proxy).

    Returns:
        (pause, reason)
    """
    reasons: list[str] = []

    news_today, news_detail = is_news_today()
    news_impacting, impact_detail = is_news_impacting()
    vol_high, vol_detail = check_volatility()

    if news_today and news_impacting:
        reasons.append(f"SCHEDULED NEWS: {impact_detail}")
    elif news_today:
        reasons.append(f"SCHEDULED NEWS TODAY (not yet in window): {news_detail}")

    if vol_high:
        reasons.append(f"VOLATILITY: {vol_detail}")

    if reasons:
        return True, " | ".join(reasons)
    return False, "No pause conditions met"


# ---------------------------------------------------------------------------
# CLI entry point for quick testing
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== News Filter Diagnostic ===\n")
    pause, reason = should_pause()
    print(f"Should pause trading? {pause}")
    print(f"Reason: {reason}")
