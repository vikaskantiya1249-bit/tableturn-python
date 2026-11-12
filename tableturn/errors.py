"""Domain refusals and error types.

No FastAPI or Starlette imports.
Services raise domain errors.
"""


class DomainError(Exception):
    status: int = 400
    type: str = "/errors/domain"
    title: str = "Refused"

    def __init__(self, detail: str, **extra):
        super().__init__(detail)
        self.detail = detail
        self.extra = extra


class NoSuchBranch(DomainError):
    status = 404
    type = "/errors/no-such-branch"
    title = "No such branch"


class NoSuchTable(DomainError):
    status = 404
    type = "/errors/no-such-table"
    title = "No such table"


class NoSuchParty(DomainError):
    status = 404
    type = "/errors/no-such-party"
    title = "No such party"


class NoSuchSeating(DomainError):
    status = 404
    type = "/errors/no-such-seating"
    title = "No such seating"


class PartyTooBig(DomainError):
    status = 400
    type = "/errors/party-too-big"
    title = "No table here could seat that many"


class TableTooSmall(DomainError):
    status = 409
    type = "/errors/table-too-small"
    title = "Table too small"


class AlreadySeated(DomainError):
    status = 409
    type = "/errors/already-seated"
    title = "Already seated"


class TableNotCleared(DomainError):
    status = 409
    type = "/errors/table-not-cleared"
    title = "Table not cleared"


class Overtaking(DomainError):
    """A smaller party may not take a larger table ahead of a larger party the table would fit."""
    status = 409
    type = "/errors/overtaking"
    title = "A larger party waiting must be seated first"


class AlreadyLeft(DomainError):
    status = 409
    type = "/errors/already-left"
    title = "The party has already left"


class NotLeftYet(DomainError):
    status = 409
    type = "/errors/not-left-yet"
    title = "The party has not left yet"


class AlreadyCleared(DomainError):
    status = 409
    type = "/errors/already-cleared"
    title = "The table has already been cleared"


# Framework-generated errors: a body or filter that fails validation, a path or
# a method the app does not serve (every error is problem+json), and the one 500 for anything unexpected.

VALIDATION_BODY = (
    422,
    "/errors/validation",
    "The request body is not valid",
)

VALIDATION_QUERY = (
    400,
    "/errors/validation",
    "Invalid filter value",
)

INTERNAL = (
    500,
    "/errors/internal",
    "Something went wrong",
)

NOT_FOUND = (
    404,
    "/errors/not-found",
    "No such resource",
)

METHOD_NOT_ALLOWED = (
    405,
    "/errors/method-not-allowed",
    "Method not allowed",
)

HTTP = "/errors/http"