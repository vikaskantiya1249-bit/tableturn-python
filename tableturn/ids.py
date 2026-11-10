"""Public IDs for parties and seatings."""

import re

_PREFIX = "W"
_PARTY = re.compile(r"^W(\d{3,})$")
_SEATING = re.compile(r"^S(\d{3,})$")


def encode_party_id(database_id: int) -> str:
    return f"{_PREFIX}{database_id:03d}"


def decode_party_id(public_id: str) -> int | None:
    match = _PARTY.match(public_id or "")
    return int(match.group(1)) if match else None


def party_public(database_id: int) -> str:
    return encode_party_id(database_id)


def seating_public(database_id: int) -> str:
    return f"S{database_id:03d}"


def seating_internal(public_id: str) -> int | None:
    match = _SEATING.match(public_id or "")
    return int(match.group(1)) if match else None