"""Request and response models. Every response goes through one of these; bodies use Field constraints."""

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer


Section = Literal["Window", "Garden", "Indoor"]
TableState = Literal["free", "seated", "uncleared"]
PartyState = Literal["waiting", "seated", "left", "cleared"]
EventKind = Literal["joined", "quoted", "seated", "left", "cleared"]
Upgrade = Literal["never", "when_nobody_larger_waits", "always"]


def _iso_z(dt: datetime) -> str:
    """SQLite hands naive datetimes back; everything the app stores is UTC."""

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


UtcZ = Annotated[
    datetime,
    PlainSerializer(_iso_z, return_type=str),
]


# TABLE RESPONSE

class TableOut(BaseModel):
    no: str
    seats: int
    section: Section
    state: TableState
    party_id: str | None = None
    seating_id: str | None = None   # seated and uncleared tables: what the floor's Leave / Clear act on
    seated_minutes: int | None = None


class FloorOut(BaseModel):
    branch: str
    free: int
    tables: list[TableOut]


# PARTY REQUEST BODY

class JoinIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    covers: int = Field(ge=1, le=20)

    phone: str | None = Field(
        default=None,
        pattern=r"^\+[1-9]\d{7,14}$",
        description="E.164, optional",
    )


# JOIN RESPONSE

class JoinOut(BaseModel):
    party_id: str
    name: str
    covers: int
    position: int
    joined_at: UtcZ
    quoted_minutes: int
    quoted_at: UtcZ


class EventOut(BaseModel):
    """One timeline row. Every fact an event can carry is declared; each kind carries only its own."""

    model_config = ConfigDict(extra="forbid")

    at: UtcZ
    kind: EventKind
    covers: int | None = None            # joined
    quoted_minutes: int | None = None    # quoted
    table: str | None = None             # seated
    waited_minutes: int | None = None    # seated
    turn_minutes: int | None = None      # cleared


# PARTY DETAILS RESPONSE

class PartyOut(BaseModel):
    party_id: str
    name: str
    covers: int
    state: PartyState
    position: int
    joined_at: UtcZ
    quoted_minutes: int
    quoted_at: UtcZ
    waited_minutes: int | None = None
    table: str | None = None
    events: list[EventOut]


# SEATING REQUEST

class SeatIn(BaseModel):
    party_id: str
    table: str


# SEATING RESPONSE

class SeatOut(BaseModel):
    seating_id: str
    party_id: str
    table: str
    seated_at: UtcZ
    waited_minutes: int


class LeaveOut(BaseModel):
    seating_id: str
    left_at: UtcZ


class ClearOut(BaseModel):
    seating_id: str
    table: str
    turn_minutes: int
    cleared_at: UtcZ


class SettingsOut(BaseModel):
    default_quote_minutes: int
    small_party_upgrade: Upgrade
    max_covers: int


class HealthOut(BaseModel):
    status: Literal["ok"]