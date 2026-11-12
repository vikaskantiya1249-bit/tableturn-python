"""Append one event row inside the caller's transaction. Ids and facts only — never the guest's phone.

The row is written with a Core INSERT and only its new id comes back: the ORM class `Event` is used for reads, so
there is no object here that could be changed and flushed as an UPDATE."""
"""Append one event row inside the caller's transaction. Ids and facts only — never the guest's phone.

The row is written with a Core INSERT and only its new id comes back: the ORM class `Event` is used for reads, so
there is no object here that could be changed and flushed as an UPDATE."""

import json
from datetime import datetime

from sqlalchemy import insert
from sqlalchemy.orm import Session

from ..models import Branch, Event


def record(session: Session, branch: Branch, party_id: int, kind: str, at: datetime,
           data: dict | None = None, seating_id: int | None = None) -> int:
    event_id = session.execute(
        insert(Event)
        .values(branch_id=branch.id, party_id=party_id, seating_id=seating_id, kind=kind, at=at, data=json.dumps(data or {}))
        .returning(Event.id)
    ).scalar_one()

    return event_id