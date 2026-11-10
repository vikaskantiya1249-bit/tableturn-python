"""Tests for quoted wait times and the swappable clock."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from tableturn.app import create_app
from tableturn.clock import FixedClock, SystemClock, get_clock
from tests.conftest import join, make_settings, seat


def test_join_quotes_the_setting_at_the_fixed_clock(client):
    body = join(client, 6)

    assert (
        body["quoted_minutes"] == 40
        and body["quoted_at"] == "2026-09-27T19:10:00Z"
    )


def test_the_quote_is_the_setting(tmp_path, clock):
    app = create_app(
        make_settings(tmp_path, default_quote_minutes=30)
    )
    app.dependency_overrides[get_clock] = lambda: clock

    with TestClient(app) as c:
        assert join(c, 2)["quoted_minutes"] == 30


def test_the_clock_is_a_dependency_a_test_overrides(tmp_path):
    """Rule: the clock is Depends(get_clock), overridable in tests. Without an override the app reads the system
    clock; with `dependency_overrides[get_clock]` every stamp comes from the clock the test supplies."""

    assert isinstance(get_clock(), SystemClock)

    at = datetime(2031, 1, 2, 3, 4, tzinfo=timezone.utc)

    app = create_app(make_settings(tmp_path))
    app.dependency_overrides[get_clock] = lambda: FixedClock(at)

    with TestClient(app) as c:
        body = join(c, 2)

    assert body["joined_at"] == body["quoted_at"] == "2031-01-02T03:04:00Z"


def test_real_wait_is_stamped_at_seating_and_never_recomputed(client, clock):
    party = join(client, 6)
    clock.advance(minutes=47)

    r = seat(client, party["party_id"], "T20")

    assert r.status_code == 201 and r.json()["waited_minutes"] == 47

    body = client.get(f"/parties/{party['party_id']}").json()

    assert (
        body["state"] == "seated"
        and body["quoted_minutes"] == 40
        and body["waited_minutes"] == 47
        and body["table"] == "T20"
    )

    clock.advance(hours=3)
    assert client.get(f"/parties/{party['party_id']}").json()["waited_minutes"] == 47


def test_wait_is_rounded_down_to_whole_minutes(client, clock):
    party = join(client, 2)
    clock.advance(minutes=12, seconds=59)

    assert seat(client, party["party_id"], "T01").json()["waited_minutes"] == 12