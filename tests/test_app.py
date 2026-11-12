"""The app as a whole: docs, honest OpenAPI, the 500 and the framework's errors."""

import json
import logging
import subprocess
import sys

from pathlib import Path

from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from tableturn.handlers import PROBLEM
from tableturn.routers import get_session

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "tableturn"

# Every operation, its tag, and exactly the problem answers it can give: status → the types behind it.
# 500 is on every operation (the one unexpected-error handler); 422 only where there is a body to fail; 400
# validation only where a query parameter can fail.
EXPECTED = {
    ("/branches/{branch}/tables", "get"): ("tables", {"400": {"/errors/validation"}, "404": {"/errors/no-such-branch"}}),
    ("/branches/{branch}/tables/{no}", "get"): ("tables", {"404": {"/errors/no-such-branch", "/errors/no-such-table"}}),
    ("/waitlist", "post"): ("waitlist", {"400": {"/errors/party-too-big"}, "422": {"/errors/validation"}}),
    ("/seatings", "post"): ("seatings", {"404": {"/errors/no-such-party", "/errors/no-such-table"},
                                         "409": {"/errors/table-too-small", "/errors/already-seated",
                                                 "/errors/table-not-cleared", "/errors/overtaking"},
                                         "422": {"/errors/validation"}}),
    ("/seatings/{seating_id}/leave", "post"): ("seatings", {"404": {"/errors/no-such-seating"}, "409": {"/errors/already-left"}}),
    ("/seatings/{seating_id}/clear", "post"): ("seatings", {"404": {"/errors/no-such-seating"},
                                                            "409": {"/errors/not-left-yet", "/errors/already-cleared"}}),
    ("/parties/{party_id}", "get"): ("parties", {"404": {"/errors/no-such-party"}}),
    ("/settings", "get"): ("settings", {}),
    ("/healthz", "get"): ("settings", {}),
}


def problem_examples(entry: dict) -> list[dict]:
    content = entry.get("content", {}).get(PROBLEM, {})
    return [content["example"]] if "example" in content else [v["value"] for v in content.get("examples", {}).values()]


def test_docs_render_and_every_operation_has_a_summary_and_its_tag(client):
    assert client.get("/docs").status_code == 200
    spec = client.get("/openapi.json").json()

    served = {(p, m) for p, ops in spec["paths"].items() for m in ops}
    assert served == set(EXPECTED)

    for (path, method), (tag, _) in EXPECTED.items():
        op = spec["paths"][path][method]
        assert op.get("summary"), f"{method.upper()} {path} has no summary"
        assert op["tags"] == [tag], f"{method.upper()} {path} is tagged {op['tags']}, not {tag}"


def test_every_refusal_is_documented_with_a_problem_example(client):
    spec = client.get("/openapi.json").json()
    seatings = spec["paths"]["/seatings"]["post"]["responses"]
    assert {"404", "409", "422"} <= set(seatings)

    examples = seatings["409"]["content"][PROBLEM]["examples"]
    assert {"/errors/table-too-small", "/errors/already-seated", "/errors/table-not-cleared"} <= set(examples)
    assert examples["/errors/table-too-small"]["value"]["status"] == 409
    assert {"/errors/no-such-party", "/errors/no-such-table"} <= set(seatings["404"]["content"][PROBLEM]["examples"])

    waitlist = spec["paths"]["/waitlist"]["post"]["responses"]
    assert waitlist["400"]["content"][PROBLEM]["example"]["type"] == "/errors/party-too-big"
    assert waitlist["422"]["content"][PROBLEM]["example"]["type"] == "/errors/validation"


def test_no_operation_documents_an_answer_it_cannot_send(client):
    """Honest OpenAPI: each operation documents exactly its reachable problem answers plus the one 500; FastAPI's
    stock HTTPValidationError is gone; every problem example has type, title, status and detail."""
    spec = client.get("/openapi.json").json()

    for (path, method), (_, want) in EXPECTED.items():
        answers = spec["paths"][path][method]["responses"]
        errors = {s: e for s, e in answers.items() if int(s) >= 400}
        documented = {s: {ex["type"] for ex in problem_examples(e)} for s, e in errors.items()}
        assert documented == {**want, "500": {"/errors/internal"}}, f"{method.upper()} {path}: {documented}"

        for status, entry in errors.items():
            assert list(entry["content"]) == [PROBLEM], f"{method.upper()} {path} {status}: {list(entry['content'])}"

            for ex in problem_examples(entry):
                assert {"type", "title", "status", "detail"} <= set(ex), ex
                assert ex["status"] == int(status), ex

    assert "HTTPValidationError" not in json.dumps(spec)
    assert "ValidationError" not in spec["components"]["schemas"]


def test_the_201_of_post_waitlist_documents_its_location_header(client):
    spec = client.get("/openapi.json").json()
    created = spec["paths"]["/waitlist"]["post"]["responses"]["201"]

    assert created["headers"]["Location"]["schema"] == {"type": "string"}
    assert "application/json" in created["content"], "the body schema is still documented beside the header"


def test_unexpected_exception_is_a_generic_problem_with_request_id(app, client, caplog):
    @app.get("/boom", include_in_schema=False)
    def boom():
        raise RuntimeError("secret detail")

    caplog.set_level(logging.ERROR)
    r = client.get("/boom")

    assert r.status_code == 500 and r.headers["content-type"].startswith(PROBLEM)
    body = r.json()

    assert body["type"] == "/errors/internal" and "secret detail" not in r.text and "Traceback" not in r.text
    assert set(body) == {"type", "title", "status", "detail", "request_id"}
    assert len(body["request_id"]) == 12

    assert any(body["request_id"] in rec.getMessage() and "/boom" in rec.getMessage() for rec in caplog.records), \
        "the request id and the path are logged"


def test_framework_errors_are_problem_json_too(client):
    """One handler produces every error body: a path the app does not serve and a method a path does not accept."""
    r = client.get("/nope")
    assert r.status_code == 404 and r.headers["content-type"].startswith(PROBLEM)
    assert r.json() == {"type": "/errors/not-found", "title": "No such resource", "status": 404,
                        "detail": "There is nothing at /nope"}

    r = client.delete("/branches/Baner/tables")
    assert r.status_code == 405 and r.headers["content-type"].startswith(PROBLEM)
    assert r.json()["type"] == "/errors/method-not-allowed" and r.json()["title"] == "Method not allowed"
    assert r.headers["allow"] == "GET", "the Allow header the framework sets is kept"


def test_health_reads_the_database_and_a_failure_is_the_one_500(app, client):
    statements = []
    event.listen(app.state.engine, "before_cursor_execute", lambda *a: statements.append(a[2]))

    assert client.get("/healthz").json() == {"status": "ok"}
    assert "SELECT 1" in statements, "health makes a round trip through the session"

    class Unreachable:
        def execute(self, *_):
            raise OperationalError("SELECT 1", {}, Exception("unable to open database file"))

    app.dependency_overrides[get_session] = lambda: Unreachable()
    r = client.get("/healthz")
    assert r.status_code == 500 and r.json()["type"] == "/errors/internal" and "unable to open" not in r.text


def test_services_and_rules_load_without_fastapi():
    """In a fresh interpreter, importing every service (and the modules they stand on) pulls in neither FastAPI nor
    Starlette — not even indirectly."""
    modules = [f"tableturn.services.{p.stem}" for p in sorted((PKG / "services").glob("*.py")) if p.stem != "__init__"]
    modules += ["tableturn.errors", "tableturn.settings", "tableturn.schemas", "tableturn.models", "tableturn.clock",
                "tableturn.ids", "tableturn.db"]

    code = ("import importlib, sys\n"
            f"for m in {modules!r}: importlib.import_module(m)\n"
            "bad = sorted(m for m in sys.modules if m.split('.')[0] in ('fastapi', 'starlette'))\n"
            "print(bad); sys.exit(1 if bad else 0)\n")

    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stdout + done.stderr


def test_one_router_per_resource():
    assert {p.stem for p in (PKG / "routers").glob("*.py")} >= {"tables", "waitlist", "seatings", "parties"}