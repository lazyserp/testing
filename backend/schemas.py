"""
schemas.py — Pydantic request/response schemas (separate from SQLModel ORM models).
"""
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel

from models import BatchType, BookingStatus, SeatType, UserRole


# ── Auth ──────────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class EmployeeBasic(BaseModel):
    """Minimal employee info returned alongside a token."""
    id: int
    name: str
    email: str
    role: UserRole
    squad_id: int
    group_id: int
    fixed_seat_id: Optional[int] = None

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    employee: EmployeeBasic


# ── Group / Squad ─────────────────────────────────────────────────────────────

class GroupRead(BaseModel):
    id: int
    name: str
    batch: BatchType

    class Config:
        from_attributes = True


class SquadRead(BaseModel):
    id: int
    name: str
    group_id: int

    class Config:
        from_attributes = True


# ── Seat ──────────────────────────────────────────────────────────────────────

class SeatRead(BaseModel):
    id: int
    seat_number: str
    type: SeatType

    class Config:
        from_attributes = True


class SeatAssign(BaseModel):
    employee_id: int
    seat_id: int


# ── Employee ──────────────────────────────────────────────────────────────────

class EmployeeCreate(BaseModel):
    name: str
    email: str
    password: str
    squad_id: int
    group_id: int
    role: UserRole = UserRole.EMPLOYEE


class EmployeeRead(BaseModel):
    id: int
    name: str
    email: str
    role: UserRole
    squad_id: int
    group_id: int
    fixed_seat_id: Optional[int] = None

    class Config:
        from_attributes = True


class EmployeeDetail(EmployeeRead):
    """Employee with enriched squad/group/seat info for admin views."""
    squad_name: Optional[str] = None
    group_name: Optional[str] = None
    group_batch: Optional[BatchType] = None
    fixed_seat_number: Optional[str] = None


# ── Booking ───────────────────────────────────────────────────────────────────

class BookingCreate(BaseModel):
    seat_id: int
    booking_date: date


class BookingRead(BaseModel):
    id: int
    employee_id: int
    seat_id: int
    booking_date: date
    status: BookingStatus
    booked_at: datetime
    released_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BookingDetail(BookingRead):
    """Booking enriched with seat number and employee name."""
    seat_number: Optional[str] = None
    employee_name: Optional[str] = None


# ── Leave ─────────────────────────────────────────────────────────────────────

class LeaveCreate(BaseModel):
    leave_date: date
    reason: Optional[str] = None


class LeaveRead(BaseModel):
    id: int
    employee_id: int
    leave_date: date
    reason: Optional[str] = None

    class Config:
        from_attributes = True


# ── Holiday ───────────────────────────────────────────────────────────────────

class HolidayCreate(BaseModel):
    holiday_date: date
    name: str


class HolidayRead(BaseModel):
    id: int
    holiday_date: date
    name: str

    class Config:
        from_attributes = True


# ── Audit Log ─────────────────────────────────────────────────────────────────

class AuditLogRead(BaseModel):
    id: int
    employee_id: Optional[int] = None
    action: str
    details: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True


# ── Schedule ──────────────────────────────────────────────────────────────────

class DailyStatus(BaseModel):
    """Full status for one day from the perspective of one employee."""
    date: date
    weekday: str                                  # "Monday", etc.
    is_weekend: bool
    is_holiday: bool
    holiday_name: Optional[str] = None
    cycle_week: int                               # 1 or 2
    batch_in_office: Optional[BatchType] = None  # Which batch is in today
    is_office_day: bool                           # True if this employee's batch is in
    is_on_leave: bool
    fixed_seat: Optional[SeatRead] = None        # Employee's fixed seat (if in office)
    fixed_seat_released: bool = False            # Has the employee released their seat?
    booked_floater_seat: Optional[SeatRead] = None # Optional booked floater seat
    available_floater_count: int = 0


class WeekSchedule(BaseModel):
    week_start: date
    cycle_week: int
    days: List[DailyStatus]


class DailyAllocation(BaseModel):
    """Admin view: full seat allocation for a given day."""
    date: date
    is_holiday: bool
    holiday_name: Optional[str] = None
    batch_in_office: Optional[BatchType] = None
    total_employees_in_office: int
    fixed_seat_occupancy: List[BookingDetail]   # Confirmed fixed seats
    released_seats: List[SeatRead]              # Fixed seats freed up today
    floater_bookings: List[BookingDetail]       # Floater seat bookings
    available_floaters: List[SeatRead]          # Still-free floater seats


# ── Generic ───────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str


class DBStatus(BaseModel):
    groups: int
    squads: int
    employees: int
    seats: int
    fixed_seats: int
    floater_seats: int
