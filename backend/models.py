"""
models.py — SQLModel ORM models for the Wissen Seat Booking System.

Entity hierarchy:
    Group (2) → Squad (10) → Employee (80)
    Seat (50: 40 FIXED + 10 FLOATER)
    Booking  — floater bookings + released fixed-seat records
    Leave    — employee leave days
    Holiday  — organisation holidays
    AuditLog — immutable record of every action

Fixed-seat sharing:
    Both batches share the same 40 physical fixed seats. Because the batches
    NEVER come in on the same day, one Group-A employee and one Group-B employee
    can hold `fixed_seat_id` pointing to the same seat with no conflict.
"""
from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


# ── Enums ──────────────────────────────────────────────────────────────────────

class BatchType(str, Enum):
    BATCH_1 = "BATCH_1"
    BATCH_2 = "BATCH_2"


class SeatType(str, Enum):
    FIXED = "FIXED"
    FLOATER = "FLOATER"


class BookingStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    RELEASED = "RELEASED"


class UserRole(str, Enum):
    EMPLOYEE = "EMPLOYEE"
    ADMIN = "ADMIN"


# ── Tables ─────────────────────────────────────────────────────────────────────

class Group(SQLModel, table=True):
    """Represents Group A (BATCH_1) or Group B (BATCH_2)."""

    __tablename__ = "groups"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    batch: BatchType

    squads: List["Squad"] = Relationship(back_populates="group")
    employees: List["Employee"] = Relationship(back_populates="group")


class Squad(SQLModel, table=True):
    """One of 10 squads, each belonging to a group."""

    __tablename__ = "squads"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    group_id: int = Field(foreign_key="groups.id")

    group: Optional[Group] = Relationship(back_populates="squads")
    employees: List["Employee"] = Relationship(back_populates="squad")


class Seat(SQLModel, table=True):
    """A physical seat. Type is FIXED or FLOATER."""

    __tablename__ = "seats"

    id: Optional[int] = Field(default=None, primary_key=True)
    seat_number: str = Field(unique=True, index=True)        # e.g. S-01, F-01
    type: SeatType

    bookings: List["Booking"] = Relationship(back_populates="seat")
    assigned_employees: List["Employee"] = Relationship(back_populates="fixed_seat")


class Employee(SQLModel, table=True):
    """An employee with squad/group membership and an optional fixed seat."""

    __tablename__ = "employees"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str = Field(unique=True, index=True)
    password_hash: str
    role: UserRole = Field(default=UserRole.EMPLOYEE)
    squad_id: int = Field(foreign_key="squads.id")
    group_id: int = Field(foreign_key="groups.id")
    # Fixed seat: may be shared with one employee from the other batch
    fixed_seat_id: Optional[int] = Field(default=None, foreign_key="seats.id")

    squad: Optional[Squad] = Relationship(back_populates="employees")
    group: Optional[Group] = Relationship(back_populates="employees")
    fixed_seat: Optional[Seat] = Relationship(back_populates="assigned_employees")
    bookings: List["Booking"] = Relationship(back_populates="employee")
    leaves: List["Leave"] = Relationship(back_populates="employee")
    audit_logs: List["AuditLog"] = Relationship(back_populates="employee")


class Booking(SQLModel, table=True):
    """
    Tracks manual floater bookings and released fixed-seat events.
    A CONFIRMED booking means the seat is occupied.
    A RELEASED booking means the employee released their fixed seat early
    (it then becomes a floater for that day).
    """

    __tablename__ = "bookings"

    id: Optional[int] = Field(default=None, primary_key=True)
    employee_id: int = Field(foreign_key="employees.id", index=True)
    seat_id: int = Field(foreign_key="seats.id", index=True)
    booking_date: date = Field(index=True)          # Using booking_date to avoid SQLite keyword clash
    status: BookingStatus = Field(default=BookingStatus.CONFIRMED)
    booked_at: datetime = Field(default_factory=datetime.utcnow)
    released_at: Optional[datetime] = Field(default=None)

    employee: Optional[Employee] = Relationship(back_populates="bookings")
    seat: Optional[Seat] = Relationship(back_populates="bookings")


class Leave(SQLModel, table=True):
    """Records an employee's leave for a specific date."""

    __tablename__ = "leaves"

    id: Optional[int] = Field(default=None, primary_key=True)
    employee_id: int = Field(foreign_key="employees.id", index=True)
    leave_date: date = Field(index=True)
    reason: Optional[str] = Field(default=None)

    employee: Optional[Employee] = Relationship(back_populates="leaves")


class Holiday(SQLModel, table=True):
    """Organisation-wide public holidays. No bookings allowed on these days."""

    __tablename__ = "holidays"

    id: Optional[int] = Field(default=None, primary_key=True)
    holiday_date: date = Field(unique=True, index=True)
    name: str


class AuditLog(SQLModel, table=True):
    """Immutable record of every booking/release/leave action."""

    __tablename__ = "audit_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    employee_id: Optional[int] = Field(default=None, foreign_key="employees.id", index=True)
    action: str          # e.g. BOOK_FLOATER, RELEASE_SEAT, MARK_LEAVE, ADD_HOLIDAY
    details: Optional[str] = Field(default=None)   # JSON or plain text
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)

    employee: Optional[Employee] = Relationship(back_populates="audit_logs")
