"""
audit_service.py — Write-only, fire-and-forget audit log helper.
All booking, release, and leave actions must call log_action().
"""
from typing import Optional

from sqlmodel import Session

from models import AuditLog


def log_action(
    session: Session,
    employee_id: Optional[int],
    action: str,
    details: Optional[str] = None,
) -> None:
    """
    Append an immutable audit log entry.

    Actions expected:
        BOOK_FLOATER, RELEASE_FIXED_SEAT, CANCEL_FLOATER_BOOKING,
        MARK_LEAVE, CANCEL_LEAVE, ADD_HOLIDAY, REMOVE_HOLIDAY,
        ASSIGN_FIXED_SEAT, CREATE_EMPLOYEE
    """
    entry = AuditLog(employee_id=employee_id, action=action, details=details)
    session.add(entry)
    session.commit()
