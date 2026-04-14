"""
main.py — FastAPI application entry point for the Wissen Seat Booking System.

Start the server with:
    uvicorn main:app --reload --port 8000
"""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from database import create_db_and_tables, get_session
from models import Employee, Group, Seat, SeatType, Squad
from routers import auth as auth_router
from routers import schedule as schedule_router
from routers import bookings as bookings_router
from routers import leaves as leaves_router
from routers import admin as admin_router

# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup (idempotent — safe to run on every boot)."""
    create_db_and_tables()
    yield


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Wissen Seat Booking System",
    description=(
        "Hybrid-work seat booking for 80 employees across 10 squads.\n\n"
        "Manages **50 seats** (40 fixed + 10 floater) on a rolling 2-week rotation schedule.\n\n"
        "**Default credentials after seeding**\n"
        "- Employee: `emp.a1.01@wissen.com` / `password123`\n"
        "- Admin:    `admin@wissen.com` / `admin123`"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ── Middleware ─────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Tighten this to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────

app.include_router(auth_router.router)

# Phase 2+ routers will be added here:
app.include_router(schedule_router.router)
app.include_router(bookings_router.router)
app.include_router(leaves_router.router)
app.include_router(admin_router.router)


# ── Utility endpoints ─────────────────────────────────────────────────────────

@app.get("/api/health", tags=["System"], summary="Health check")
def health_check():
    """Returns OK — used by monitoring tools and to verify the server is up."""
    return {
        "status": "ok",
        "app": "Wissen Seat Booking System",
        "version": "1.0.0",
    }


@app.get("/api/status", tags=["System"], summary="Seed-data verification")
def db_status(session: Session = Depends(get_session)):
    """
    Returns entity counts — use this to verify the seed ran successfully.

    Expected after seeding:
      groups=2, squads=10, employees=81, seats=50, fixed_seats=40, floater_seats=10
    """
    all_employees = session.exec(select(Employee)).all()
    all_seats = session.exec(select(Seat)).all()
    all_groups = session.exec(select(Group)).all()
    all_squads = session.exec(select(Squad)).all()

    fixed = [s for s in all_seats if s.type == SeatType.FIXED]
    floater = [s for s in all_seats if s.type == SeatType.FLOATER]

    return {
        "groups": len(all_groups),
        "squads": len(all_squads),
        "employees": len(all_employees),
        "seats": len(all_seats),
        "fixed_seats": len(fixed),
        "floater_seats": len(floater),
    }
