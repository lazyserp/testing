import asyncio
from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient
from sqlmodel import Session, select
import pytest

# We import the app directly for testing
from main import app
from database import engine, get_session
from models import Employee, Holiday, Booking, BookingStatus, Seat, Leave

client = TestClient(app)

def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200

def get_auth_token(email: str, password: str = "password123"):
    response = client.post("/api/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]

def build_headers(token: str):
    return {"Authorization": f"Bearer {token}"}

def test_auth_and_profile():
    token = get_auth_token("emp.a1.01@wissen.com")
    headers = build_headers(token)
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "emp.a1.01@wissen.com"

# Edge Case Verifications
def test_holiday_override(monkeypatch):
    """Verify that a holiday blocks all bookings and releases for that day."""
    # First, let's create a holiday as an admin
    admin_token = get_auth_token("admin@wissen.com", "admin123")
    admin_headers = build_headers(admin_token)
    
    test_date = "2026-12-25" # A holiday in the future
    
    # Clean up existing to avoid conflicts during repeated tests
    with Session(engine) as session:
        h = session.exec(select(Holiday).where(Holiday.holiday_date == date(2026, 12, 25))).first()
        if h:
            session.delete(h)
            session.commit()

    res = client.post("/api/admin/holidays", json={"holiday_date": test_date, "name": "Christmas"}, headers=admin_headers)
    assert res.status_code == 200
    
    # Now try to book a seat on that holiday as a normal employee
    emp_token = get_auth_token("emp.a1.01@wissen.com")
    emp_headers = build_headers(emp_token)
    
    # We don't care if it's their batch or not, holiday overrides everything
    book_res = client.post("/api/bookings", json={"seat_id": 1, "booking_date": test_date}, headers=emp_headers)
    assert book_res.status_code == 422
    assert "public holiday" in book_res.json()["detail"]

def test_late_release_cutoff():
    """Verify releases are locked after 3:00 PM on the SAME day."""
    # We will mock the current time to 4:00 PM
    from services import booking_service, schedule_service
    
    from services.schedule_service import get_cycle_dates
    # Find a valid office date for Batch_1
    today_dt = datetime.now()
    valid_dates = [d for d in get_cycle_dates(today_dt.date()) if schedule_service.get_office_batch(d) == schedule_service.BatchType.BATCH_1]
    test_date = valid_dates[0]
    
    class MockDatetime:
        @classmethod
        def now(cls):
            # Mock the time to be 16:01 (4:01 PM) on the valid date
            return datetime.combine(test_date, datetime.min.time()).replace(hour=16, minute=1)
            
    schedule_service.datetime = MockDatetime
    
    emp_token = get_auth_token("emp.a1.01@wissen.com")
    emp_headers = build_headers(emp_token)
    
    res = client.post("/api/bookings/release", json={"seat_id": 0, "booking_date": test_date.strftime("%Y-%m-%d")}, headers=emp_headers)
    assert res.status_code == 422
    assert "must release your seat before 3:00 PM" in res.json()["detail"] or "Release window closed" in res.json()["detail"]

    # Restore module
    import datetime as real_dt
    schedule_service.datetime = real_dt

def test_audit_logs():
    admin_token = get_auth_token("admin@wissen.com", "admin123")
    admin_headers = build_headers(admin_token)
    
    res = client.get("/api/admin/audit-logs", headers=admin_headers)
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) > 0 # We created a holiday earlier, should be at least 1 log
    
    action_types = [log["action"] for log in logs]
    assert "ADD_HOLIDAY" in action_types
