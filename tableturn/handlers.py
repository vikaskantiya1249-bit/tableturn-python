"""The one place errors become HTTP: every error body — domain refusals, validation, a path or method the app
does not serve, and the unexpected — is application/problem+json built by `problem`. Also the OpenAPI `responses`
entries the routers declare, so /docs shows how each endpoint can say no.
"""

import logging
from http import HTTPStatus

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .errors import (
    DomainError,
    VALIDATION_BODY,
    VALIDATION_QUERY,
    NOT_FOUND,
    METHOD_NOT_ALLOWED,
    HTTP,
    INTERNAL,
)

log = logging.getLogger("tableturn.errors")

PROBLEM = "application/problem+json"


def problem(status: int, error_type: str, title: str, detail: str, extra=None, headers=None, **more):
    body = {
        "type": error_type,
        "title": title,
        "status": status,
        "detail": detail,
    }

    if extra:
        body.update(extra)

    body.update(more)

    return JSONResponse(
        status_code=status,
        content=body,
        media_type=PROBLEM,
        headers=headers,
    )


def _example(status, type_, title, detail, request_id=None, extra=None) -> dict:
    example = {"type": type_, "title": title, "status": status, "detail": detail}
    if request_id:
        example["request_id"] = request_id
    if extra:
        example.update(extra)
    return example


def problem_entry(status, type_, title, detail, request_id=None, **extra) -> dict:
    """One OpenAPI response entry with a single problem+json example."""
    return {
        "description": title,
        "content": {PROBLEM: {"schema": {"type": "object"}, "example": _example(status, type_, title, detail, request_id, extra)}},
    }


def responses(*pairs) -> dict:
    """Build `responses=` entries from (ErrorClass, example text[, extra dict]) pairs.

    One refusal for a status gives one `example`; several give an `examples` set keyed by type."""
    grouped: dict[int, list] = {}

    for pair in pairs:
        cls, text = pair[0], pair[1]
        extra = pair[2] if len(pair) > 2 else {}
        grouped.setdefault(cls.status, []).append((cls, text, extra))

    result = {}

    for status, items in grouped.items():
        if len(items) == 1:
            cls, text, extra = items[0]
            result[status] = problem_entry(status, cls.type, cls.title, text, **extra)
        else:
            examples = {
                cls.type: {
                    "summary": cls.title,
                    "value": _example(status, cls.type, cls.title, text, None, extra),
                }
                for cls, text, extra in items
            }
            result[status] = {
                "description": " or ".join(cls.title for cls, _, _ in items),
                "content": {PROBLEM: {"schema": {"type": "object"}, "examples": examples}},
            }

    return result


# A body that fails validation (POST /waitlist, POST /seatings).
VALIDATION_RESPONSE = {VALIDATION_BODY[0]: problem_entry(
    *VALIDATION_BODY, "1 field(s) failed validation",
    errors=[{"field": "covers", "message": "Input should be greater than or equal to 1"}])}

# A query parameter outside its enum (GET /branches/{branch}/tables?section=Roof).
FILTER_RESPONSE = {VALIDATION_QUERY[0]: problem_entry(
    *VALIDATION_QUERY, "1 field(s) failed validation",
    errors=[{"field": "section", "message": "Input should be 'Window', 'Garden' or 'Indoor'"}])}

# The one unexpected-error answer every operation can give.
INTERNAL_RESPONSE = {INTERNAL[0]: problem_entry(*INTERNAL, "The request could not be completed", request_id="3f9c2a7b1d04")}


def install_handlers(app):

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError):
        return problem(
            exc.status,
            exc.type,
            exc.title,
            exc.detail,
            exc.extra,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        validation_errors = exc.errors()

        is_query_error = any(
            error["loc"][0] == "query"
            for error in validation_errors
            if error.get("loc")
        )

        if is_query_error:
            status, error_type, title = VALIDATION_QUERY
        else:
            status, error_type, title = VALIDATION_BODY

        errors = []

        for error in validation_errors:
            location = error.get("loc", ())
            field = location[-1] if location else "body"

            errors.append({
                "field": str(field),
                "message": error.get("msg", "Invalid value"),
            })

        return problem(
            status,
            error_type,
            title,
            "The request parameters or body are not valid.",
            {"errors": errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            status, error_type, title = NOT_FOUND
            detail = f"There is nothing at {request.url.path}"

        elif exc.status_code == 405:
            status, error_type, title = METHOD_NOT_ALLOWED
            detail = f"{request.method} is not allowed at {request.url.path}"

        else:
            status = exc.status_code
            error_type = HTTP
            detail = str(exc.detail)

            try:
                title = HTTPStatus(status).phrase
            except ValueError:
                title = "HTTP error"

        return problem(
            status,
            error_type,
            title,
            detail,
            headers=dict(exc.headers) if exc.headers else None,
        )

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "-")

        log.exception(
            "unhandled error path=%s request_id=%s",
            request.url.path,
            request_id,
        )

        status, type_, title = INTERNAL

        return problem(
            status,
            type_,
            title,
            "The request could not be completed",
            request_id=request_id,
        )