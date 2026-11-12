"""Shared fixtures for TableTurn tests."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from tableturn.app import create_app
from tableturn.clock import FixedClock, get_clock
from tableturn.settings import Settings


def make_settings(tmp_path, **overrides):
    values = {
        "database_url": f"sqlite:///{tmp_path / 'test.db'}", "default_quote_minutes": 40,
        "small_party_upgrade": "when_nobody_larger_waits", "seed_dir": "seed"}
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def clock():
    return FixedClock(
        datetime(2026, 9, 27, 19, 10, tzinfo=timezone.utc)
    )


@pytest.fixture
def app(tmp_path):
    return create_app(make_settings(tmp_path))


@pytest.fixture
def client(app, clock):
    app.dependency_overrides[get_clock] = lambda: clock

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def db(app):
    yield app.state.session_factory


def join(client, covers=2, phone=None):
    body = {
        "name": "Rao",
        "covers": covers,
    }
    if phone is not None:
        body["phone"] = phone

    r = client.post("/waitlist", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def seat(client, party_id: str, table: str):
    return client.post(
        "/seatings",
        json={
            "party_id": party_id,
            "table": table,
        },
    )


def seated(client, covers: int = 6, table: str = "T20") -> dict:
    """join + seat, returning the seating body."""
    party = join(client, covers)
    r = seat(client, party["party_id"], table)
    assert r.status_code == 201, r.text
    return r.json()