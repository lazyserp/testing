"""
schedule_service.py — Deterministic 2-week cycle scheduling logic.

2-Week Cycle Definition
───────────────────────
  Week 1 (odd  ISO week number):  Mon/Tue/Wed → BATCH_1 | Thu/Fri → BATCH_2
  Week 2 (even ISO week number):  Mon/Tue/Wed → BATCH_2 | Thu/Fri → BATCH_1

This gives EACH squad exactly 5 office days per 2-week period:
  BATCH_1: Mon/Tue/Wed (Wk1) + Thu/Fri (Wk2) = 5 days ✓
  BATCH_2: Thu/Fri (Wk1) + Mon/Tue/Wed (Wk2) = 5 days ✓

ISO week numbers are deterministic year-round — no anchor-date config needed.
"""
from datetime import date, timedelta
from typing import List, Optional

from models import BatchType


# ── Core helpers ──────────────────────────────────────────────────────────────

def get_cycle_week(d: date) -> int:
    """Return 1 (odd ISO week) or 2 (even ISO week) for the given date."""
    _, iso_week, _ = d.isocalendar()
    return 1 if iso_week % 2 == 1 else 2


def get_office_batch(d: date) -> Optional[BatchType]:
    """
    Return the BatchType that should be in office on date `d`.
    Returns None for weekends.
    """
    weekday = d.weekday()   # Monday = 0 … Sunday = 6
    if weekday >= 5:
        return None         # Weekend — no one in office

    cycle_week = get_cycle_week(d)
    if cycle_week == 1:
        return BatchType.BATCH_1 if weekday <= 2 else BatchType.BATCH_2
    else:
        return BatchType.BATCH_2 if weekday <= 2 else BatchType.BATCH_1


def is_employee_office_day(employee_batch: BatchType, d: date) -> bool:
    """True if `employee_batch` is scheduled to be in office on `d`."""
    return get_office_batch(d) == employee_batch


# ── Week / cycle navigation ───────────────────────────────────────────────────

def get_week_dates(d: date) -> List[date]:
    """Return Mon–Fri dates of the ISO week containing `d`."""
    monday = d - timedelta(days=d.weekday())
    return [monday + timedelta(days=i) for i in range(5)]


def get_cycle_start(d: date) -> date:
    """
    Return the Monday that starts the 2-week cycle containing `d`.
    Cycle week 1 starts on this Monday; cycle week 2 starts 7 days later.
    """
    monday = d - timedelta(days=d.weekday())
    if get_cycle_week(d) == 1:
        return monday           # This Monday is the cycle start
    else:
        return monday - timedelta(weeks=1)   # Previous Monday


def get_cycle_dates(d: date) -> List[date]:
    """Return all Mon–Fri dates in the 2-week cycle containing `d`."""
    cycle_start = get_cycle_start(d)
    result = []
    for week_offset in range(2):
        for day_offset in range(5):          # Mon → Fri
            result.append(cycle_start + timedelta(weeks=week_offset, days=day_offset))
    return result


# ── Booking window ────────────────────────────────────────────────────────────

def is_booking_window_open(for_date: date, now: Optional[object] = None) -> bool:
    """
    Bookings and releases are allowed only BEFORE 15:00 (3 PM) on the SAME day.

    Rules:
      • Past dates          → always closed
      • Today before 15:00  → open
      • Today after  15:00  → closed
      • Future dates        → open (pre-booking allowed)

    Pass `now` (a datetime object) to override the current time (useful for tests).
    """
    from datetime import datetime

    current = now or datetime.now()
    today = current.date()

    if for_date < today:
        return False        # Cannot modify past bookings

    if for_date == today:
        return current.hour < 15   # Before 3 PM

    return True             # Future date — booking ahead is allowed


# ── Schedule summary ──────────────────────────────────────────────────────────

def build_cycle_summary(d: date) -> List[dict]:
    """
    Return a list of 10 dicts (Mon–Fri × 2 weeks) describing the full cycle.
    Each dict: {date, weekday, cycle_week, batch_in_office}
    """
    return [
        {
            "date": day,
            "weekday": day.strftime("%A"),
            "cycle_week": get_cycle_week(day),
            "batch_in_office": get_office_batch(day),
        }
        for day in get_cycle_dates(d)
    ]
