"""One place for all application error responses."""

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
)


def problem(status: int, error_type: str, title: str, detail: str, extra=None):
    body = {
        "type": error_type,
        "title": title,
        "status": status,
        "detail": detail,
    }

    if extra:
        body.update(extra)

    return JSONResponse(
        status_code=status,
        content=body,
        media_type="application/problem+json",
    )


def register_error_handlers(app):

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

        elif exc.status_code == 405:
            status, error_type, title = METHOD_NOT_ALLOWED

        else:
            status = exc.status_code
            error_type = HTTP

            try:
                title = HTTPStatus(status).phrase
            except ValueError:
                title = "HTTP error"

        return problem(
            status,
            error_type,
            title,
            str(exc.detail),
        )