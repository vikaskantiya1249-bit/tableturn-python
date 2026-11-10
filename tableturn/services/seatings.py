"""Seat a party, let it leave, clear the table. Every refusal is raised here, never in a route; every
change is one transaction."""
"""Seating business rules."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clock import Clock, as_utc, minutes_between
from ..errors import (
    AlreadyCleared,
    AlreadyLeft,
    AlreadySeated,
    NoSuchParty,
    NoSuchSeating,
    NotLeftYet,
    TableNotCleared,
    TableTooSmall,
)
from ..ids import decode_party_id, seating_internal
from ..models import Branch, DiningTable, Party, Seating
from .tables import get_table


def _seating(session: Session, branch: Branch, public_id: str) -> Seating:
    internal = seating_internal(public_id)
    seating = session.get(Seating, internal) if internal is not None else None

    if seating is not None:
        table = session.get(DiningTable, seating.table_id)
        if table is None or table.branch_id != branch.id:
            seating = None

    if seating is None:
        raise NoSuchSeating(f"There is no seating {public_id!r}.")

    return seating


def seat(
    session: Session,
    branch: Branch,
    party_public_id: str,
    table_no: str,
    clock: Clock,
) -> Seating:

    # 1. Party must exist.
    party_id = decode_party_id(party_public_id)

    party = None
    if party_id is not None:
        party = session.scalar(
            select(Party).where(
                Party.id == party_id,
                Party.branch_id == branch.id,
            )
        )

    if party is None:
        raise NoSuchParty("No such party")

    # 2. Table must exist.
    table = get_table(session, branch, table_no)

    # 3. Party must not already be seated.
    if party.state == "seated":
        raise AlreadySeated("Party is already seated")

    # 4. Table must be cleared and available.
    if table.current_seating_id is not None:
        raise TableNotCleared("Table has not been cleared")

    # 5. Table must fit the party.
    if table.seats < party.covers:
        raise TableTooSmall("Table cannot seat this party")

    # Stamp the actual wait at seating time.
    now = as_utc(clock.now())
    joined_at = as_utc(party.joined_at)

    waited_minutes = int(
        (now - joined_at).total_seconds() // 60
    )

    seating = Seating(
        party_id=party.id,
        table_id=table.id,
        seated_at=now,
        waited_minutes=waited_minutes,
    )

    session.add(seating)
    session.flush()

    table.current_seating_id = seating.id
    party.state = "seated"
    party.waited_minutes = waited_minutes

    session.commit()
    session.refresh(seating)

    return seating


def leave(
    session: Session,
    branch: Branch,
    seating_public_id: str,
    clock: Clock,
) -> Seating:
    seating = _seating(session, branch, seating_public_id)

    if seating.left_at is not None:
        raise AlreadyLeft(
            f"{seating_public_id} left at {seating.left_at:%H:%M}"
        )

    now = clock.now()
    seating.left_at = now

    party = session.get(Party, seating.party_id)
    party.state = "left"

    session.commit()
    return seating


def clear(
    session: Session,
    branch: Branch,
    seating_public_id: str,
    clock: Clock,
) -> tuple[Seating, DiningTable]:
    seating = _seating(session, branch, seating_public_id)

    if seating.left_at is None:
        raise NotLeftYet(
            f"{seating_public_id}: the party has not left; clear comes after leave"
        )

    if seating.cleared_at is not None:
        raise AlreadyCleared(
            f"{seating_public_id} was cleared at {seating.cleared_at:%H:%M}"
        )

    now = clock.now()
    table = session.get(DiningTable, seating.table_id)

    # One transaction — the seating, the table and the party.
    seating.cleared_at = now
    seating.turn_minutes = minutes_between(seating.seated_at, seating.left_at)   # what the table earned, not what the server took

    table.current_seating_id = None
    table.cleared_at = now

    party = session.get(Party, seating.party_id)
    party.state = "cleared"

    session.commit()
    return seating, table