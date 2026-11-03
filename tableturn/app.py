"""The application: settings read once, the schema created and seeded
before the first request, routers mounted, one error handler.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .settings import Settings
from .db import make_engine, init_db, make_sessionmaker
from .services.seed import seed
from .handlers import register_error_handlers
from .routers import router


def create_app():

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

    app = FastAPI(lifespan=lifespan)

    app.state.engine = engine
    app.state.session_factory = session_factory

    app.include_router(router)

    register_error_handlers(app)

    return app