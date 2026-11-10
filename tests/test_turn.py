"""Leave then clear — turn time is what the table earned, the clear is one transaction, both are idempotent by refusal."""
"""Tests for leaving and clearing a table."""

from sqlalchemy import select, text

from tableturn.models import DiningTable, Party, Seating
from tests.conftest import seated


def test_leave_then_clear_stamps_turn_and_frees_the_table(client, clock, db):
    s = seated(client, 6, "T20")
    clock.advance(minutes=83)
    r = client.post(f"/seatings/{s['seating_id']}/leave")

    assert r.status_code == 200, r.text
    assert r.json() == {
        "seating_id": s["seating_id"],
        "left_at": "2026-09-27T20:33:00Z",
    }
    assert client.get("/branches/Baner/tables/T20").json()["state"] == "uncleared"

    clock.advance(minutes=6)
    r = client.post(f"/seatings/{s['seating_id']}/clear")
    assert r.status_code == 200, r.text

    body = r.json()
    assert (
        body["table"] == "T20"
        and body["turn_minutes"] == 83
        and body["cleared_at"] == "2026-09-27T20:39:00Z"
    )
    assert client.get("/branches/Baner/tables/T20").json()["state"] == "free"

    with db() as db_s:
        table = db_s.scalar(select(DiningTable).where(DiningTable.no == "T20"))
        assert table.current_seating_id is None
        assert table.cleared_at is not None
        assert db_s.get(Seating, 1).turn_minutes == 83
        assert db_s.get(Party, 1).state == "cleared"


def test_a_failure_after_the_first_write_rolls_the_clear_back(client, clock, db):
    s = seated(client, 2, "T01")
    client.post(f"/seatings/{s['seating_id']}/leave")

    with db() as db_s:     # the database refuses the clear's last write - the party becoming 'cleared'
        db_s.execute(text(
            "CREATE TRIGGER fail_clear BEFORE UPDATE ON parties WHEN NEW.state = 'cleared' "
            "BEGIN SELECT RAISE(ABORT, 'injected failure'); END"))
        db_s.commit()

    r = client.post(f"/seatings/{s['seating_id']}/clear")
    assert r.status_code == 500

    with db() as db_s:
        seating = db_s.get(Seating, 1)
        table = db_s.scalar(select(DiningTable).where(DiningTable.no == "T01"))
        assert seating.cleared_at is None and seating.turn_minutes is None and table.current_seating_id == 1

    assert client.get("/branches/Baner/tables/T01").json()["state"] == "uncleared"


def test_leave_and_clear_are_idempotent_by_refusal(client):
    s = seated(client, 2, "T01")

    r = client.post(f"/seatings/{s['seating_id']}/clear")
    assert r.status_code == 409 and r.json()["type"] == "/errors/not-left-yet"

    assert client.post(f"/seatings/{s['seating_id']}/leave").status_code == 200
    r = client.post(f"/seatings/{s['seating_id']}/leave")
    assert r.status_code == 409 and r.json()["type"] == "/errors/already-left"

    assert client.post(f"/seatings/{s['seating_id']}/clear").status_code == 200
    r = client.post(f"/seatings/{s['seating_id']}/clear")
    assert r.status_code == 409 and r.json()["type"] == "/errors/already-cleared"


def test_unknown_seating_is_404(client):
    for action in ("leave", "clear"):
        r = client.post(f"/seatings/S999/{action}")
        assert r.status_code == 404 and r.json()["type"] == "/errors/no-such-seating"