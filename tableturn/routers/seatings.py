"""Seating API routes."""

from fastapi import APIRouter

from ..ids import party_public, seating_public
from ..models import Party
from ..schemas import ClearOut, LeaveOut, SeatIn, SeatOut

from ..services import seatings
from ..services.seed import BRANCH
from ..services.tables import get_branch
from . import ClockDep, SessionDep


router = APIRouter(prefix="/seatings")


@router.post(
    "",
    response_model=SeatOut,
    status_code=201,
)
def seat(
    body: SeatIn,
    session: SessionDep,
    clock: ClockDep,
) -> SeatOut:

    branch = get_branch(session, BRANCH[0])

    seating = seatings.seat(
        session,
        branch,
        body.party_id,
        body.table,
        clock,
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