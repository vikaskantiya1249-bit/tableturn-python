"""Domain refusals and the error types. No FastAPI or Starlette import: services raise domain errors."""


class DomainError(Exception):
    status: int = 400
    type: str = "/errors/domain"
    title: str = "Refused"

    def __init__(self, detail: str, **extra):
        super().__init__(detail)
        self.detail = detail
        self.extra = extra


class NoSuchBranch(DomainError):
    status, type, title = 404, "/errors/no-such-branch", "No such branch"


class NoSuchTable(DomainError):
    status, type, title = 404, "/errors/no-such-table", "No such table"


# (status, type, title) of the errors the framework raises rather than a service: 400 for a query parameter that fails validation
# ("filter values outside the enum are 400"), 404/405 for a path or
# a method the app does not serve (every error is problem+json).

VALIDATION_BODY = (422, "/errors/validation", "The request body is not valid")

VALIDATION_QUERY = (400, "/errors/validation", "Invalid filter value")

NOT_FOUND = (404, "/errors/not-found", "No such resource")

METHOD_NOT_ALLOWED = (405, "/errors/method-not-allowed", "Method not allowed")

HTTP = "/errors/http"