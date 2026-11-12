"""Every transition writes an event in the same transaction; events can never be updated or deleted."""
"""Tests for the append-only event log."""

import ast
from pathlib import Path
from unittest.mock import patch

import pytest

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import DBAPIError

from tableturn.models import Event, Seating
from tests.conftest import join, seat, seated


def test_join_writes_joined_and_quoted(client, db):
    join(client, 6)

    with db() as s:
        assert list(s.scalars(select(Event.kind).order_by(Event.id))) == ["joined", "quoted"]


def test_a_seating_writes_exactly_one_seated_event_with_table_and_wait(client, clock, db):
    party = join(client, 6)
    clock.advance(minutes=47)
    seat(client, party["party_id"], "T20")

    with db() as s:
        rows = s.scalars(select(Event).where(Event.kind == "seated")).all()
        assert (
            len(rows) == 1
            and rows[0].seating_id == 1
            and '"table": "T20"' in rows[0].data
            and '"waited_minutes": 47' in rows[0].data
        )


def test_a_failed_seating_leaves_no_event_and_no_seating(client, db):
    party = join(client, 6)

    with patch("tableturn.services.seatings.events.record", side_effect=RuntimeError("boom")):
        assert seat(client, party["party_id"], "T20").status_code == 500

    with db() as s:
        assert s.scalar(select(func.count()).select_from(Event).where(Event.kind == "seated")) == 0
        assert s.scalar(select(func.count()).select_from(Seating)) == 0

    assert client.get("/branches/Baner/tables/T20").json()["state"] == "free"


def test_events_are_append_only(client, db):
    join(client, 6)

    with db() as s, pytest.raises(DBAPIError):
        s.execute(update(Event).values(kind="edited"))
        s.commit()

    with db() as s, pytest.raises(DBAPIError):
        s.execute(delete(Event))
        s.commit()

    with db() as s, pytest.raises(DBAPIError):
        s.execute(text("DELETE FROM events WHERE id = 1"))
        s.commit()

    with db() as s:
        assert s.scalar(select(func.count()).select_from(Event)) == 2


def test_party_timeline_is_ordered_and_complete(client, clock):
    s = seated(client, 6, "T20")
    clock.advance(minutes=83)
    client.post(f"/seatings/{s['seating_id']}/leave")
    clock.advance(minutes=6)
    client.post(f"/seatings/{s['seating_id']}/clear")

    body = client.get(f"/parties/{s['party_id']}").json()
    events = body["events"]

    assert [e["kind"] for e in events] == ["joined", "quoted", "seated", "left", "cleared"]

    assert events[0]["covers"] == 6
    assert events[1]["quoted_minutes"] == 40
    assert events[2]["table"] == "T20" and events[2]["waited_minutes"] == 0 and events[4]["turn_minutes"] == 83
    assert [e["at"] for e in events] == sorted(e["at"] for e in events)


def test_no_event_carries_the_phone_number(client, db):
    party = join(client, 6, phone="+919876543210")
    seat(client, party["party_id"], "T20")

    with db() as s:
        assert all("9876543210" not in e.data for e in s.scalars(select(Event)))

    assert "9876543210" not in client.get(f"/parties/{party['party_id']}").text


def test_no_code_path_can_update_an_event():
    """Data: "a repository with no update method". The only writer is services/events.py, which inserts with a
    `Core INSERT`; no service ever builds an `Event` object that a flush could turn into an UPDATE."""
    services = Path(__file__).resolve().parent.parent / "tableturn" / "services"

    for path in services.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert "Event" not in calls, f"{path.name} builds an Event object"

    src = (services / "events.py").read_text(encoding="utf-8")
    assert "insert(Event)" in src and "session.add" not in src