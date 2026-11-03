import csv
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Branch, DiningTable


log = logging.getLogger("tableturn.seed")

BRANCH = ("Baner", "Kothari's, Baner")


def seed(session: Session, seed_dir: str) -> None:

    branch = session.scalar(
        select(Branch).where(Branch.code == BRANCH[0])
    )

    if branch is None:
        branch = Branch(
            code=BRANCH[0],
            name=BRANCH[1],
        )
        session.add(branch)
        session.flush()

    if session.scalar(
        select(DiningTable.id)
        .where(DiningTable.branch_id == branch.id)
        .limit(1)
    ) is None:

        with (Path(seed_dir) / "tables.csv").open(
            encoding="utf-8",
            newline="",
        ) as f:

            for row in csv.DictReader(f):
                session.add(
                    DiningTable(
                        branch_id=branch.id,
                        no=row["no"],
                        seats=int(row["seats"]),
                        section=row["section"],
                    )
                )

    session.commit()

    count = session.scalar(
        select(DiningTable.id)
        .where(DiningTable.branch_id == branch.id)
        .limit(1)
    )

    log.info(
        "seed complete branch=%s tables_present=%s",
        branch.code,
        count is not None,
    )