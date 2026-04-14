import pytest
from datetime import date, datetime

from models import BatchType
from services.schedule_service import (
    get_cycle_week,
    get_office_batch,
    is_employee_office_day,
    get_week_dates,
    get_cycle_start,
    get_cycle_dates,
    is_booking_window_open,
)


def test_get_cycle_week():
    # 2026-04-13 is Monday, week 16 (even) -> cycle 2
    assert get_cycle_week(date(2026, 4, 13)) == 2
    # 2026-04-20 is Monday, week 17 (odd) -> cycle 1
    assert get_cycle_week(date(2026, 4, 20)) == 1


def test_get_office_batch():
    # 2026-04-13 (Monday, cycle 2) -> batch 2 in office
    assert get_office_batch(date(2026, 4, 13)) == BatchType.BATCH_2
    # 2026-04-16 (Thursday, cycle 2) -> batch 1 in office
    assert get_office_batch(date(2026, 4, 16)) == BatchType.BATCH_1
    
    # 2026-04-20 (Monday, cycle 1) -> batch 1 in office
    assert get_office_batch(date(2026, 4, 20)) == BatchType.BATCH_1
    # 2026-04-23 (Thursday, cycle 1) -> batch 2 in office
    assert get_office_batch(date(2026, 4, 23)) == BatchType.BATCH_2
    
    # 2026-04-18 (Saturday) -> None
    assert get_office_batch(date(2026, 4, 18)) is None


def test_is_employee_office_day():
    d = date(2026, 4, 13) # cycle 2 Monday -> batch 2
    assert is_employee_office_day(BatchType.BATCH_2, d) is True
    assert is_employee_office_day(BatchType.BATCH_1, d) is False


def test_get_week_dates():
    dates = get_week_dates(date(2026, 4, 15)) # Wednesday
    assert len(dates) == 5
    assert dates[0] == date(2026, 4, 13) # Monday
    assert dates[4] == date(2026, 4, 17) # Friday


def test_get_cycle_start():
    # 2026-04-20 (cycle 1 Monday) -> cycle start
    assert get_cycle_start(date(2026, 4, 20)) == date(2026, 4, 20)
    # 2026-04-22 (cycle 1 Wednesday) -> cycle start is 2026-04-20
    assert get_cycle_start(date(2026, 4, 22)) == date(2026, 4, 20)
    # 2026-04-13 (cycle 2 Monday) -> cycle start is previous Monday (2026-04-06, which is week 15 -> cycle 1)
    # let's verify. 2026-04-06 is week 15 -> cycle 1
    assert get_cycle_start(date(2026, 4, 13)) == date(2026, 4, 6)


def test_is_booking_window_open():
    today = date(2026, 4, 14)
    past = date(2026, 4, 13)
    future = date(2026, 4, 15)
    
    # Before 3 PM
    now_before_3 = datetime(2026, 4, 14, 14, 59, 59)
    assert is_booking_window_open(today, now=now_before_3) is True
    
    # After 3 PM
    now_after_3 = datetime(2026, 4, 14, 15, 0, 0)
    assert is_booking_window_open(today, now=now_after_3) is False
    
    # Past is always false
    assert is_booking_window_open(past, now=now_before_3) is False
    
    # Future is always true
    assert is_booking_window_open(future, now=now_after_3) is True
