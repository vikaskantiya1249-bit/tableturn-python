"""Tests for seating refusals and error response shapes."""

import ast
from pathlib import Path

import pytest

from tests.conftest import join, seat, seated


PKG = Path(__file__).resolve().parent.parent / "tableturn"

PROBLEM = "application/problem+json"


def test_table_too_small(client):
    """A party of six cannot fit at a four-seat table."""
    party = join(client, 6)

    r = seat(client, party["party_id"], "T11")

    assert r.status_code == 409, r.text
    assert r.json()["type"] == "/errors/table-too-small"


def test_already_seated(client):
    """An already seated party cannot be seated again."""
    party = join(client, 6)

    first = seat(client, party["party_id"], "T20")
    assert first.status_code == 201, first.text

    r = seat(client, party["party_id"], "T20")

    assert r.status_code == 409, r.text
    assert r.json()["type"] == "/errors/already-seated"


def test_an_occupied_table_is_refused_the_same_way(client):
    """A table occupied by another party cannot be reused."""
    seated(client, 2, "T01")
    party = join(client, 2)

    r = seat(client, party["party_id"], "T01")

    assert r.status_code == 409, r.text
    assert r.json()["type"] == "/errors/table-not-cleared"


def test_the_404s_and_the_order_of_checks(client):
    """The first failing business rule determines the response."""

    party = join(client, 2)

    r = seat(client, party["party_id"], "T99")
    assert r.status_code == 404
    assert r.json()["type"] == "/errors/no-such-table"

    r = seat(client, "W999", "T99")
    assert r.status_code == 404
    assert r.json()["type"] == "/errors/no-such-party"

    s = seated(client, 6, "T20")

    r = seat(client, s["party_id"], "T99")  # already seated AND no such table: the table is checked first
    assert r.status_code == 404
    assert r.json()["type"] == "/errors/no-such-table"

    r = seat(client, s["party_id"], "T01")  # already seated AND too small: already-seated wins
    assert r.status_code == 409
    assert r.json()["type"] == "/errors/already-seated"


def _too_small(client):
    return seat(client, join(client, 6)["party_id"], "T11"), set()


def _too_big(client):
    return client.post(
        "/waitlist",
        json={"name": "Big", "covers": 9},
    ), {"max_covers"}


@pytest.mark.parametrize(
    "make",
    [_too_small, _too_big],
    ids=["table-too-small", "party-too-big"],
)
def test_refusal_body_has_exactly_the_documented_shape(client, make):
    """Error responses contain exactly the documented fields."""

    r, named = make(client)

    assert r.status_code in (400, 409)
    assert r.headers["content-type"].startswith(PROBLEM)

    assert set(r.json()) == {
        "type",
        "title",
        "status",
        "detail",
    } | named

    assert r.json()["status"] == r.status_code
    assert "Traceback" not in r.text and 'File "' not in r.text


def test_routes_never_build_error_responses():
    """Routes must not construct error responses themselves."""

    for path in (PKG / "routers").glob("*.py"):
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)

        assert not any(
            isinstance(node, ast.Raise)
            for node in ast.walk(tree)
        ), f"{path.name} raises inside a route"

        names = (
            {
                node.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Name)
            }
            | {
                node.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Attribute)
            }
        )

        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }

        for banned in ("HTTPException", "JSONResponse"):
            assert banned not in names and banned not in imported, (
                f"{path.name} uses {banned}"
            )