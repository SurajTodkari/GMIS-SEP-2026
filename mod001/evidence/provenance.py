"""
MOD-001 Developer 1
D1-009 — Provenance Metadata

Responsibility:
    Attach source, collector, configuration, timing, job, and tracing
    metadata without changing the raw evidence.

Temporal correctness rules:
    - source_timestamp: preserve exactly when supplied by the source.
    - published_at: preserve exactly when supplied.
    - acquired_at: set from the system clock when not explicitly supplied.
    - completed_at: preserve when supplied by the acquisition runtime.
    - effective_at: preserve when supplied; never infer silently.
    - processed_at: intentionally NOT created by MOD-001.

This module does not perform semantic normalization, feature extraction,
sentiment analysis, or prediction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

VALID_COLLECTOR_TYPES = frozenset(
    {"API", "BROWSER", "RSS", "WEBSOCKET"}
)


def _utc_now() -> datetime:
    """Return the current UTC timestamp as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def _validate_timestamp(
    value: datetime | str | None,
    field_name: str,
    *,
    required: bool = False,
) -> None:
    """Validate a timestamp value without modifying it."""
    if value is None:
        if required:
            raise ValueError(f"{field_name} is required")
        return

    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError(
                f"{field_name} must be timezone-aware"
            )
        return

    if isinstance(value, str):
        try:
            datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise ValueError(
                f"{field_name} must be a valid ISO-8601 timestamp"
            ) from exc
        return

    raise TypeError(
        f"{field_name} must be datetime, ISO-8601 string, or None"
    )


def _require_non_empty_string(value: Any, field_name: str) -> None:
    """Validate a required non-empty string field."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{field_name} must be a non-empty string"
        )


@dataclass(frozen=True, slots=True)
class ProvenanceMetadata:
    """
    Immutable provenance record for an acquisition result.

    The fields intentionally mirror the MOD-001 acquisition context:
        - source identity
        - collector identity/version
        - configuration version
        - job/execution context
        - trace/request context
        - source and acquisition timing

    Raw payload is not stored here. It remains the responsibility of the
    raw evidence layer (D1-007).
    """

    source_id: str
    collector_type: str
    collector_version: str
    config_version: int
    source_config_version: int

    job_id: str
    trace_id: str
    request_id: str | None = None
    schedule_id: str | None = None
    attempt_no: int = 1

    source_timestamp: datetime | str | None = None
    published_at: datetime | str | None = None
    acquired_at: datetime = field(default_factory=_utc_now)
    completed_at: datetime | str | None = None
    effective_at: datetime | str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_string(self.source_id, "source_id")

        if self.collector_type not in VALID_COLLECTOR_TYPES:
            raise ValueError(
                f"Invalid collector_type: {self.collector_type}"
            )

        _require_non_empty_string(
            self.collector_version,
            "collector_version",
        )
        _require_non_empty_string(self.job_id, "job_id")
        _require_non_empty_string(self.trace_id, "trace_id")

        if self.request_id is not None:
            _require_non_empty_string(
                self.request_id,
                "request_id",
            )

        if self.schedule_id is not None:
            _require_non_empty_string(
                self.schedule_id,
                "schedule_id",
            )

        if not isinstance(self.config_version, int):
            raise TypeError("config_version must be an integer")

        if self.config_version < 1:
            raise ValueError("config_version must be >= 1")

        if not isinstance(self.source_config_version, int):
            raise TypeError(
                "source_config_version must be an integer"
            )

        if self.source_config_version < 1:
            raise ValueError(
                "source_config_version must be >= 1"
            )

        if not isinstance(self.attempt_no, int):
            raise TypeError("attempt_no must be an integer")

        if self.attempt_no < 1:
            raise ValueError("attempt_no must be >= 1")

        _validate_timestamp(
            self.source_timestamp,
            "source_timestamp",
        )
        _validate_timestamp(
            self.published_at,
            "published_at",
        )
        _validate_timestamp(
            self.acquired_at,
            "acquired_at",
            required=True,
        )
        _validate_timestamp(
            self.completed_at,
            "completed_at",
        )
        _validate_timestamp(
            self.effective_at,
            "effective_at",
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize provenance without introducing derived temporal fields.

        In particular, `processed_at` is not emitted because MOD-001 must
        not invent downstream processing time.
        """

        data: dict[str, Any] = {
            "source_id": self.source_id,
            "collector_type": self.collector_type,
            "collector_version": self.collector_version,
            "config_version": self.config_version,
            "source_config_version": self.source_config_version,
            "job_id": self.job_id,
            "trace_id": self.trace_id,
            "attempt_no": self.attempt_no,
            "source_timestamp": self.source_timestamp,
            "published_at": self.published_at,
            "acquired_at": self.acquired_at,
            "completed_at": self.completed_at,
            "effective_at": self.effective_at,
        }

        if self.request_id is not None:
            data["request_id"] = self.request_id

        if self.schedule_id is not None:
            data["schedule_id"] = self.schedule_id

        return data


def create_provenance(
    *,
    source_id: str,
    collector_type: str,
    collector_version: str,
    config_version: int,
    source_config_version: int,
    job_id: str,
    trace_id: str,
    request_id: str | None = None,
    schedule_id: str | None = None,
    attempt_no: int = 1,
    source_timestamp: datetime | str | None = None,
    published_at: datetime | str | None = None,
    acquired_at: datetime | None = None,
    completed_at: datetime | str | None = None,
    effective_at: datetime | str | None = None,
) -> ProvenanceMetadata:
    """
    Build provenance metadata for an acquisition.

    When `acquired_at` is not supplied, this function uses the system UTC
    clock. Other temporal fields are preserved only when supplied.
    """

    return ProvenanceMetadata(
        source_id=source_id,
        collector_type=collector_type,
        collector_version=collector_version,
        config_version=config_version,
        source_config_version=source_config_version,
        job_id=job_id,
        trace_id=trace_id,
        request_id=request_id,
        schedule_id=schedule_id,
        attempt_no=attempt_no,
        source_timestamp=source_timestamp,
        published_at=published_at,
        acquired_at=acquired_at or _utc_now(),
        completed_at=completed_at,
        effective_at=effective_at,
    )


def attach_provenance(
    envelope: Mapping[str, Any],
    provenance: ProvenanceMetadata,
) -> dict[str, Any]:
    """
    Return a new envelope with provenance attached.

    The original envelope is not mutated. The raw payload is copied by
    reference and is not parsed, normalized, or rewritten.
    """
    if not isinstance(envelope, Mapping):
        raise TypeError("envelope must be a mapping")

    result = dict(envelope)
    result["provenance"] = provenance.to_dict()

    return result


def provenance_from_envelope(
    envelope: Mapping[str, Any],
) -> ProvenanceMetadata:
    """
    Reconstruct provenance metadata from the acquisition envelope fields.

    This function preserves supplied temporal values and does not derive
    missing effective or processed times.
    """
    if not isinstance(envelope, Mapping):
        raise TypeError("envelope must be a mapping")

    required_fields = (
        "source_id",
        "collector_type",
        "collector_version",
        "config_version",
        "source_config_version",
        "job_id",
        "trace_id",
        "acquired_at",
    )

    missing = [
        field_name
        for field_name in required_fields
        if field_name not in envelope
    ]

    if missing:
        raise ValueError(
            "Missing required envelope provenance fields: "
            + ", ".join(missing)
        )

    return ProvenanceMetadata(
        source_id=envelope["source_id"],
        collector_type=envelope["collector_type"],
        collector_version=envelope["collector_version"],
        config_version=envelope["config_version"],
        source_config_version=envelope["source_config_version"],
        job_id=envelope["job_id"],
        trace_id=envelope["trace_id"],
        request_id=envelope.get("request_id"),
        schedule_id=envelope.get("schedule_id"),
        attempt_no=envelope.get("attempt_no", 1),
        source_timestamp=envelope.get("source_timestamp"),
        published_at=envelope.get("published_at"),
        acquired_at=envelope["acquired_at"],
        completed_at=envelope.get("completed_at"),
        effective_at=envelope.get("effective_at"),
    )
