"""
booking_service.py — Concurrency-safe seat booking and release logic.

Design
──────
• Fixed seat assignments are IMPLICIT — no Booking record is required for a
  fixed-seat employee on their office day. The system infers the assignment.
• A RELEASED Booking record signals the employee will not use their seat that day,
  making it available as a floater for others.
• Floater bookings are EXPLICIT CONFIRMED Booking records.
• Per-(seat_id, date) asyncio.Lock prevents double-booking without Redis.
"""
import asyncio
from collections import defaultdict
from datetime import date, datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlmodel import Session, select

from models import (
    BatchType, Booking, BookingStatus, Employee,
    Group, Holiday, Leave, Seat, SeatType,
)
from services.schedule_service import get_office_batch, is_booking_window_open, is_employee_office_day


# ── Per-(seat_id, date) lock registry ─────────────────────────────────────────
_lock_registry: dict[tuple, asyncio.Lock] = defaultdict(asyncio.Lock)


def _get_lock(seat_id: int, d: date) -> asyncio.Lock:
    """Return (or create) the asyncio.Lock for a specific seat+date pair."""
    return _lock_registry[(seat_id, d.isoformat())]


# ── Query helpers (pure reads, no side effects) ───────────────────────────────

def check_holiday(session: Session, d: date) -> Optional[str]:
    """Return holiday name if `d` is a holiday, else None."""
    h = session.exec(select(Holiday).where(Holiday.holiday_date == d)).first()
    return h.name if h else None


def is_on_leave(session: Session, employee_id: int, d: date) -> bool:
    """Return True if the employee has a leave record for date `d`."""
    return (
        session.exec(
            select(Leave)
            .where(Leave.employee_id == employee_id)
            .where(Leave.leave_date == d)
        ).first()
        is not None
    )


def has_released_fixed_seat(session: Session, employee_id: int, d: date) -> bool:
    """Return True if the employee created a RELEASED record for date `d`."""
    return (
        session.exec(
            select(Booking)
            .where(Booking.employee_id == employee_id)
            .where(Booking.booking_date == d)
            .where(Booking.status == BookingStatus.RELEASED)
        ).first()
        is not None
    )


def get_active_booking(session: Session, employee_id: int, d: date) -> Optional[Booking]:
    """Return the employee's CONFIRMED floater booking for date `d`, if any."""
    return session.exec(
        select(Booking)
        .where(Booking.employee_id == employee_id)
        .where(Booking.booking_date == d)
        .where(Booking.status == BookingStatus.CONFIRMED)
    ).first()


def is_seat_confirmed(session: Session, seat_id: int, d: date) -> bool:
    """Return True if the seat has an active CONFIRMED booking on date `d`."""
    return (
        session.exec(
            select(Booking)
            .where(Booking.seat_id == seat_id)
            .where(Booking.booking_date == d)
            .where(Booking.status == BookingStatus.CONFIRMED)
        ).first()
        is not None
    )


def get_available_floater_seats(session: Session, d: date) -> List[Seat]:
    """
    Return all seats currently available as floaters for date `d`.

    Formula:
        available = (base F-seats) ∪ (on-leave fixed seats) ∪ (released fixed seats)
                    minus already CONFIRMED bookings

    Only seats from the IN-OFFICE batch contribute leave-converted seats.
    """
    # All CONFIRMED seat IDs for this day (cannot be re-booked)
    confirmed_ids: set[int] = {
        b.seat_id
        for b in session.exec(
            select(Booking)
            .where(Booking.booking_date == d)
            .where(Booking.status == BookingStatus.CONFIRMED)
        ).all()
    }

    seen_ids: set[int] = set(confirmed_ids)
    available: List[Seat] = []

    # 1. Base floater seats (F-01 … F-10)
    for seat in session.exec(select(Seat).where(Seat.type == SeatType.FLOATER)).all():
        if seat.id not in confirmed_ids:
            available.append(seat)
            seen_ids.add(seat.id)

    # 2. Leave-converted fixed seats
    #    Only employees from the IN-OFFICE batch on `d` can liberate fixed seats.
    office_batch = get_office_batch(d)
    if office_batch:
        in_office_group = session.exec(
            select(Group).where(Group.batch == office_batch)
        ).first()

        if in_office_group:
            leaves_today = session.exec(
                select(Leave).where(Leave.leave_date == d)
            ).all()
            leave_emp_ids = {lv.employee_id for lv in leaves_today}

            if leave_emp_ids:
                on_leave_employees = session.exec(
                    select(Employee)
                    .where(Employee.group_id == in_office_group.id)
                    .where(Employee.id.in_(leave_emp_ids))
                ).all()

                for emp in on_leave_employees:
                    if emp.fixed_seat_id and emp.fixed_seat_id not in seen_ids:
                        seat = session.get(Seat, emp.fixed_seat_id)
                        if seat:
                            available.append(seat)
                            seen_ids.add(emp.fixed_seat_id)

    # 3. Released fixed seats (employees who explicitly released before 3 PM)
    for rel in session.exec(
        select(Booking)
        .where(Booking.booking_date == d)
        .where(Booking.status == BookingStatus.RELEASED)
    ).all():
        if rel.seat_id not in seen_ids:
            seat = session.get(Seat, rel.seat_id)
            if seat:
                available.append(seat)
                seen_ids.add(rel.seat_id)

    return available


# ── Booking actions ───────────────────────────────────────────────────────────

async def book_floater_seat(
    session: Session,
    employee: Employee,
    seat_id: int,
    booking_date: date,
) -> Booking:
    """
    Book a floater seat for a given date.

    Validation order (fail-fast):
      1. Booking window open (before 3 PM)
      2. Not a public holiday
      3. Employee's designated office day
      4. Employee not on leave
      5. Employee has no other active booking this day
      6. Seat is available as a floater (advisory pre-lock check)
      7. Seat not taken (definitive post-lock check)
    """
    # 1. Booking window
    if not is_booking_window_open(booking_date):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Booking window closed — bookings must be made before 3:00 PM on the booking day.",
        )

    # 2. Holiday
    holiday_name = check_holiday(session, booking_date)
    if holiday_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{booking_date} is a public holiday ({holiday_name}). No bookings allowed.",
        )

    # 3. Leave
    if is_on_leave(session, employee.id, booking_date):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You are on leave on this date — booking not allowed.",
        )

    # 5. Duplicate booking
    if get_active_booking(session, employee.id, booking_date):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active booking for this date.",
        )

    # 6. Advisory availability check (before acquiring lock)
    available_ids = {s.id for s in get_available_floater_seats(session, booking_date)}
    if seat_id not in available_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That seat is not available as a floater on this date.",
        )

    # 7. Acquire lock → definitive check → insert
    async with _get_lock(seat_id, booking_date):
        if is_seat_confirmed(session, seat_id, booking_date):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Seat was just booked by another user. Please select a different seat.",
            )

        booking = Booking(
            employee_id=employee.id,
            seat_id=seat_id,
            booking_date=booking_date,
            status=BookingStatus.CONFIRMED,
        )
        session.add(booking)
        session.commit()
        session.refresh(booking)

    # Audit log (outside lock — failure here should not roll back the booking)
    from services.audit_service import log_action
    seat = session.get(Seat, seat_id)
    log_action(
        session,
        employee.id,
        "BOOK_FLOATER",
        f"Booked {seat.seat_number if seat else seat_id} on {booking_date} [Booking #{booking.id}]",
    )

    return booking


async def release_fixed_seat(
    session: Session,
    employee: Employee,
    booking_date: date,
) -> None:
    """
    Release the employee's fixed seat for a given date, making it a floater.

    Requires:
      - Employee has a fixed seat assigned
      - It is a designated office day for the employee
      - Employee is not on leave on this date
      - Seat has not already been released for this date
      - Before 3:00 PM cutoff
    """
    if not is_booking_window_open(booking_date):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Release window closed — must release your seat before 3:00 PM.",
        )

    if not employee.fixed_seat_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You do not have a fixed seat assigned.",
        )

    group = session.get(Group, employee.group_id)
    if not group or not is_employee_office_day(group.batch, booking_date):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{booking_date} is not a designated office day for your batch.",
        )

    if is_on_leave(session, employee.id, booking_date):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You are on leave on this date — your seat is already available as a floater.",
        )

    if has_released_fixed_seat(session, employee.id, booking_date):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already released your fixed seat for this date.",
        )

    async with _get_lock(employee.fixed_seat_id, booking_date):
        release_record = Booking(
            employee_id=employee.id,
            seat_id=employee.fixed_seat_id,
            booking_date=booking_date,
            status=BookingStatus.RELEASED,
            released_at=datetime.utcnow(),
        )
        session.add(release_record)
        session.commit()

    from services.audit_service import log_action
    seat = session.get(Seat, employee.fixed_seat_id)
    log_action(
        session,
        employee.id,
        "RELEASE_FIXED_SEAT",
        f"Released fixed seat {seat.seat_number if seat else employee.fixed_seat_id} on {booking_date}",
    )


async def cancel_floater_booking(
    session: Session,
    employee: Employee,
    booking_id: int,
) -> None:
    """
    Cancel an active CONFIRMED floater booking (only before 3:00 PM).
    """
    booking = session.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
    if booking.employee_id != employee.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This is not your booking.")
    if booking.status != BookingStatus.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Booking is not active (already released or cancelled).",
        )

    if not is_booking_window_open(booking.booking_date):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot cancel a booking after 3:00 PM on the booking day.",
        )

    async with _get_lock(booking.seat_id, booking.booking_date):
        booking.status = BookingStatus.RELEASED
        booking.released_at = datetime.utcnow()
        session.add(booking)
        session.commit()

    from services.audit_service import log_action
    seat = session.get(Seat, booking.seat_id)
    log_action(
        session,
        employee.id,
        "CANCEL_FLOATER_BOOKING",
        f"Cancelled booking #{booking_id} ({seat.seat_number if seat else booking.seat_id}) on {booking.booking_date}",
    )
