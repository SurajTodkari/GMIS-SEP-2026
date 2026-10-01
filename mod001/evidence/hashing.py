"""
MOD-001 Developer 1
D1-008 — Payload Hashing

Responsibility:
    Generate and verify a deterministic integrity hash for the exact raw
    evidence representation.

Architecture rule:
    D1-008 hashes the exact bytes preserved by D1-007.
    It must not parse, normalize, sort keys, trim whitespace, or otherwise
    semantically transform the payload before hashing.

Hash algorithm:
    SHA-256

Stored format:
    sha256:<64 lowercase hexadecimal characters>
"""

from __future__ import annotations

import hashlib
from typing import Final


HASH_ALGORITHM: Final[str] = "sha256"
HASH_PREFIX: Final[str] = "sha256:"
SHA256_HEX_LENGTH: Final[int] = 64


def _coerce_bytes(payload: object) -> bytes:
    """
    Convert supported byte-oriented values to immutable bytes.

    This conversion is representation-preserving for the supported types.
    Parsed dictionaries/lists/numbers/strings are intentionally rejected so
    callers cannot accidentally introduce semantic normalization here.
    """
    if isinstance(payload, bytes):
        return payload

    if isinstance(payload, bytearray):
        return bytes(payload)

    if isinstance(payload, memoryview):
        return payload.tobytes()

    raise TypeError(
        "payload must be bytes, bytearray, or memoryview. "
        "Hash the exact raw evidence bytes produced by D1-007."
    )


def generate_sha256(payload: bytes | bytearray | memoryview) -> str:
    """
    Generate the SHA-256 integrity hash for the exact raw bytes.

    Example:
        >>> generate_sha256(b"abc")
        'sha256:ba7816bf...'
    """
    raw_bytes = _coerce_bytes(payload)
    digest = hashlib.sha256(raw_bytes).hexdigest()
    return f"{HASH_PREFIX}{digest}"


def validate_hash_format(payload_hash: str) -> bool:
    """
    Validate the external/stored SHA-256 hash representation.

    Expected form:
        sha256:<64 lowercase hexadecimal characters>
    """
    if not isinstance(payload_hash, str):
        return False

    if not payload_hash.startswith(HASH_PREFIX):
        return False

    digest = payload_hash[len(HASH_PREFIX):]

    if len(digest) != SHA256_HEX_LENGTH:
        return False

    return all(character in "0123456789abcdef" for character in digest)


def verify_sha256(
    payload: bytes | bytearray | memoryview,
    expected_hash: str,
) -> bool:
    """
    Verify that expected_hash matches the exact supplied raw bytes.

    The comparison uses hmac.compare_digest for constant-time comparison.
    """
    if not validate_hash_format(expected_hash):
        return False

    actual_hash = generate_sha256(payload)

    # Import locally to keep the public module surface small.
    import hmac

    return hmac.compare_digest(actual_hash, expected_hash)


def hash_raw_evidence(evidence: object) -> str:
    """
    Hash a D1-007 RawEvidence object.

    The object must expose a byte-valued `payload` attribute. The payload is
    passed directly to generate_sha256 without semantic transformation.
    """
    if not hasattr(evidence, "payload"):
        raise TypeError(
            "evidence must provide a raw byte payload"
        )

    return generate_sha256(evidence.payload)
