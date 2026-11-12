"""Seating API routes."""

from fastapi import APIRouter

from ..errors import (
    AlreadyCleared,
    AlreadyLeft,
    AlreadySeated,
    NoSuchParty,
    NoSuchSeating,
    NoSuchTable,
    NotLeftYet,
    Overtaking,
    TableNotCleared,
    TableTooSmall,
)
from ..handlers import VALIDATION_RESPONSE, responses
from ..ids import party_public, seating_public
from ..models import Party
from ..schemas import ClearOut, LeaveOut, SeatIn, SeatOut

from ..services import seatings
from ..services.seed import BRANCH
from ..services.tables import get_branch
from . import ClockDep, SessionDep
from .settings import SettingsDep


router = APIRouter(prefix="/seatings", tags=["seatings"])


@router.post(
    "",
    response_model=SeatOut,
    status_code=201,
    summary="Seat a waiting party at a table",
    responses={**responses(
        (TableTooSmall, "T11 seats 4; the party has 6 covers"),
        (AlreadySeated, "W031 is already seated (state seated)"),
        (TableNotCleared, "T12 has not been cleared since W030 left"),
        (Overtaking, "W029 (4) is waiting and fits T11; seat them first", {"must_seat_first": "W029"}),
        (NoSuchParty, "There is no party 'W999' on the Baner list"),
        (NoSuchTable, "There is no table 'T99' in branch Baner"),
    ), **VALIDATION_RESPONSE},
)
def seat(
    body: SeatIn,
    session: SessionDep,
    clock: ClockDep,
    settings: SettingsDep,
) -> SeatOut:

    branch = get_branch(session, BRANCH[0])

    seating = seatings.seat(
        session,
        branch,
        body.party_id,
        body.table,
        clock,
        settings,
    )

    party = session.get(Party, seating.party_id)

    return SeatOut(
        seating_id=seating_public(seating.id),
        party_id=party_public(seating.party_id),
        table=body.table,
        seated_at=seating.seated_at,
        waited_minutes=party.waited_minutes,
    )


@router.post(
    "/{seating_id}/leave",
    response_model=LeaveOut,
    summary="The party has left; the table is now uncleared",
    responses=responses(
        (AlreadyLeft, "S204 left at 21:20"),
        (NoSuchSeating, "There is no seating 'S999'"),
    ),
)
def leave(
    seating_id: str,
    session: SessionDep,
    clock: ClockDep,
) -> LeaveOut:

    seating = seatings.leave(
        session,
        get_branch(session, BRANCH[0]),
        seating_id,
        clock,
    )

    return LeaveOut(
        seating_id=seating_public(seating.id),
        left_at=seating.left_at,
    )


@router.post(
    "/{seating_id}/clear",
    response_model=ClearOut,
    summary="The server has cleared the table; turn time is stamped and the table is free",
    responses=responses(
        (NotLeftYet, "S204: the party has not left; clear comes after leave"),
        (AlreadyCleared, "S204 was cleared at 21:26"),
        (NoSuchSeating, "There is no seating 'S999'"),
    ),
)
def clear(
    seating_id: str,
    session: SessionDep,
    clock: ClockDep,
) -> ClearOut:

    seating, table = seatings.clear(
        session,
        get_branch(session, BRANCH[0]),
        seating_id,
        clock,
    )

    return ClearOut(
        seating_id=seating_public(seating.id),
        table=table.no,
        turn_minutes=seating.turn_minutes,
        cleared_at=seating.cleared_at,
    )