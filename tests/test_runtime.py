"""Rows checked here: the guest's number never reaches a log line and log lines carry public ids,
settings really do come from an env-file, and the image recipe, the env-file example, the README and the How it runs
screen match what the container does. (The docker build/run proofs themselves are recorded in the README and in
TRACEABILITY.md.)"""
"""Runtime: logs, env-file settings, the Dockerfile and the README."""

import logging
import re

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tableturn.app import create_app
from tableturn.clock import get_clock
from tableturn.settings import Settings
from tests.conftest import ROOT, join, seat


def test_no_log_line_ever_contains_the_phone(client, caplog):
    caplog.set_level(logging.INFO)
    party = join(client, 6, phone="+919876543210")
    seat(client, party["party_id"], "T20")
    seat(client, party["party_id"], "T20")     # the refusal path logs too
    client.get(f"/parties/{party['party_id']}")

    lines = [r.getMessage() for r in caplog.records]
    assert lines, "requests and events are logged"
    assert any("event kind=joined" in line for line in lines) and any("request method=POST path=/waitlist" in line for line in lines)
    assert all("9876543210" not in line for line in lines)


def test_log_lines_carry_public_ids_never_database_integers(client, caplog):
    caplog.set_level(logging.INFO)
    party = join(client, 6)
    s = seat(client, party["party_id"], "T20").json()

    events = [r.getMessage() for r in caplog.records if r.name == "tableturn.events"]
    assert "event kind=joined party_id=W001 seating_id=- branch=Baner" in events
    assert f"event kind=seated party_id=W001 seating_id={s['seating_id']} branch=Baner" in events
    assert not any(re.search(r"(party_id|seating_id|branch_id)=\d", line) for line in events)


def test_settings_come_from_an_env_file(tmp_path, clock, caplog):
    env = tmp_path / ".env"
    db = (tmp_path / "env.db").as_posix()
    env.write_text(f"DATABASE_URL=sqlite:///{db}\nDEFAULT_QUOTE_MINUTES=30\nSMALL_PARTY_UPGRADE=never\n"
                   f"SEED_DIR={ROOT / 'seed'}\nHOST=127.0.0.1\nPORT=9090\n", encoding="utf-8")

    settings = Settings(_env_file=env)
    assert settings.default_quote_minutes == 30 and settings.small_party_upgrade == "never"
    assert settings.host == "127.0.0.1" and settings.port == 9090

    app = create_app(settings)                 # it re-configures the root logger for stdout, so listen on "tableturn"
    app.dependency_overrides[get_clock] = lambda: clock
    logging.getLogger("tableturn").addHandler(caplog.handler)

    try:
        with TestClient(app) as c:
            assert c.get("/settings").json()["default_quote_minutes"] == 30
            assert c.get("/branches/Baner/tables").json()["free"] == 22
    finally:
        logging.getLogger("tableturn").removeHandler(caplog.handler)

    assert Path(db).exists()
    assert any("ready host=127.0.0.1 port=9090" in r.getMessage() for r in caplog.records), "the settings object reads HOST and PORT"


def test_env_example_lists_every_setting_the_app_reads():
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    keys = {line.split("=", 1)[0] for line in example.splitlines() if line and not line.startswith("#")}
    assert keys == {name.upper() for name in Settings.model_fields}


def test_dockerfile_and_ignore_match_the_contract():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.12-slim" in dockerfile and "pip install --no-cache-dir -r requirements.lock" in dockerfile
    assert "HOST=0.0.0.0" in dockerfile and "PORT=8080" in dockerfile and 'VOLUME ["/data"]' in dockerfile

    assert 'CMD ["sh", "-c", "exec uvicorn tableturn.app:app --host \\"$HOST\\" --port \\"$PORT\\""]' in dockerfile
    assert "DATABASE_URL" not in dockerfile, "the database path comes from the env-file, not the image"

    ignore = set((ROOT / ".dockerignore").read_text(encoding="utf-8").split())
    assert ignore == {".git", ".venv", "venv", "**/__pycache__", "**/*.pyc", "**/.pytest_cache", ".ruff_cache", "tests",
                      "sandbox", "**/*.db", ".env", "build", "dist", "*.egg-info"}


def test_the_lock_pins_every_package():
    lock = [line for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")]
    assert lock and all(re.fullmatch(r"[a-z0-9-]+==[\w.]+", line) for line in lock), lock

    names = {line.split("==")[0] for line in lock}
    assert {"fastapi", "uvicorn", "sqlalchemy", "pydantic", "pydantic-settings", "starlette", "pydantic-core"} <= names


def test_readme_builds_runs_and_walks_one_party():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docker build -t tableturn ." in readme

    run = re.search(r"docker run [^\n]*-v [\w-]+:/data[^\n]*--env-file [^\n]*tableturn", readme)
    assert run, "docker run with the named volume on /data and the env-file"

    curls = re.findall(r"^curl [^\n]*", readme, re.MULTILINE)
    assert curls and all("http://localhost:8080/" in c for c in curls), "every curl names a full http:// URL"

    joined = "\n".join(curls)
    order = [joined.find(needle) for needle in ("/waitlist", "/parties/W001", "/seatings ", "/leave", "/clear")]
    assert -1 not in order and order == sorted(order), "join → quote → seat → leave → clear, in that order"