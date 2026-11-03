"""Tables. A dining table's state is derived from its
current seating; there is deliberately no `state`
column on tables."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
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

    seats: Mapped[int] = mapped_column(Integer)  # 2 | 4 | 6
    section: Mapped[str] = mapped_column(String(16))  # Window | Garden | Indoor
    current_seating_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)