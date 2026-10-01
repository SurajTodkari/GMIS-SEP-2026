"""
MOD-001 — Developer 1
D1-005: AcquisitionEnvelope Contract

AcquisitionEnvelope is the standard output handed from acquisition
toward the MOD-002 / raw-ingestion boundary.

Contract groups:
    Identity
    Source
    Timing
    Execution
    Payload
    Versioning
    Tracing
    Failure

Architecture boundary:
    External source / collector
            ↓
    AcquisitionEnvelope
            ↓
    MOD-002 / raw-ingestion boundary

This module defines and validates the contract only. It does not:
    - perform hashing
    - persist raw evidence
    - implement collectors
    - implement retries
    - perform semantic normalization
    - perform prediction or trading logic
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AcquisitionStatus(str, Enum):
    """Acquisition outcome statuses defined by MOD-001."""

    SUCCESS = "SUCCESS"
    RETRY = "RETRY"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"


class AcquisitionEnvelopeValidationError(ValueError):
    """Raised when an AcquisitionEnvelope violates its contract."""


def _validate_non_blank_string(field_name: str, value: Any) -> None:
    """Validate a required non-blank string field."""
    if not isinstance(value, str):
        raise AcquisitionEnvelopeValidationError(
            f"{field_name} must be a string"
        )

    if not value.strip():
        raise AcquisitionEnvelopeValidationError(
            f"{field_name} must not be blank"
        )


def _validate_optional_string(field_name: str, value: Any) -> None:
    """Validate an optional string field."""
    if value is None:
        return

    if not isinstance(value, str):
        raise AcquisitionEnvelopeValidationError(
            f"{field_name} must be a string or None"
        )


def _parse_timestamp(field_name: str, value: Any) -> Any:
    """
    Validate that a timestamp is parseable without replacing the original
    value.

    Source timestamps must be preserved exactly when supplied, so a
    supplied ISO-8601 string is retained as-is rather than rewritten.
    datetime values are also retained as supplied.

    Accepted values:
        - datetime
        - ISO-8601 string
        - None for optional timestamps
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        if not value.strip():
            raise AcquisitionEnvelopeValidationError(
                f"{field_name} must not be blank"
            )

        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AcquisitionEnvelopeValidationError(
                f"{field_name} must be a parseable ISO-8601 timestamp"
            ) from exc

        return value

    raise AcquisitionEnvelopeValidationError(
        f"{field_name} must be a datetime, ISO-8601 string, or None"
    )


def _validate_positive_integer(field_name: str, value: Any) -> None:
    """Validate a required integer that must be >= 1."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise AcquisitionEnvelopeValidationError(
            f"{field_name} must be an integer"
        )

    if value < 1:
        raise AcquisitionEnvelopeValidationError(
            f"{field_name} must be >= 1"
        )


def _validate_non_negative_integer(field_name: str, value: Any) -> None:
    """Validate an integer that must be >= 0."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise AcquisitionEnvelopeValidationError(
            f"{field_name} must be an integer"
        )

    if value < 0:
        raise AcquisitionEnvelopeValidationError(
            f"{field_name} must be >= 0"
        )


def _serialize_timestamp(value: Any) -> Any:
    """Serialize datetime values while preserving string representations."""
    if isinstance(value, datetime):
        return value.isoformat()

    return value


@dataclass(frozen=True)
class AcquisitionEnvelope:
    """
    Standard MOD-001 acquisition output contract.

    Raw payload is intentionally treated as opaque evidence. This object
    does not interpret, normalize, classify, or transform its contents.
    """

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    acquisition_id: str
    job_id: str
    source_id: str
    collector_type: str

    # ------------------------------------------------------------------
    # Source
    # ------------------------------------------------------------------
    source_message_id: str | None = None
    source_sequence: str | int | None = None
    source_timestamp: datetime | str | None = None

    # ------------------------------------------------------------------
    # Timing
    # ------------------------------------------------------------------
    published_at: datetime | str | None = None
    acquired_at: datetime | str | None = None
    completed_at: datetime | str | None = None
    effective_at: datetime | str | None = None

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    status: AcquisitionStatus = AcquisitionStatus.SUCCESS
    attempt_no: int = 1
    retry_count: int = 0

    # ------------------------------------------------------------------
    # Payload
    # ------------------------------------------------------------------
    content_type: str | None = None
    encoding: str | None = None
    raw_payload: Any = None
    payload_hash: str | None = None
    raw_size_bytes: int | None = None

    # ------------------------------------------------------------------
    # Versioning
    # ------------------------------------------------------------------
    collector_version: str = "1.0.0"
    config_version: int = 1

    # ------------------------------------------------------------------
    # Tracing
    # ------------------------------------------------------------------
    trace_id: str = ""
    request_id: str | None = None

    # ------------------------------------------------------------------
    # Failure
    # ------------------------------------------------------------------
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        """Validate the AcquisitionEnvelope contract."""

        # Identity
        _validate_non_blank_string("acquisition_id", self.acquisition_id)
        _validate_non_blank_string("job_id", self.job_id)
        _validate_non_blank_string("source_id", self.source_id)
        _validate_non_blank_string("collector_type", self.collector_type)

        # Source
        _validate_optional_string(
            "source_message_id",
            self.source_message_id,
        )

        if self.source_sequence is not None:
            if not isinstance(self.source_sequence, (str, int)):
                raise AcquisitionEnvelopeValidationError(
                    "source_sequence must be a string, integer, or None"
                )

        # Timing
        for field_name, value in (
            ("source_timestamp", self.source_timestamp),
            ("published_at", self.published_at),
            ("acquired_at", self.acquired_at),
            ("completed_at", self.completed_at),
            ("effective_at", self.effective_at),
        ):
            _parse_timestamp(field_name, value)

        # Execution
        if not isinstance(self.status, AcquisitionStatus):
            raise AcquisitionEnvelopeValidationError(
                "status must be one of: "
                "SUCCESS, RETRY, FAILED, DEGRADED"
            )

        _validate_positive_integer("attempt_no", self.attempt_no)
        _validate_non_negative_integer("retry_count", self.retry_count)

        # Payload metadata
        _validate_optional_string("content_type", self.content_type)
        _validate_optional_string("encoding", self.encoding)
        _validate_optional_string("payload_hash", self.payload_hash)

        if self.raw_size_bytes is not None:
            _validate_non_negative_integer(
                "raw_size_bytes",
                self.raw_size_bytes,
            )

        # Versioning
        _validate_non_blank_string(
            "collector_version",
            self.collector_version,
        )
        _validate_positive_integer(
            "config_version",
            self.config_version,
        )

        # Tracing
        _validate_non_blank_string("trace_id", self.trace_id)
        _validate_optional_string("request_id", self.request_id)

        # Failure information
        _validate_optional_string("error_code", self.error_code)
        _validate_optional_string("error_message", self.error_message)

        # Success requires raw evidence and integrity hash.
        if self.status is AcquisitionStatus.SUCCESS:
            if self.raw_payload is None:
                raise AcquisitionEnvelopeValidationError(
                    "raw_payload is required when status is SUCCESS"
                )

            if self.payload_hash is None or not self.payload_hash.strip():
                raise AcquisitionEnvelopeValidationError(
                    "payload_hash is required when status is SUCCESS"
                )

    def to_dict(self) -> dict[str, Any]:
        """
        Return a serializable representation of the envelope.

        Raw payload is returned unchanged; no semantic transformation is
        performed by this contract.
        """
        return {
            "acquisition_id": self.acquisition_id,
            "job_id": self.job_id,
            "source_id": self.source_id,
            "collector_type": self.collector_type,
            "source_message_id": self.source_message_id,
            "source_sequence": self.source_sequence,
            "source_timestamp": _serialize_timestamp(
                self.source_timestamp
            ),
            "published_at": _serialize_timestamp(self.published_at),
            "acquired_at": _serialize_timestamp(self.acquired_at),
            "completed_at": _serialize_timestamp(self.completed_at),
            "effective_at": _serialize_timestamp(self.effective_at),
            "status": self.status.value,
            "attempt_no": self.attempt_no,
            "retry_count": self.retry_count,
            "content_type": self.content_type,
            "encoding": self.encoding,
            "raw_payload": self.raw_payload,
            "payload_hash": self.payload_hash,
            "raw_size_bytes": self.raw_size_bytes,
            "collector_version": self.collector_version,
            "config_version": self.config_version,
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


__all__ = [
    "AcquisitionEnvelope",
    "AcquisitionEnvelopeValidationError",
    "AcquisitionStatus",
]
