"""Tables, parties and seating database models. A seating is a row; the current seating is a
column on tables. Turn time and the real wait are stamped once and never recomputed."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(80))


class DiningTable(Base):
    __tablename__ = "tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    no: Mapped[str] = mapped_column(String(8))
    seats: Mapped[int] = mapped_column(Integer)
    section: Mapped[str] = mapped_column(String(16))

    current_seating_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    cleared_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class Party(Base):
    __tablename__ = "parties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    name: Mapped[str] = mapped_column(String(60))
    covers: Mapped[int] = mapped_column(Integer)
    phone: Mapped[str | None] = mapped_column(String(16), nullable=True)
    state: Mapped[str] = mapped_column(String(12))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    position: Mapped[int] = mapped_column(Integer)

    quoted_minutes: Mapped[int] = mapped_column(Integer, default=40)
    quoted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Actual wait stamped when the party is seated.
    waited_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )


class Seating(Base):
    __tablename__ = "seatings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    party_id: Mapped[int] = mapped_column(
        ForeignKey("parties.id"),
        unique=True,
    )

    table_id: Mapped[int] = mapped_column(
        ForeignKey("tables.id"),
    )

    seated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )

    waited_minutes: Mapped[int] = mapped_column(Integer)

    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cleared_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    turn_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)     # seated_at → left_at


class Event(Base):
    """One row per transition, written in the same transaction as the change. Insert only: services/events.py
    writes it with a Core INSERT and this class is used for reads, so no code path updates a row; the database
    triggers in db.py refuse UPDATE and DELETE outright."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    party_id: Mapped[int] = mapped_column(ForeignKey("parties.id"))
    seating_id: Mapped[int | None] = mapped_column(ForeignKey("seatings.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(16))                      # joined | quoted | seated | left | cleared
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data: Mapped[str] = mapped_column(Text, default="{}")              # JSON: ids and facts, never the guest's phone