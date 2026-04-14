from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from database import get_session
from models import Booking, BookingStatus, Employee, Seat
from routers.auth import get_current_employee
from schemas import BookingCreate, BookingDetail, BookingRead, MessageResponse, SeatRead
from services.booking_service import (
    book_floater_seat,
    cancel_floater_booking,
    get_available_floater_seats,
    release_fixed_seat,
)

router = APIRouter(prefix="/api", tags=["Bookings"])


@router.get("/bookings", response_model=List[BookingDetail], summary="Get my active bookings")
def get_my_bookings(
    current_user: Employee = Depends(get_current_employee),
    session: Session = Depends(get_session),
):
    """Returns only active CONFIRMED floater bookings for the user."""
    bookings = session.exec(
        select(Booking)
        .where(Booking.employee_id == current_user.id)
        .where(Booking.status == BookingStatus.CONFIRMED)
    ).all()
    
    result = []
    for b in bookings:
        seat = session.get(Seat, b.seat_id)
        result.append(
            BookingDetail(
                id=b.id,
                employee_id=b.employee_id,
                seat_id=b.seat_id,
                booking_date=b.booking_date,
                status=b.status,
                booked_at=b.booked_at,
                released_at=b.released_at,
                seat_number=seat.seat_number if seat else None,
                employee_name=current_user.name
            )
        )
    return result


@router.post("/bookings", response_model=BookingRead, summary="Book a floater seat")
async def create_booking(
    req: BookingCreate,
    current_user: Employee = Depends(get_current_employee),
    session: Session = Depends(get_session),
):
    """
    Books a specific floater seat for a date.
    Strictly follows 3:00 PM cutoff, concurrency safe.
    """
    booking = await book_floater_seat(
        session=session,
        employee=current_user,
        seat_id=req.seat_id,
        booking_date=req.booking_date,
    )
    return booking


@router.delete("/bookings/{booking_id}", response_model=MessageResponse, summary="Cancel an active floater booking")
async def cancel_booking(
    booking_id: int,
    current_user: Employee = Depends(get_current_employee),
    session: Session = Depends(get_session),
):
    """Cancels a CONFIRMED floater booking. Must be done before 3 PM."""
    await cancel_floater_booking(session, current_user, booking_id)
    return MessageResponse(message="Booking cancelled successfully.")


@router.post("/bookings/release", response_model=MessageResponse, summary="Release your fixed seat")
async def release_seat(
    req: BookingCreate,  # Using this for just booking_date, seat_id can be ignored
    current_user: Employee = Depends(get_current_employee),
    session: Session = Depends(get_session),
):
    """
    Release your fixed seat for a specific date, making it a floater.
    """
    await release_fixed_seat(session, current_user, req.booking_date)
    return MessageResponse(message="Fixed seat released successfully.")


@router.get("/seats/available", response_model=List[SeatRead], summary="Get available floater seats")
def get_available_seats(
    d: date,
    current_user: Employee = Depends(get_current_employee),  # Just to require auth
    session: Session = Depends(get_session),
):
    """Returns a list of all currently available floater seats for the specified date."""
    seats = get_available_floater_seats(session, d)
    return seats
