"""One parametrised table of every refusal, run with the clock overridden under each SMALL_PARTY_UPGRADE
setting — and only the rows tagged `upgrade` move when the setting changes."""
"""The rule table: every row, under every setting."""

import csv
import json
import re

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tableturn.app import create_app
from tableturn.clock import get_clock
from tests.conftest import make_settings

ROWS = list(csv.DictReader((Path(__file__).parent / "rules.csv").open(encoding="utf-8")))
SETTINGS = {"default": "when_nobody_larger_waits", "never": "never", "always": "always"}


def run_case(client, row):
    last_party = last_seating = None

    for step in filter(None, row["setup"].split(";")):
        verb, *args = step.split()

        if verb == "join":
            r = client.post("/waitlist", json={"name": "Party", "covers": int(args[0])})
            assert r.status_code == 201, r.text
            last_party = r.json()["party_id"]
        elif verb == "seat":
            r = client.post("/seatings", json={"party_id": last_party, "table": args[0]})
            assert r.status_code == 201, r.text
            last_seating = r.json()["seating_id"]
        elif verb == "leave":
            assert client.post(f"/seatings/{last_seating}/leave").status_code == 200

    verb, *args = row["action"].split()

    if verb == "join":
        return client.post("/waitlist", json={"name": "Party", "covers": int(args[0])})

    party, table = args if len(args) == 2 else (last_party, args[0])      # "seat W999 T20" names the party
    return client.post("/seatings", json={"party_id": party, "table": table})


@pytest.mark.parametrize("mode", list(SETTINGS))
@pytest.mark.parametrize("row", ROWS, ids=[r["case"] for r in ROWS])
def test_rule_table(tmp_path, clock, row, mode):
    app = create_app(make_settings(tmp_path, small_party_upgrade=SETTINGS[mode]))
    app.dependency_overrides[get_clock] = lambda: clock

    with TestClient(app) as client:
        r = run_case(client, row)

        assert r.status_code == int(row[f"status_{mode}"]), (row["case"], mode, r.text)
        expected_type = row[f"type_{mode}"]

        if expected_type:
            assert r.json()["type"] == expected_type

        if expected_type == "/errors/overtaking" and row["case"] == "two_at_four_top_four_waiting" and mode != "never":
            assert r.json()["must_seat_first"] == "W001", "the larger party that must go first is named"

        if expected_type == "/errors/overtaking" and mode == "never":
            assert "must_seat_first" not in r.json(), "under never nobody is named — the field is left out, not null"


def test_only_upgrade_rows_move_when_the_setting_changes():
    def outcome(r, mode):
        return (r[f"status_{mode}"], r[f"type_{mode}"])

    moved = {r["case"] for r in ROWS if len({outcome(r, m) for m in SETTINGS}) > 1}
    assert moved == {r["case"] for r in ROWS if r["tag"] == "upgrade"} and len(moved) == 2


def test_every_refusal_type_has_a_row():
    """Every refusal type appears in at least one row: validation, party-too-big, and the seating refusals
    table-too-small, already-seated, table-not-cleared, no-such-party and no-such-table — and the upgrade refusal."""
    types = {r[f"type_{m}"] for r in ROWS for m in SETTINGS}
    assert types >= {"/errors/table-too-small", "/errors/already-seated", "/errors/table-not-cleared", "/errors/no-such-party",
                     "/errors/no-such-table", "/errors/party-too-big", "/errors/validation", "/errors/overtaking"}


def test_settings_endpoint_shows_the_live_values(tmp_path, clock):
    app = create_app(make_settings(tmp_path, default_quote_minutes=30, small_party_upgrade="never"))

    with TestClient(app) as client:
        assert client.get("/settings").json() == {"default_quote_minutes": 30, "small_party_upgrade": "never", "max_covers": 6}


def test_the_rule_book_shows_the_rows_the_tests_run():
    """Wire: the Rule book renders the same rows. The frontend's copy (between the markers in app.js) equals
    tests/rules.csv row for row — case, tag, setup, action and the expected status and type under every setting."""
    src = (Path(__file__).resolve().parent.parent / "tableturn" / "static" / "app.js").read_text(encoding="utf-8")
    block = re.search(r"/\* rules\.csv >>> \*/\s*var RULES = (\[.*?\]);\s*/\* <<< rules\.csv \*/", src, re.DOTALL)
    assert block, "the RULES block is missing from app.js"

    shown = [{k: v for k, v in row.items() if k != "given"} for row in json.loads(block.group(1))]
    assert shown == ROWS