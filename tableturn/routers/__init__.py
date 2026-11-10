"""Shared router dependencies."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..clock import Clock, get_clock


router = APIRouter()


def get_session(request: Request):
    session_factory = request.app.state.session_factory

    with session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
ClockDep = Annotated[Clock, Depends(get_clock)]