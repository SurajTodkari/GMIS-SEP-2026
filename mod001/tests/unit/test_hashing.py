"""
MOD-001 Developer 1
D1-008 — Payload Hashing Unit Tests

Coverage:
    - Deterministic SHA-256 hashing
    - Changed-payload detection
    - Exact-byte hashing
    - Empty payload
    - Binary payloads
    - Supported byte-oriented inputs
    - Hash format validation
    - Hash verification
    - RawEvidence integration
"""

from pathlib import Path

import pytest

from mod001.evidence.hashing import (
    HASH_PREFIX,
    SHA256_HEX_LENGTH,
    generate_sha256,
    hash_raw_evidence,
    validate_hash_format,
    verify_sha256,
)
from mod001.evidence.raw_capture import capture_raw_payload


# ---------------------------------------------------------------------------
# Known SHA-256 test vectors
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("payload", "expected_hash"),
    [
        (
            b"",
            "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        ),
        (
            b"abc",
            "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        ),
    ],
)
def test_known_sha256_vectors(payload, expected_hash):
    assert generate_sha256(payload) == expected_hash


# ---------------------------------------------------------------------------
# Deterministic hashing
# ---------------------------------------------------------------------------

def test_same_payload_produces_same_hash():
    payload = b'{"symbol":"XAUUSD","price":3850.25}'

    first_hash = generate_sha256(payload)
    second_hash = generate_sha256(payload)

    assert first_hash == second_hash


def test_hash_is_prefixed_with_sha256():
    payload_hash = generate_sha256(b"XAUUSD")

    assert payload_hash.startswith(HASH_PREFIX)


def test_hash_has_expected_sha256_length():
    payload_hash = generate_sha256(b"XAUUSD")
    digest = payload_hash[len(HASH_PREFIX):]

    assert len(digest) == SHA256_HEX_LENGTH


def test_hash_digest_is_lowercase_hex():
    payload_hash = generate_sha256(b"XAUUSD")
    digest = payload_hash[len(HASH_PREFIX):]

    assert all(character in "0123456789abcdef" for character in digest)


# ---------------------------------------------------------------------------
# Changed payload detection
# ---------------------------------------------------------------------------

def test_changed_payload_produces_different_hash():
    original = b'{"price":3850.25}'
    changed = b'{"price":3850.26}'

    assert generate_sha256(original) != generate_sha256(changed)


def test_single_byte_change_produces_different_hash():
    original = b"XAUUSD|3850.25"
    changed = b"XAUUSD|3850.26"

    assert generate_sha256(original) != generate_sha256(changed)


def test_case_change_produces_different_hash():
    original = b"XAUUSD"
    changed = b"xauusd"

    assert generate_sha256(original) != generate_sha256(changed)


# ---------------------------------------------------------------------------
# Exact raw representation
# ---------------------------------------------------------------------------

def test_whitespace_change_produces_different_hash():
    compact = b'{"symbol":"XAUUSD"}'
    spaced = b'{ "symbol": "XAUUSD" }'

    assert generate_sha256(compact) != generate_sha256(spaced)


def test_newline_change_produces_different_hash():
    first = b'{"symbol":"XAUUSD"}'
    second = b'{"symbol":"XAUUSD"}\n'

    assert generate_sha256(first) != generate_sha256(second)


def test_hashing_does_not_json_normalize_raw_bytes():
    first = b'{"a":1,"b":2}'
    second = b'{ "b": 2, "a": 1 }'

    # The semantic JSON values could be equivalent, but the raw byte
    # representation is different and therefore must hash differently.
    assert generate_sha256(first) != generate_sha256(second)


# ---------------------------------------------------------------------------
# Empty and binary payloads
# ---------------------------------------------------------------------------

def test_empty_payload_has_deterministic_hash():
    first = generate_sha256(b"")
    second = generate_sha256(b"")

    assert first == second


def test_binary_payload_is_hashed_exactly():
    payload = bytes([0, 1, 2, 127, 128, 254, 255])

    payload_hash = generate_sha256(payload)

    assert payload_hash == (
        "sha256:7bb6463b30f9e301fed333cdf8960ca9497b602ccd8eeb46ae42693fdea15a4d"
    )


# ---------------------------------------------------------------------------
# Supported input types
# ---------------------------------------------------------------------------

def test_bytearray_produces_same_hash_as_bytes():
    payload = b"XAUUSD|3850.25"

    assert generate_sha256(payload) == generate_sha256(bytearray(payload))


def test_memoryview_produces_same_hash_as_bytes():
    payload = b"XAUUSD|3850.25"

    assert generate_sha256(payload) == generate_sha256(memoryview(payload))


@pytest.mark.parametrize(
    "invalid_payload",
    [
        "XAUUSD",
        {"symbol": "XAUUSD"},
        ["XAUUSD"],
        3850.25,
        True,
        None,
    ],
)
def test_non_byte_payload_is_rejected(invalid_payload):
    with pytest.raises(TypeError, match="payload must be bytes"):
        generate_sha256(invalid_payload)


# ---------------------------------------------------------------------------
# Hash format validation
# ---------------------------------------------------------------------------

def test_valid_hash_format_is_accepted():
    payload_hash = generate_sha256(b"abc")

    assert validate_hash_format(payload_hash) is True


@pytest.mark.parametrize(
    "invalid_hash",
    [
        "",
        "sha256:",
        "sha256:1234",
        "sha256:" + ("g" * 64),
        "SHA256:" + ("0" * 64),
        ("0" * 64),
        None,
        123,
    ],
)
def test_invalid_hash_format_is_rejected(invalid_hash):
    assert validate_hash_format(invalid_hash) is False


# ---------------------------------------------------------------------------
# Hash verification
# ---------------------------------------------------------------------------

def test_matching_hash_verifies_successfully():
    payload = b'{"symbol":"XAUUSD","price":3850.25}'
    expected_hash = generate_sha256(payload)

    assert verify_sha256(payload, expected_hash) is True


def test_mismatched_hash_fails_verification():
    payload = b'{"symbol":"XAUUSD","price":3850.25}'
    different_payload = b'{"symbol":"XAUUSD","price":3851.25}'
    expected_hash = generate_sha256(different_payload)

    assert verify_sha256(payload, expected_hash) is False


def test_invalid_hash_format_fails_verification():
    payload = b"XAUUSD"

    assert verify_sha256(payload, "invalid") is False


def test_mutated_payload_fails_original_hash():
    original = b"XAUUSD|3850.25"
    original_hash = generate_sha256(original)

    mutated = b"XAUUSD|3850.26"

    assert verify_sha256(mutated, original_hash) is False


# ---------------------------------------------------------------------------
# D1-007 RawEvidence integration
# ---------------------------------------------------------------------------

def test_raw_evidence_payload_hash_matches_exact_preserved_bytes():
    raw_payload = b'{"symbol":"XAUUSD","price":3850.25}\n'

    evidence = capture_raw_payload(
        raw_payload,
        content_type="application/json",
        encoding="UTF-8",
    )

    expected_hash = generate_sha256(raw_payload)

    assert hash_raw_evidence(evidence) == expected_hash


def test_raw_evidence_modified_bytes_do_not_match_original_hash():
    original = capture_raw_payload(
        b'{"symbol":"XAUUSD","price":3850.25}',
    )

    original_hash = hash_raw_evidence(original)

    modified = capture_raw_payload(
        b'{"symbol":"XAUUSD","price":3851.25}',
    )

    assert verify_sha256(
        modified.payload,
        original_hash,
    ) is False


def test_hash_raw_evidence_requires_payload_attribute():
    with pytest.raises(TypeError, match="raw byte payload"):
        hash_raw_evidence(object())


# ---------------------------------------------------------------------------
# Determinism across repeated calls
# ---------------------------------------------------------------------------

def test_repeated_hash_generation_remains_deterministic():
    payload = (
        b'{"source":"gold_api","symbol":"XAUUSD",'
        b'"price":3850.25,"timestamp":"2026-10-01T10:01:00Z"}'
    )

    hashes = {
        generate_sha256(payload)
        for _ in range(100)
    }

    assert len(hashes) == 1
