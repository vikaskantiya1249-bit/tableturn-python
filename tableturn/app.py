"""The application: settings read once, the schema created and seeded
before the first request, routers mounted,
one error handler, request ids on every request.
"""

import copy
import json
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi

from . import handlers
from .settings import Settings
from .db import make_engine, init_db, make_sessionmaker
from .services.seed import seed
from .routers import parties, seatings, tables, waitlist
from .routers import settings as settings_router


TAGS = [
    {"name": "tables", "description": "The floor — 22 tables and their derived state"},
    {"name": "waitlist", "description": "A party joins the list and is quoted a wait"},
    {"name": "seatings", "description": "Seat, leave, clear — the table turns"},
    {"name": "parties", "description": "One party and its append-only history"},
    {"name": "settings", "description": "The rules in force, and health"},
]

DESCRIPTION = "A restaurant waitlist: parties quoted a wait, seated by size, tables turning over all evening."


def honest_openapi(app: FastAPI):
    """Every endpoint declares its error responses: the spec lists what each operation can really answer.
    FastAPI's stock 422 (HTTPValidationError, application/json) is removed where there is no body to fail — a query
    parameter that fails is the 400 validation problem the router documents — and replaced by the app's own
    problem+json where there is one; every operation gains the one 500 the handler gives."""

    def openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title, version=app.version, description=app.description,
            routes=app.routes, tags=app.openapi_tags,
        )

        for ops in schema["paths"].values():
            for op in ops.values():
                answers = op.setdefault("responses", {})

                if "requestBody" in op:
                    answers["422"] = copy.deepcopy(handlers.VALIDATION_RESPONSE[422])
                else:
                    answers.pop("422", None)

                answers["500"] = copy.deepcopy(handlers.INTERNAL_RESPONSE[500])

        components = schema.get("components", {}).get("schemas", {})

        for name in ("HTTPValidationError", "ValidationError"):
            others = {k: v for k, v in components.items() if k != name}

            if f"#/components/schemas/{name}" not in json.dumps([schema["paths"], others]):
                components.pop(name, None)

        app.openapi_schema = schema
        return schema

    return openapi


def create_app(settings: Settings | None = None):

    if settings is None:
        settings = Settings()

    engine = make_engine(settings.database_url)
    session_factory = make_sessionmaker(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(engine)

        with session_factory() as session:
            seed(session, settings.seed_dir)

        yield

        engine.dispose()

    app = FastAPI(lifespan=lifespan, openapi_tags=TAGS, description=DESCRIPTION)

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.settings = settings

    @app.middleware("http")
    async def request_id_and_log(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex[:12]
        response = await call_next(request)
        return response

    for api_router in (
        tables.router,
        waitlist.router,
        seatings.router,
        parties.router,
        settings_router.router,
    ):
        app.include_router(api_router)

    handlers.install_handlers(app)

    app.openapi = honest_openapi(app)

    return app