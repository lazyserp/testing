from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from database import get_session
from models import Employee, Leave, Holiday, Group, BatchType
from routers.auth import get_current_employee
from schemas import LeaveCreate, LeaveRead, MessageResponse
from services.audit_service import log_action
from services.schedule_service import is_booking_window_open, is_employee_office_day

router = APIRouter(prefix="/api/leaves", tags=["Leaves"])


@router.get("", response_model=List[LeaveRead], summary="Get my leaves")
def get_my_leaves(
    current_user: Employee = Depends(get_current_employee),
    session: Session = Depends(get_session),
):
    leaves = session.exec(
        select(Leave).where(Leave.employee_id == current_user.id)
    ).all()
    return leaves


@router.post("", response_model=LeaveRead, summary="Mark leave for a date")
def create_leave(
    req: LeaveCreate,
    current_user: Employee = Depends(get_current_employee),
    session: Session = Depends(get_session),
):
    """
    Marks the employee as being on leave for a specific date.
    This automatically frees up their fixed seat (if they have one) as a floater.
    Must be done before 3 PM on the day of the leave.
    """
    if not is_booking_window_open(req.leave_date):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Leave window closed — you must mark leave before 3:00 PM on the day.",
        )

    # Check if already on leave
    existing = session.exec(
        select(Leave)
        .where(Leave.employee_id == current_user.id)
        .where(Leave.leave_date == req.leave_date)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already marked on leave for this date.",
        )

    # Note: If they have an active CONFIRMED floater booking on this day, 
    # strictly speaking they should cancel it first or we cancel it automatically.
    # We will enforce they cancel it first.
    from models import Booking, BookingStatus
    active_booking = session.exec(
        select(Booking)
        .where(Booking.employee_id == current_user.id)
        .where(Booking.booking_date == req.leave_date)
        .where(Booking.status == BookingStatus.CONFIRMED)
    ).first()
    if active_booking:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please cancel your active floater booking for this date before marking leave.",
        )

    leave = Leave(
        employee_id=current_user.id,
        leave_date=req.leave_date,
        reason=req.reason
    )
    session.add(leave)
    session.commit()
    session.refresh(leave)

    log_action(session, current_user.id, "MARK_LEAVE", f"Marked leave for {req.leave_date}")
    return leave


@router.delete("/{leave_id}", response_model=MessageResponse, summary="Cancel a leave")
def cancel_leave(
    leave_id: int,
    current_user: Employee = Depends(get_current_employee),
    session: Session = Depends(get_session),
):
    """
    Cancels a leave entry before 3 PM.
    If the date has passed or is 3 PM+, it cannot be cancelled.
    """
    leave = session.get(Leave, leave_id)
    if not leave:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave not found.")
    if leave.employee_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This is not your leave record.")

    if not is_booking_window_open(leave.leave_date):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot cancel leave after 3:00 PM on the day.",
        )

    session.delete(leave)
    session.commit()

    log_action(session, current_user.id, "CANCEL_LEAVE", f"Cancelled leave for {leave.leave_date}")
    return MessageResponse(message="Leave cancelled successfully.")
