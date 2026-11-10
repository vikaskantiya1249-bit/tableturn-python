"""Party API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy.orm import Session

from . import get_session

from ..models import Party
from ..schemas import JoinIn, JoinOut, PartyOut
from ..services.parties import join_party, get_party_details
from ..ids import encode_party_id
from ..clock import Clock, get_clock, as_utc


router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]
ClockDep = Annotated[Clock, Depends(get_clock)]


@router.post(
    "/waitlist",
    response_model=JoinOut,
    status_code=201,
)
def create_party(
    data: JoinIn,
    response: Response,
    request: Request,
    session: SessionDep,
    clock: ClockDep,
):
    party = join_party(
        session=session,
        name=data.name,
        covers=data.covers,
        phone=data.phone,
        clock=clock,
        default_quote_minutes=request.app.state.settings.default_quote_minutes,
    )

    party_id = encode_party_id(party.id)

    response.headers["Location"] = f"/parties/{party_id}"

    return JoinOut(
        party_id=party_id,
        name=party.name,
        covers=party.covers,
        position=party.position,
        joined_at=as_utc(party.joined_at),
        quoted_minutes=party.quoted_minutes,
        quoted_at=as_utc(party.quoted_at),
    )


@router.get(
    "/parties/{party_id}",
    response_model=PartyOut,
)
def get_party(
    party_id: str,
    session: SessionDep,
):
    party, seating, table = get_party_details(session, party_id)

    return PartyOut(
        party_id=encode_party_id(party.id),
        name=party.name,
        covers=party.covers,
        state=party.state,
        position=party.position,
        joined_at=as_utc(party.joined_at),
        quoted_minutes=party.quoted_minutes,
        quoted_at=as_utc(party.quoted_at),
        waited_minutes=party.waited_minutes,
        table=table.no if table is not None else None,
    )