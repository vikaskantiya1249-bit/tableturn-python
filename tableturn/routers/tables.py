"""Table and floor API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import get_session
from ..models import Branch, DiningTable
from ..schemas import FloorOut, TableOut, Section, TableState
from ..errors import NoSuchBranch, NoSuchTable


router = APIRouter()


SessionDep = Annotated[Session, Depends(get_session)]


def get_table_state(table: DiningTable) -> TableState:
    """Derive table state from its current seating."""

    if table.current_seating_id is None:
        return "free"

    return "seated"


@router.get(
    "/branches/{branch}/tables",
    response_model=FloorOut,
    response_model_exclude_none=True,
)
def get_floor(
    branch: str,
    session: SessionDep,
    section: Section | None = None,
    state: TableState | None = None,
):
    branch_obj = session.scalar(
        select(Branch).where(Branch.code == branch)
    )

    if branch_obj is None:
        raise NoSuchBranch("No such branch")

    query = (
        select(DiningTable)
        .where(DiningTable.branch_id == branch_obj.id)
        .order_by(DiningTable.no)
    )

    if section is not None:
        query = query.where(DiningTable.section == section)

    tables = session.scalars(query).all()

    result = []

    for table in tables:
        table_state = get_table_state(table)

        if state is not None and table_state != state:
            continue

        result.append(
            TableOut(
                no=table.no,
                seats=table.seats,
                section=table.section,
                state=table_state,
            )
        )

    free_count = sum(
        1 for table in result if table.state == "free"
    )

    return FloorOut(
        branch=branch_obj.code,
        free=free_count,
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
):
    branch_obj = session.scalar(
        select(Branch).where(Branch.code == branch)
    )

    if branch_obj is None:
        raise NoSuchBranch("No such branch")

    table = session.scalar(
        select(DiningTable).where(
            DiningTable.branch_id == branch_obj.id,
            DiningTable.no == no,
        )
    )

    if table is None:
        raise NoSuchTable("No such table")

    return TableOut(
        no=table.no,
        seats=table.seats,
        section=table.section,
        state=get_table_state(table),
    )