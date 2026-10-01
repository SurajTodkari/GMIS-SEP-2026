"""
MOD-001 — Developer 1
D1-004: AcquisitionJob Contract

AcquisitionJob is the standard job object consumed by acquisition
workers/runtime components.

Fields are aligned with the Developer 1 implementation specification:
    job_id
    source_id
    collector_type
    schedule_id
    attempt_no
    created_at
    scheduled_for
    trace_id
    config_version
    source_config_version

Scope:
    - Define the AcquisitionJob contract
    - Validate required identity, timing, attempt, tracing, and version fields

Out of scope:
    - Scheduler implementation
    - Worker implementation
    - Retry/backoff execution
    - Collector implementation
    - Runtime state management
    - Semantic normalization
    - Prediction/trading logic
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from mod001.contracts.source_config import CollectorType


class AcquisitionJobValidationError(ValueError):
    """Raised when an AcquisitionJob violates its contract."""


def _validate_non_blank_string(field_name: str, value: Any) -> None:
    """Validate a required string field."""
    if not isinstance(value, str):
        raise AcquisitionJobValidationError(
            f"{field_name} must be a string"
        )

    if not value.strip():
        raise AcquisitionJobValidationError(
            f"{field_name} must not be blank"
        )


def _parse_timestamp(field_name: str, value: Any) -> datetime:
    """
    Parse and validate a required timestamp.

    Accepted values:
        - datetime
        - ISO-8601 string

    The timestamp is normalized to timezone-aware UTC when a naive
    datetime/string is supplied. The contract only requires that
    timestamps be parseable; this normalization does not change the
    represented instant for timezone-aware values.
    """
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        if not value.strip():
            raise AcquisitionJobValidationError(
                f"{field_name} must not be blank"
            )

        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AcquisitionJobValidationError(
                f"{field_name} must be a parseable ISO-8601 timestamp"
            ) from exc
    else:
        raise AcquisitionJobValidationError(
            f"{field_name} must be a datetime or ISO-8601 string"
        )

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


def _validate_positive_integer(field_name: str, value: Any) -> None:
    """Validate an integer that must be >= 1."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise AcquisitionJobValidationError(
            f"{field_name} must be an integer"
        )

    if value < 1:
        raise AcquisitionJobValidationError(
            f"{field_name} must be >= 1"
        )


@dataclass(frozen=True)
class AcquisitionJob:
    """
    Standard acquisition job contract.

    This object carries the context required for an acquisition operation
    and provides explicit traceability to the source configuration version.
    """

    job_id: str
    source_id: str
    collector_type: CollectorType
    schedule_id: str
    attempt_no: int
    created_at: datetime | str
    scheduled_for: datetime | str
    trace_id: str
    config_version: int
    source_config_version: int

    def __post_init__(self) -> None:
        """Validate the AcquisitionJob contract."""

        _validate_non_blank_string("job_id", self.job_id)
        _validate_non_blank_string("source_id", self.source_id)
        _validate_non_blank_string("schedule_id", self.schedule_id)
        _validate_non_blank_string("trace_id", self.trace_id)

        if not isinstance(self.collector_type, CollectorType):
            raise AcquisitionJobValidationError(
                "collector_type must be one of: "
                "API, BROWSER, RSS, WEBSOCKET"
            )

        _validate_positive_integer("attempt_no", self.attempt_no)
        _validate_positive_integer("config_version", self.config_version)
        _validate_positive_integer(
            "source_config_version",
            self.source_config_version,
        )

        created_at = _parse_timestamp(
            "created_at",
            self.created_at,
        )
        scheduled_for = _parse_timestamp(
            "scheduled_for",
            self.scheduled_for,
        )

        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "scheduled_for", scheduled_for)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the contract."""
        return {
            "job_id": self.job_id,
            "source_id": self.source_id,
            "collector_type": self.collector_type.value,
            "schedule_id": self.schedule_id,
            "attempt_no": self.attempt_no,
            "created_at": self.created_at.isoformat(),
            "scheduled_for": self.scheduled_for.isoformat(),
            "trace_id": self.trace_id,
            "config_version": self.config_version,
            "source_config_version": self.source_config_version,
        }


__all__ = [
    "AcquisitionJob",
    "AcquisitionJobValidationError",
]
