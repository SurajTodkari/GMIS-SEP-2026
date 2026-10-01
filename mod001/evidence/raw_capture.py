"""
MOD-001 Developer 1
D1-007 — Raw Evidence Handling

Responsibility:
    Preserve raw source evidence without semantic modification.

Architecture rules implemented here:
    - Store the raw representation as bytes.
    - Do not parse or normalize source content.
    - Record content type and encoding metadata.
    - Record raw payload size.
    - Preserve acquisition timing metadata.
    - Support exact byte-for-byte persistence and retrieval.

Important:
    This module intentionally does NOT calculate payload hashes.
    Hashing belongs to D1-008.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final


DEFAULT_ENCODING: Final[str] = "UTF-8"


def _utc_now() -> datetime:
    """Return the current UTC timestamp as an aware datetime."""
    return datetime.now(timezone.utc)


def _validate_bytes_payload(payload: object) -> bytes:
    """
    Accept only byte-oriented raw evidence.

    The raw evidence boundary must not parse, normalize, or reconstruct
    structured source content. If a collector has received JSON/XML/HTML/etc.,
    it should pass the original response bytes to this function.
    """
    if isinstance(payload, bytes):
        return payload

    if isinstance(payload, bytearray):
        return bytes(payload)

    if isinstance(payload, memoryview):
        return payload.tobytes()

    raise TypeError(
        "raw_payload must be bytes, bytearray, or memoryview. "
        "Do not pass parsed/normalized objects to the raw-evidence layer."
    )


@dataclass(frozen=True, slots=True)
class RawEvidence:
    """
    Immutable representation of captured raw source evidence.

    payload:
        Exact byte representation received from the collector.

    content_type:
        Source content type, for example 'application/json'.

    encoding:
        Character encoding associated with the source representation,
        when known.

    acquired_at:
        Time at which the collector acquired the evidence.
    """

    payload: bytes
    content_type: str | None
    encoding: str | None
    acquired_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.payload, bytes):
            raise TypeError("payload must be bytes")

        if self.acquired_at.tzinfo is None:
            raise ValueError("acquired_at must be timezone-aware")

    @property
    def raw_size_bytes(self) -> int:
        """Return the exact byte size of the preserved evidence."""
        return len(self.payload)

    def to_metadata(self) -> dict[str, object]:
        """
        Return evidence metadata without changing the raw payload.

        The payload itself is intentionally not converted into a semantic
        structure here.
        """
        return {
            "content_type": self.content_type,
            "encoding": self.encoding,
            "raw_size_bytes": self.raw_size_bytes,
            "acquired_at": self.acquired_at.isoformat(),
        }


def capture_raw_payload(
    raw_payload: bytes | bytearray | memoryview,
    *,
    content_type: str | None = None,
    encoding: str | None = DEFAULT_ENCODING,
    acquired_at: datetime | None = None,
) -> RawEvidence:
    """
    Capture raw source bytes without semantic modification.

    This is the primary D1-007 entry point.

    Example:
        response_body = http_response.content

        evidence = capture_raw_payload(
            response_body,
            content_type="application/json",
            encoding="UTF-8",
        )
    """
    payload_bytes = _validate_bytes_payload(raw_payload)
    timestamp = acquired_at or _utc_now()

    return RawEvidence(
        payload=payload_bytes,
        content_type=content_type,
        encoding=encoding,
        acquired_at=timestamp,
    )


def capture_text_payload(
    raw_payload: str,
    *,
    encoding: str = DEFAULT_ENCODING,
    content_type: str | None = None,
    acquired_at: datetime | None = None,
) -> RawEvidence:
    """
    Explicit helper for text that has already been received as text.

    This performs only the requested text -> bytes encoding operation.
    It does not parse, normalize, trim, or otherwise modify the content.

    For strongest evidence fidelity, collectors should prefer passing the
    original response bytes to capture_raw_payload().
    """
    if not isinstance(raw_payload, str):
        raise TypeError("raw_payload must be a string")

    payload_bytes = raw_payload.encode(encoding)

    return capture_raw_payload(
        payload_bytes,
        content_type=content_type,
        encoding=encoding,
        acquired_at=acquired_at,
    )


def persist_raw_evidence(
    evidence: RawEvidence,
    destination: str | Path,
) -> Path:
    """
    Persist the exact evidence bytes to a file.

    The file contains only the raw payload bytes. No JSON serialization,
    parsing, whitespace normalization, or semantic transformation occurs.

    Metadata should be stored separately by the caller/storage layer.
    """
    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    destination_path.write_bytes(evidence.payload)

    return destination_path


def load_raw_evidence(
    source: str | Path,
    *,
    content_type: str | None = None,
    encoding: str | None = DEFAULT_ENCODING,
    acquired_at: datetime | None = None,
) -> RawEvidence:
    """
    Load previously persisted raw evidence without transformation.
    """
    source_path = Path(source)
    payload = source_path.read_bytes()

    return capture_raw_payload(
        payload,
        content_type=content_type,
        encoding=encoding,
        acquired_at=acquired_at,
    )


def verify_raw_preservation(
    original: RawEvidence,
    restored: RawEvidence,
) -> bool:
    """
    Verify that two evidence records contain identical raw bytes.

    This is a byte-for-byte preservation check.
    D1-008 is responsible for cryptographic hashing.
    """
    return original.payload == restored.payload
