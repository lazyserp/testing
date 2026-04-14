from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from database import get_session
from models import Employee, Group, Seat, Booking, BookingStatus, Holiday, Leave
from routers.auth import get_current_employee, require_admin
from schemas import DailyAllocation, DailyStatus, WeekSchedule, BookingDetail
from services.booking_service import (
    check_holiday,
    get_available_floater_seats,
    get_active_booking,
    has_released_fixed_seat,
    is_on_leave,
)
from services.schedule_service import (
    build_cycle_summary,
    get_cycle_week,
    get_office_batch,
    get_week_dates,
)

router = APIRouter(prefix="/api/schedule", tags=["Schedule"])


@router.get("/cycle-position", summary="Get cycle info for a date")
def get_cycle_position(d: Optional[date] = None):
    d = d or date.today()
    return {
        "date": d,
        "cycle_week": get_cycle_week(d),
        "cycle_summary": build_cycle_summary(d),
    }


@router.get("/week", response_model=WeekSchedule, summary="Get weekly schedule for authenticated employee")
def get_my_week_schedule(
    d: Optional[date] = None,
    current_user: Employee = Depends(get_current_employee),
    session: Session = Depends(get_session),
):
    d = d or date.today()
    week_dates = get_week_dates(d)

    group = session.get(Group, current_user.group_id)
    employee_batch = group.batch if group else None

    days = []
    for day in week_dates:
        holiday_name = check_holiday(session, day)
        is_holiday = holiday_name is not None
        batch_in = get_office_batch(day)
        is_office_day = bool(employee_batch and batch_in == employee_batch)

        is_leave = is_on_leave(session, current_user.id, day)
        fixed_seat_rel = has_released_fixed_seat(session, current_user.id, day)

        fixed_seat_schema = None
        if current_user.fixed_seat_id:
            fixed_seat_obj = session.get(Seat, current_user.fixed_seat_id)
            if fixed_seat_obj:
                fixed_seat_schema = {
                    "id": fixed_seat_obj.id,
                    "seat_number": fixed_seat_obj.seat_number,
                    "type": fixed_seat_obj.type,
                }

        # For performance, could optimize floater counting, but doing it here aligns with the requirement.
        avail_count = len(get_available_floater_seats(session, day))

        booked_floater_schema = None
        active_booking = get_active_booking(session, current_user.id, day)
        if active_booking:
            floater_seat_obj = session.get(Seat, active_booking.seat_id)
            if floater_seat_obj:
                booked_floater_schema = {
                    "id": floater_seat_obj.id,
                    "seat_number": floater_seat_obj.seat_number,
                    "type": floater_seat_obj.type,
                }

        days.append(
            DailyStatus(
                date=day,
                weekday=day.strftime("%A"),
                is_weekend=day.weekday() >= 5,
                is_holiday=is_holiday,
                holiday_name=holiday_name,
                cycle_week=get_cycle_week(day),
                batch_in_office=batch_in,
                is_office_day=is_office_day,
                is_on_leave=is_leave,
                fixed_seat=fixed_seat_schema,
                fixed_seat_released=fixed_seat_rel,
                booked_floater_seat=booked_floater_schema,
                available_floater_count=avail_count,
            )
        )

    return WeekSchedule(
        week_start=week_dates[0],
        cycle_week=get_cycle_week(week_dates[0]),
        days=days,
    )


@router.get("/day", response_model=DailyAllocation, summary="Get detailed day allocation (Admin)")
def get_daily_allocation(
    d: Optional[date] = None,
    current_admin: Employee = Depends(require_admin),
    session: Session = Depends(get_session),
):
    d = d or date.today()

    holiday_name = check_holiday(session, d)
    is_holiday = holiday_name is not None
    batch_in = get_office_batch(d)

    total_employees = 0
    fixed_seat_occupancy = []
    released_seats = []
    floater_bookings = []

    # Get available floaters early
    available_floaters = get_available_floater_seats(session, d)

    if not is_holiday and batch_in:
        group = session.exec(select(Group).where(Group.batch == batch_in)).first()
        if group:
            in_office_employees = session.exec(select(Employee).where(Employee.group_id == group.id)).all()
            total_employees = len(in_office_employees)

            # Determine leaves and releases
            leaves = session.exec(select(Leave).where(Leave.leave_date == d)).all()
            leave_emp_ids = {lv.employee_id for lv in leaves}
            
            releases = session.exec(
                select(Booking)
                .where(Booking.booking_date == d)
                .where(Booking.status == BookingStatus.RELEASED)
            ).all()
            released_emp_ids = {r.employee_id for r in releases}

            for emp in in_office_employees:
                if emp.fixed_seat_id:
                    seat = session.get(Seat, emp.fixed_seat_id)
                    if emp.id in leave_emp_ids or emp.id in released_emp_ids:
                        if seat:
                            released_seats.append(seat)
                    else:
                        if seat:
                            # Mock booking detail for implicit fixed seat occupancy
                            b_detail = BookingDetail(
                                id=0,
                                employee_id=emp.id,
                                seat_id=seat.id,
                                booking_date=d,
                                status=BookingStatus.CONFIRMED,
                                booked_at=date.today(), # Just a filler
                                seat_number=seat.seat_number,
                                employee_name=emp.name
                            )
                            fixed_seat_occupancy.append(b_detail)

    # Active explicit floater bookings
    bookings = session.exec(
        select(Booking)
        .where(Booking.booking_date == d)
        .where(Booking.status == BookingStatus.CONFIRMED)
    ).all()

    for b in bookings:
        seat = session.get(Seat, b.seat_id)
        emp = session.get(Employee, b.employee_id)
        b_detail = BookingDetail(
            id=b.id,
            employee_id=b.employee_id,
            seat_id=b.seat_id,
            booking_date=b.booking_date,
            status=b.status,
            booked_at=b.booked_at,
            seat_number=seat.seat_number if seat else None,
            employee_name=emp.name if emp else None,
        )
        floater_bookings.append(b_detail)

    return DailyAllocation(
        date=d,
        is_holiday=is_holiday,
        holiday_name=holiday_name,
        batch_in_office=batch_in,
        total_employees_in_office=total_employees,
        fixed_seat_occupancy=fixed_seat_occupancy,
        released_seats=released_seats,
        floater_bookings=floater_bookings,
        available_floaters=available_floaters,
    )
