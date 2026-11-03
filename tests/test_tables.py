"""22 tables loaded once, a floor filterable by section and state, state derived — never stored."""
from types import SimpleNamespace

from fastapi.testclient import TestClient

from tableturn.app import create_app
import tableturn.settings


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