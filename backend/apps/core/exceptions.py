"""Domain exceptions surfaced via DRF as HTTP 400s."""
from rest_framework.exceptions import APIException


class DomainError(APIException):
    """Base for business-rule violations (insufficient stock, bad state, etc.)."""

    status_code = 400
    default_detail = "Operation could not be completed."
    default_code = "domain_error"


class InsufficientStock(DomainError):
    default_detail = "Insufficient stock to complete this operation."
    default_code = "insufficient_stock"
