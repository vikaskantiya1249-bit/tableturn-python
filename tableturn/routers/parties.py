"""Party API routes."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import get_session

from ..errors import NoSuchParty, PartyTooBig
from ..handlers import VALIDATION_RESPONSE, responses
from ..models import Event, Party
from ..schemas import EventOut, JoinIn, JoinOut, PartyOut
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
    tags=["waitlist"],
    summary="A party joins the list and is quoted a wait",
    responses={
        201: {
            "description": "On the list",
            "headers": {"Location": {
                "schema": {"type": "string"},
                "description": "Where the party can be read: /parties/{party_id}",
            }},
        },
        **responses((PartyTooBig, "No table in Baner seats 9; the largest seats 6", {"max_covers": 6})),
        **VALIDATION_RESPONSE,
    },
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
    response_model_exclude_none=True,
    tags=["parties"],
    summary="One party: quote, real wait, table and every transition",
    responses=responses((NoSuchParty, "There is no party 'W999' on the Baner list")),
)
def get_party(
    party_id: str,
    session: SessionDep,
):
    party, seating, table = get_party_details(session, party_id)

    rows = session.scalars(
        select(Event)
        .where(Event.party_id == party.id)
        .order_by(Event.at, Event.id)
    ).all()

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
        events=[
            EventOut(at=as_utc(e.at), kind=e.kind, **json.loads(e.data))
            for e in rows
        ],
    )