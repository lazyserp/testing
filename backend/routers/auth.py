"""
routers/auth.py — Login and /me endpoints.

The `get_current_employee` dependency is exported so other routers can import it.
The `require_admin` dependency gates admin-only endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session, select

from database import get_session
from models import Employee, UserRole
from services.auth_service import create_access_token, decode_access_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ── Shared dependencies ────────────────────────────────────────────────────────

def get_current_employee(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> Employee:
    """Validate Bearer JWT and return the authenticated Employee."""
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if not payload:
        raise exc
    employee_id = payload.get("sub")
    if employee_id is None:
        raise exc
    employee = session.get(Employee, int(employee_id))
    if employee is None:
        raise exc
    return employee


def require_admin(
    current: Employee = Depends(get_current_employee),
) -> Employee:
    """Raises 403 if the authenticated user is not an ADMIN."""
    if current.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current


def _serialize_employee(emp: Employee) -> dict:
    return {
        "id": emp.id,
        "name": emp.name,
        "email": emp.email,
        "role": emp.role,
        "squad_id": emp.squad_id,
        "group_id": emp.group_id,
        "fixed_seat_id": emp.fixed_seat_id,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/login", summary="Login — returns a Bearer JWT token")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    """
    Authenticate with **email** (as `username`) and `password`.

    Returns an `access_token` to use in the `Authorization: Bearer <token>` header.
    """
    employee = session.exec(
        select(Employee).where(Employee.email == form_data.username)
    ).first()

    if not employee or not verify_password(form_data.password, employee.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(data={"sub": str(employee.id)})
    return {
        "access_token": token,
        "token_type": "bearer",
        "employee": _serialize_employee(employee),
    }


@router.get("/me", summary="Return the authenticated employee's profile")
def get_me(current: Employee = Depends(get_current_employee)):
    return _serialize_employee(current)
