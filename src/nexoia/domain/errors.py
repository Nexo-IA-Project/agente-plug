class DomainError(Exception):
    """Base exception for domain layer."""


class InvalidPhoneError(DomainError):
    pass


class InvalidIntentError(DomainError):
    pass


class TenantIsolationError(DomainError):
    """Raised when a query is attempted without account_id filter."""


class HandoffRequiredError(DomainError):
    """Agent cannot handle, must escalate to human."""


class CademiError(Exception):
    """Falha ao comunicar com a API da Cademi."""
