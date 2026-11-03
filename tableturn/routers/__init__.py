"""API routers and database session dependency."""

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session

router = APIRouter()


def get_session(request: Request):
    session_factory = request.app.state.session_factory

    with session_factory() as session:
        yield session


from .tables import router as tables_router

router.include_router(tables_router)