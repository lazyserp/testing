"""
seed.py — Populates the database with initial data.

Structure seeded:
  Groups   : Group A (BATCH_1), Group B (BATCH_2)
  Squads   : Squad A1–A5 (Group A), Squad B1–B5 (Group B)
  Seats    : S-01 to S-40 (FIXED), F-01 to F-10 (FLOATER)
  Employees: 8 per squad = 80 employees total
             Group A employees → unique fixed seats S-01 … S-40
             Group B employees → SAME fixed seats S-01 … S-40
             (Both batches never come in on the same day, so seats never double-conflict)
  Admin    : admin@wissen.com / admin123

Run with:  python seed.py
"""
import os
import sys

# Ensure backend package root is on the path
sys.path.insert(0, os.path.dirname(__file__))

from sqlmodel import Session, select

from database import create_db_and_tables, engine
from models import BatchType, Employee, Group, Leave, Seat, SeatType, Squad, UserRole
from services.auth_service import hash_password


def seed() -> None:
    create_db_and_tables()

    with Session(engine) as session:
        # ── Guard: skip if already seeded ─────────────────────────────────────
        if session.exec(select(Employee)).first():
            print("✅ Database already seeded — skipping.")
            return

        print("[SEED] Seeding database ...\n")

        # ── Groups ─────────────────────────────────────────────────────────────
        group_a = Group(name="Group A", batch=BatchType.BATCH_1)
        group_b = Group(name="Group B", batch=BatchType.BATCH_2)
        session.add_all([group_a, group_b])
        session.commit()
        session.refresh(group_a)
        session.refresh(group_b)
        print(f"  [OK] Groups    : {group_a.name} ({group_a.batch.value}), {group_b.name} ({group_b.batch.value})")

        # ── Squads ─────────────────────────────────────────────────────────────
        squads_a = [Squad(name=f"Squad A{i}", group_id=group_a.id) for i in range(1, 6)]
        squads_b = [Squad(name=f"Squad B{i}", group_id=group_b.id) for i in range(1, 6)]
        all_squads = squads_a + squads_b
        session.add_all(all_squads)
        session.commit()
        for s in all_squads:
            session.refresh(s)
        print(f"  [OK] Squads    : {len(all_squads)} (5 per group)")

        # ── Seats ──────────────────────────────────────────────────────────────
        fixed_seats = [
            Seat(seat_number=f"S-{i:02d}", type=SeatType.FIXED)
            for i in range(1, 41)
        ]
        floater_seats = [
            Seat(seat_number=f"F-{i:02d}", type=SeatType.FLOATER)
            for i in range(1, 11)
        ]
        all_seats = fixed_seats + floater_seats
        session.add_all(all_seats)
        session.commit()
        for s in all_seats:
            session.refresh(s)
        print(f"  [OK] Seats     : {len(fixed_seats)} fixed (S-01..S-40) + {len(floater_seats)} floater (F-01..F-10)")

        # ── Employees ──────────────────────────────────────────────────────────
        default_pwd = hash_password("password123")
        employees: list[Employee] = []

        # Group A — each member gets a unique fixed seat
        seat_idx = 0
        for sq_i, squad in enumerate(squads_a):
            for member_i in range(1, 9):
                employees.append(
                    Employee(
                        name=f"Emp A{sq_i + 1}-{member_i:02d}",
                        email=f"emp.a{sq_i + 1}.{member_i:02d}@wissen.com",
                        password_hash=default_pwd,
                        squad_id=squad.id,
                        group_id=group_a.id,
                        fixed_seat_id=fixed_seats[seat_idx].id,
                    )
                )
                seat_idx += 1

        # Group B — reuse the same 40 fixed seats (different days, no conflict)
        seat_idx = 0
        for sq_i, squad in enumerate(squads_b):
            for member_i in range(1, 9):
                employees.append(
                    Employee(
                        name=f"Emp B{sq_i + 1}-{member_i:02d}",
                        email=f"emp.b{sq_i + 1}.{member_i:02d}@wissen.com",
                        password_hash=default_pwd,
                        squad_id=squad.id,
                        group_id=group_b.id,
                        fixed_seat_id=fixed_seats[seat_idx].id,  # Shared seat
                    )
                )
                seat_idx += 1

        session.add_all(employees)
        session.commit()
        print(f"  [OK] Employees : {len(employees)} (8 per squad)")

        # ── Admin user ─────────────────────────────────────────────────────────
        admin = Employee(
            name="System Admin",
            email="admin@wissen.com",
            password_hash=hash_password("admin123"),
            squad_id=squads_a[0].id,   # Assigned to Squad A1 for FK validity
            group_id=group_a.id,
            role=UserRole.ADMIN,
            fixed_seat_id=None,        # Admin doesn't occupy a seat
        )
        session.add(admin)
        session.commit()
        print(f"  [OK] Admin     : admin@wissen.com / admin123")

        print("\n[DONE] Seeding complete!")
        print("   Total entities: 2 groups | 10 squads | 81 employees | 50 seats")
        print("\n   Sample credentials")
        print("   Employee : emp.a1.01@wissen.com / password123")
        print("   Admin    : admin@wissen.com     / admin123")


if __name__ == "__main__":
    seed()
