from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from database import get_session
from models import AuditLog, Employee, Holiday, Squad, Group, Seat
from routers.auth import require_admin
from schemas import (
    AuditLogRead,
    EmployeeCreate,
    EmployeeDetail,
    HolidayCreate,
    HolidayRead,
    MessageResponse,
    SeatAssign,
)
from services.audit_service import log_action
from services.auth_service import hash_password

# Use require_admin dependency for ALL routes in this router
router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)


@router.get("/employees", response_model=List[EmployeeDetail], summary="Get all employees (enriched)")
def get_all_employees(session: Session = Depends(get_session)):
    employees = session.exec(select(Employee)).all()
    
    result = []
    for emp in employees:
        squad = session.get(Squad, emp.squad_id)
        group = session.get(Group, emp.group_id)
        seat = session.get(Seat, emp.fixed_seat_id) if emp.fixed_seat_id else None
        
        detail = EmployeeDetail.model_validate(emp)
        detail.squad_name = squad.name if squad else None
        detail.group_name = group.name if group else None
        detail.group_batch = group.batch if group else None
        detail.fixed_seat_number = seat.seat_number if seat else None
        
        result.append(detail)
    
    return result


@router.post("/employees", response_model=EmployeeDetail, summary="Create a new employee")
def create_employee(
    req: EmployeeCreate,
    current_admin: Employee = Depends(require_admin),
    session: Session = Depends(get_session)
):
    existing = session.exec(select(Employee).where(Employee.email == req.email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee with this email already exists."
        )
        
    squad = session.get(Squad, req.squad_id)
    if not squad:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Squad not found.")
        
    if squad.group_id != req.group_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Squad does not belong to the specified group."
        )
        
    emp = Employee(
        name=req.name,
        email=req.email,
        password_hash=hash_password(req.password),
        squad_id=req.squad_id,
        group_id=req.group_id,
        role=req.role,
    )
    session.add(emp)
    session.commit()
    session.refresh(emp)
    
    log_action(session, current_admin.id, "CREATE_EMPLOYEE", f"Created employee {emp.email}")
    
    # Reload for enriched model
    group = session.get(Group, emp.group_id)
    detail = EmployeeDetail.model_validate(emp)
    detail.squad_name = squad.name
    detail.group_name = group.name if group else None
    detail.group_batch = group.batch if group else None
    
    return detail


@router.get("/holidays", response_model=List[HolidayRead], summary="Get all holidays")
def get_holidays(session: Session = Depends(get_session)):
    return session.exec(select(Holiday).order_by(Holiday.holiday_date)).all()


@router.post("/holidays", response_model=HolidayRead, summary="Add a new public holiday")
def create_holiday(
    req: HolidayCreate,
    current_admin: Employee = Depends(require_admin),
    session: Session = Depends(get_session)
):
    existing = session.exec(select(Holiday).where(Holiday.holiday_date == req.holiday_date)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A holiday already exists on {req.holiday_date}."
        )
        
    holiday = Holiday(holiday_date=req.holiday_date, name=req.name)
    session.add(holiday)
    session.commit()
    session.refresh(holiday)
    
    log_action(session, current_admin.id, "ADD_HOLIDAY", f"Added holiday {holiday.name} on {holiday.holiday_date}")
    return holiday


@router.delete("/holidays/{holiday_id}", response_model=MessageResponse, summary="Remove a holiday")
def delete_holiday(
    holiday_id: int,
    current_admin: Employee = Depends(require_admin),
    session: Session = Depends(get_session)
):
    holiday = session.get(Holiday, holiday_id)
    if not holiday:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holiday not found.")
        
    session.delete(holiday)
    session.commit()
    
    log_action(session, current_admin.id, "REMOVE_HOLIDAY", f"Removed holiday {holiday.name} on {holiday.holiday_date}")
    return MessageResponse(message="Holiday removed successfully.")


@router.post("/seats/assign", response_model=MessageResponse, summary="Assign a fixed seat to an employee")
def assign_fixed_seat(
    req: SeatAssign,
    current_admin: Employee = Depends(require_admin),
    session: Session = Depends(get_session)
):
    emp = session.get(Employee, req.employee_id)
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")
        
    seat = session.get(Seat, req.seat_id)
    if not seat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seat not found.")
        
    if seat.type != "FIXED":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, 
            detail="Cannot assign a NON-FIXED seat to an employee."
        )
        
    # Check if seat is already assigned to someone in the SAME batch
    group = session.get(Group, emp.group_id)
    batch = group.batch if group else None
    
    if batch:
        conflicting_emps = session.exec(
            select(Employee).where(Employee.fixed_seat_id == seat.id)
        ).all()
        for c_emp in conflicting_emps:
            if c_emp.id != emp.id:
                c_group = session.get(Group, c_emp.group_id)
                c_batch = c_group.batch if c_group else None
                if c_batch == batch:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Seat is already assigned to {c_emp.name} in the same batch."
                    )
    
    old_seat_id = emp.fixed_seat_id
    emp.fixed_seat_id = seat.id
    session.add(emp)
    session.commit()
    
    log_action(
        session, 
        current_admin.id, 
        "ASSIGN_FIXED_SEAT", 
        f"Assigned seat {seat.seat_number} to employee {emp.name} (was {old_seat_id})"
    )
    
    return MessageResponse(message="Seat assigned successfully.")


@router.get("/audit-logs", response_model=List[AuditLogRead], summary="View system audit logs")
def get_audit_logs(
    limit: int = 100, 
    offset: int = 0,
    session: Session = Depends(get_session)
):
    logs = session.exec(
        select(AuditLog)
        .order_by(AuditLog.timestamp.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return logs
