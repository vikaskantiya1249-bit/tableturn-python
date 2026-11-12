"""Party waitlist business rules. The join and the quote are written as events in the same transaction."""

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..models import Branch, Party, DiningTable, Seating
from ..errors import NoSuchBranch, PartyTooBig, NoSuchParty
from ..clock import Clock
from ..ids import decode_party_id
from . import events


def join_party(
    session: Session,
    name: str,
    covers: int,
    phone: str | None,
    clock: Clock,
    default_quote_minutes: int = 40,
    branch_code: str = "Baner",
) -> Party:

    branch = session.scalar(
        select(Branch).where(Branch.code == branch_code)
    )

    if branch is None:
        raise NoSuchBranch("No such branch")

    max_covers = session.scalar(
        select(func.max(DiningTable.seats)).where(
            DiningTable.branch_id == branch.id
        )
    ) or 0

    if covers > max_covers:
        raise PartyTooBig(
            "No table can seat this many people",
            max_covers=max_covers,
        )

    waiting_count = session.scalar(
        select(func.count()).select_from(Party).where(
            Party.branch_id == branch.id,
            Party.state == "waiting",
        )
    ) or 0

    now = clock.now()

    party = Party(
        branch_id=branch.id,
        name=name,
        covers=covers,
        phone=phone,
        state="waiting",
        joined_at=now,
        position=waiting_count + 1,
        quoted_minutes=default_quote_minutes,
        quoted_at=now,
    )

    session.add(party)
    session.flush()

    events.record(session, branch, party.id, "joined", now, {"covers": covers})
    events.record(session, branch, party.id, "quoted", now, {"quoted_minutes": party.quoted_minutes})

    session.commit()
    session.refresh(party)

    return party


def get_party_details(session: Session, public_id: str):
    """Get a party and its seating details."""

    party_id = decode_party_id(public_id)

    party = None

    if party_id is not None:
        party = session.get(Party, party_id)

    if party is None:
        raise NoSuchParty("No such party")

    seating = session.scalar(
        select(Seating).where(Seating.party_id == party.id)
    )

    table = None

    if seating is not None:
        table = session.get(DiningTable, seating.table_id)

    return party, seating, table