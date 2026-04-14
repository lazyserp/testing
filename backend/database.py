"""
database.py — SQLite engine and session factory for the Wissen Seat Booking System.
"""
from typing import Generator

from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = "mysql+pymysql://root:12345678@localhost/wissen_db"

engine = create_engine(
    DATABASE_URL,
    echo=False,
)


def create_db_and_tables() -> None:
    """Create all SQLModel-defined tables (idempotent)."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a transactional DB session."""
    with Session(engine) as session:
        yield session
