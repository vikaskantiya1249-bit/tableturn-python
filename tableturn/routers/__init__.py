"""One router per resource. Shared router dependencies."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..clock import Clock, get_clock
from ..settings import Settings


router = APIRouter()


def get_session(request: Request):
    session_factory = request.app.state.session_factory

    with session_factory() as session:
        yield session


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


SessionDep = Annotated[Session, Depends(get_session)]
ClockDep = Annotated[Clock, Depends(get_clock)]
SettingsDep = Annotated[Settings, Depends(get_settings)]