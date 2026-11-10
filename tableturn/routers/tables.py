"""Table and floor API routes."""

from datetime import datetime, timezone

from fastapi import APIRouter

from ..ids import party_public, seating_public
from ..models import Party, Seating
from ..schemas import FloorOut, TableOut, Section, TableState
from ..services import tables
from ..clock import Clock, as_utc
from . import ClockDep, SessionDep


router = APIRouter()


def get_table_state(session, table) -> TableState:
    if table.current_seating_id is None:
        return "free"

    seating = session.get(Seating, table.current_seating_id)

    if seating is not None and seating.left_at is not None:
        return "uncleared"

    return "seated"


def table_output(session, table, clock):
    state = get_table_state(session, table)

    if state == "free":
        return TableOut(
            no=table.no,
            seats=table.seats,
            section=table.section,
            state=state,
        )

    seating = session.get(Seating, table.current_seating_id)
    party = session.get(Party, seating.party_id)

    if state == "uncleared":
        return TableOut(
            no=table.no,
            seats=table.seats,
            section=table.section,
            state=state,
            party_id=party_public(party.id),
            seating_id=seating_public(seating.id),
        )

    seated_minutes = int(
        (as_utc(clock.now()) - as_utc(seating.seated_at)).total_seconds() // 60
    )

    return TableOut(
        no=table.no,
        seats=table.seats,
        section=table.section,
        state=state,
        party_id=party_public(party.id),
        seating_id=seating_public(seating.id),
        seated_minutes=seated_minutes,
    )


@router.get(
    "/branches/{branch}/tables",
    response_model=FloorOut,
    response_model_exclude_none=True,
)
def get_floor(
    branch: str,
    session: SessionDep,
    clock: ClockDep,
    section: Section | None = None,
    state: TableState | None = None,
):
    branch_obj = tables.get_branch(session, branch)

    all_tables = tables.get_tables(session, branch_obj)

    result = []

    for table in all_tables:
        body = table_output(session, table, clock)

        if section is not None and table.section != section:
            continue

        if state is not None and body.state != state:
            continue

        result.append(body)

    return FloorOut(
        branch=branch_obj.code,
        free=sum(1 for table in result if table.state == "free"),
        tables=result,
    )


@router.get(
    "/branches/{branch}/tables/{no}",
    response_model=TableOut,
    response_model_exclude_none=True,
)
def get_one_table(
    branch: str,
    no: str,
    session: SessionDep,
    clock: ClockDep,
):
    branch_obj = tables.get_branch(session, branch)
    table = tables.get_table(session, branch_obj, no)

    return table_output(session, table, clock)