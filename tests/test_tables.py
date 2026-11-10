"""22 tables loaded once, a floor filterable by section and state, state derived — never stored."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from tableturn.app import create_app
import tableturn.settings
from tests.conftest import join, make_settings, seat, seated


def test_seeding_is_idempotent_across_two_starts(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    seed_dir = "seed"

    monkeypatch.setattr(
        tableturn.settings,
        "Settings",
        lambda: SimpleNamespace(
            database_url=f"sqlite:///{db_path}",
            seed_dir=seed_dir,
        ),
    )

    # First application start
    app1 = create_app()

    with TestClient(app1) as client:
        response = client.get("/branches/Baner/tables")

        assert response.status_code == 200
        assert len(response.json()["tables"]) == 22

    # Second application start using the same database
    app2 = create_app()

    with TestClient(app2) as client:
        response = client.get("/branches/Baner/tables")

        assert response.status_code == 200
        assert len(response.json()["tables"]) == 22
        assert response.json()["free"] == 22


def test_section_filter_returns_only_that_section_and_its_free_count(client):
    seated(client, 4, "T11")                    # a Garden table
    seated(client, 2, "T01")                    # a Window table: must not change the Garden count

    body = client.get(
        "/branches/Baner/tables?section=Garden"
    ).json()

    assert len(body["tables"]) == 8
    assert body["free"] == 7, "free counts the filtered tables, not the whole floor"


def test_state_filter_shows_the_seated_table_with_party_and_minutes(client, clock):
    party = join(client, 4)
    s = seat(client, party["party_id"], "T11")

    assert s.status_code == 201, s.text

    clock.advance(minutes=42)

    body = client.get(
        "/branches/Baner/tables?state=seated"
    ).json()

    assert [t["no"] for t in body["tables"]] == ["T11"]

    assert body["tables"][0] == {
        "no": "T11",
        "seats": 4,
        "section": "Garden",
        "state": "seated",
        "party_id": party["party_id"],
        "seating_id": s.json()["seating_id"],
        "seated_minutes": 42,
    }

    assert body["free"] == 0

    unfiltered = client.get("/branches/Baner/tables").json()
    assert unfiltered["free"] == 21