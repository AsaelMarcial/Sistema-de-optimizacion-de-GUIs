from __future__ import annotations

from typing import Any

from app.exceptions.custom_mesagges import MESSAGES


class PipelineValidationError(Exception):
    """
    Unified Pipeline Validation Exception.
    Uses flat MappingProxyType definitions for crisp lookups.
    """

    __slots__ = ("error_key", "message", "status_code", "additional_information")

    def __init__(self, error_key: str, additional_information: Any = None) -> None:
        self.error_key = error_key
        self.message = MESSAGES.get(
            error_key, "An unexpected pipeline validation error occurred."
        )
        self.status_code = 400
        self.additional_information = additional_information
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        information = {
            "error_key": self.error_key,
            "message": self.message,
            "status_code": self.status_code,
        }
        if self.additional_information is not None:
            information["additional_information"] = self.additional_information
        return information
