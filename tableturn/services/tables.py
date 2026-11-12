"""Table and branch lookup services."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Branch, DiningTable
from ..errors import NoSuchBranch, NoSuchTable


def get_branch(session: Session, branch_code: str) -> Branch:
    branch = session.scalar(
        select(Branch).where(Branch.code == branch_code)
    )

    if branch is None:
        raise NoSuchBranch("No such branch")

    return branch


def get_tables(
    session: Session,
    branch: Branch,
) -> list[DiningTable]:
    return list(
        session.scalars(
            select(DiningTable)
            .where(DiningTable.branch_id == branch.id)
            .order_by(DiningTable.no)
        ).all()
    )


def get_table(
    session: Session,
    branch: Branch,
    table_no: str,
) -> DiningTable:
    table = session.scalar(
        select(DiningTable).where(
            DiningTable.branch_id == branch.id,
            DiningTable.no == table_no,
        )
    )

    if table is None:
        raise NoSuchTable("No such table")

    return table


def max_covers(session: Session, branch_id: int) -> int:
    return session.scalar(
        select(func.max(DiningTable.seats)).where(
            DiningTable.branch_id == branch_id
        )
    ) or 0