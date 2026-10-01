"""
MOD-001 Developer 1
D1-007 — Raw Evidence Handling Unit Tests

Coverage:
    - Raw byte capture
    - Exact byte-for-byte preservation
    - Raw size calculation
    - Metadata preservation
    - Timestamp preservation
    - File persistence and reload
    - Empty payload behavior
    - Rejection of parsed/normalized objects
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from mod001.evidence.raw_capture import (
    DEFAULT_ENCODING,
    RawEvidence,
    capture_raw_payload,
    capture_text_payload,
    load_raw_evidence,
    persist_raw_evidence,
    verify_raw_preservation,
)


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

RAW_JSON_BYTES = (
    b'{"symbol":"XAUUSD","price":3850.25,"source":"gold_api"}'
)

ACQUIRED_AT = datetime(
    2026,
    10,
    1,
    10,
    1,
    1,
    200000,
    tzinfo=timezone.utc,
)


# ---------------------------------------------------------------------------
# D1-T17 — Valid raw capture
# ---------------------------------------------------------------------------

def test_capture_valid_raw_bytes_is_accepted():
    evidence = capture_raw_payload(
        RAW_JSON_BYTES,
        content_type="application/json",
        encoding="UTF-8",
        acquired_at=ACQUIRED_AT,
    )

    assert isinstance(evidence, RawEvidence)
    assert evidence.payload == RAW_JSON_BYTES


# ---------------------------------------------------------------------------
# D1-T18 — Exact raw preservation
# ---------------------------------------------------------------------------

def test_raw_bytes_are_preserved_exactly():
    evidence = capture_raw_payload(
        RAW_JSON_BYTES,
        content_type="application/json",
        encoding="UTF-8",
        acquired_at=ACQUIRED_AT,
    )

    assert evidence.payload == RAW_JSON_BYTES
    assert evidence.payload == bytes(RAW_JSON_BYTES)


def test_raw_whitespace_is_not_normalized():
    raw_payload = (
        b'{  "symbol": "XAUUSD",  '
        b'"price": 3850.25 }\n'
    )

    evidence = capture_raw_payload(
        raw_payload,
        content_type="application/json",
        encoding="UTF-8",
        acquired_at=ACQUIRED_AT,
    )

    assert evidence.payload == raw_payload


def test_raw_byte_order_is_not_changed():
    raw_payload = bytes([0, 1, 2, 127, 128, 254, 255])

    evidence = capture_raw_payload(
        raw_payload,
        acquired_at=ACQUIRED_AT,
    )

    assert evidence.payload == raw_payload


# ---------------------------------------------------------------------------
# D1-T19 — Raw size
# ---------------------------------------------------------------------------

def test_raw_size_bytes_matches_exact_payload_length():
    evidence = capture_raw_payload(
        RAW_JSON_BYTES,
        acquired_at=ACQUIRED_AT,
    )

    assert evidence.raw_size_bytes == len(RAW_JSON_BYTES)


def test_multibyte_utf8_payload_uses_byte_count():
    raw_text = "XAUUSD € 金"
    raw_payload = raw_text.encode("UTF-8")

    evidence = capture_raw_payload(
        raw_payload,
        content_type="text/plain",
        encoding="UTF-8",
        acquired_at=ACQUIRED_AT,
    )

    assert evidence.raw_size_bytes == len(raw_payload)
    assert evidence.raw_size_bytes != len(raw_text)


# ---------------------------------------------------------------------------
# D1-T20 — Metadata preservation
# ---------------------------------------------------------------------------

def test_content_type_and_encoding_are_preserved():
    evidence = capture_raw_payload(
        RAW_JSON_BYTES,
        content_type="application/json",
        encoding="UTF-8",
        acquired_at=ACQUIRED_AT,
    )

    metadata = evidence.to_metadata()

    assert metadata["content_type"] == "application/json"
    assert metadata["encoding"] == "UTF-8"
    assert metadata["raw_size_bytes"] == len(RAW_JSON_BYTES)


def test_default_encoding_is_utf8():
    evidence = capture_raw_payload(
        RAW_JSON_BYTES,
        acquired_at=ACQUIRED_AT,
    )

    assert evidence.encoding == DEFAULT_ENCODING


# ---------------------------------------------------------------------------
# D1-T21 — Acquisition timestamp
# ---------------------------------------------------------------------------

def test_acquisition_timestamp_is_preserved():
    evidence = capture_raw_payload(
        RAW_JSON_BYTES,
        acquired_at=ACQUIRED_AT,
    )

    assert evidence.acquired_at == ACQUIRED_AT


def test_naive_acquisition_timestamp_is_rejected():
    naive_timestamp = datetime(2026, 10, 1, 10, 1, 1)

    with pytest.raises(ValueError, match="timezone-aware"):
        capture_raw_payload(
            RAW_JSON_BYTES,
            acquired_at=naive_timestamp,
        )


# ---------------------------------------------------------------------------
# D1-T22 — Persistence and reload
# ---------------------------------------------------------------------------

def test_persist_and_reload_preserves_exact_raw_bytes(tmp_path: Path):
    evidence = capture_raw_payload(
        RAW_JSON_BYTES,
        content_type="application/json",
        encoding="UTF-8",
        acquired_at=ACQUIRED_AT,
    )

    destination = tmp_path / "raw_payload.bin"

    persisted_path = persist_raw_evidence(
        evidence,
        destination,
    )

    restored = load_raw_evidence(
        persisted_path,
        content_type="application/json",
        encoding="UTF-8",
        acquired_at=ACQUIRED_AT,
    )

    assert persisted_path.exists()
    assert persisted_path.read_bytes() == RAW_JSON_BYTES
    assert restored.payload == RAW_JSON_BYTES
    assert verify_raw_preservation(evidence, restored) is True


def test_persist_creates_missing_parent_directories(tmp_path: Path):
    evidence = capture_raw_payload(
        b"raw-evidence",
        acquired_at=ACQUIRED_AT,
    )

    destination = (
        tmp_path
        / "nested"
        / "evidence"
        / "payload.bin"
    )

    persist_raw_evidence(evidence, destination)

    assert destination.exists()
    assert destination.read_bytes() == b"raw-evidence"


# ---------------------------------------------------------------------------
# D1-T23 — Preservation mismatch
# ---------------------------------------------------------------------------

def test_modified_payload_is_not_considered_preserved():
    original = capture_raw_payload(
        b'{"price":3850.25}',
        acquired_at=ACQUIRED_AT,
    )

    modified = capture_raw_payload(
        b'{"price":3851.25}',
        acquired_at=ACQUIRED_AT,
    )

    assert verify_raw_preservation(original, modified) is False


def test_single_byte_change_is_detected():
    original = capture_raw_payload(
        b"XAUUSD|3850.25",
        acquired_at=ACQUIRED_AT,
    )

    modified = capture_raw_payload(
        b"XAUUSD|3850.26",
        acquired_at=ACQUIRED_AT,
    )

    assert verify_raw_preservation(original, modified) is False


# ---------------------------------------------------------------------------
# D1-T24 — Parsed/normalized objects must be rejected
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "invalid_payload",
    [
        {"symbol": "XAUUSD", "price": 3850.25},
        ["XAUUSD", 3850.25],
        3850.25,
        True,
        None,
    ],
)
def test_parsed_or_non_byte_payload_is_rejected(invalid_payload):
    with pytest.raises(TypeError, match="raw_payload must be bytes"):
        capture_raw_payload(
            invalid_payload,
            acquired_at=ACQUIRED_AT,
        )


def test_raw_evidence_does_not_store_a_parsed_object():
    evidence = capture_raw_payload(
        b'{"price":3850.25}',
        acquired_at=ACQUIRED_AT,
    )

    assert isinstance(evidence.payload, bytes)
    assert not isinstance(evidence.payload, dict)


# ---------------------------------------------------------------------------
# D1-T25 — Empty payload behavior
# ---------------------------------------------------------------------------

def test_empty_raw_payload_is_preserved():
    evidence = capture_raw_payload(
        b"",
        content_type="application/octet-stream",
        acquired_at=ACQUIRED_AT,
    )

    assert evidence.payload == b""
    assert evidence.raw_size_bytes == 0


def test_empty_raw_payload_persists_and_reloads(tmp_path: Path):
    evidence = capture_raw_payload(
        b"",
        acquired_at=ACQUIRED_AT,
    )

    destination = tmp_path / "empty.bin"
    persist_raw_evidence(evidence, destination)

    restored = load_raw_evidence(
        destination,
        acquired_at=ACQUIRED_AT,
    )

    assert destination.exists()
    assert destination.read_bytes() == b""
    assert restored.payload == b""
    assert restored.raw_size_bytes == 0


# ---------------------------------------------------------------------------
# Additional byte-oriented input tests
# ---------------------------------------------------------------------------

def test_bytearray_is_captured_as_immutable_bytes():
    payload = bytearray(RAW_JSON_BYTES)

    evidence = capture_raw_payload(
        payload,
        acquired_at=ACQUIRED_AT,
    )

    assert isinstance(evidence.payload, bytes)
    assert evidence.payload == RAW_JSON_BYTES


def test_memoryview_is_captured_as_immutable_bytes():
    payload = memoryview(RAW_JSON_BYTES)

    evidence = capture_raw_payload(
        payload,
        acquired_at=ACQUIRED_AT,
    )

    assert isinstance(evidence.payload, bytes)
    assert evidence.payload == RAW_JSON_BYTES


# ---------------------------------------------------------------------------
# Text helper tests
# ---------------------------------------------------------------------------

def test_capture_text_payload_encodes_without_semantic_processing():
    raw_text = '{"symbol":"XAUUSD","price":3850.25}\n'

    evidence = capture_text_payload(
        raw_text,
        encoding="UTF-8",
        content_type="application/json",
        acquired_at=ACQUIRED_AT,
    )

    assert evidence.payload == raw_text.encode("UTF-8")
    assert evidence.raw_size_bytes == len(
        raw_text.encode("UTF-8")
    )


def test_capture_text_payload_rejects_non_string_input():
    with pytest.raises(TypeError, match="raw_payload must be a string"):
        capture_text_payload(
            b"already-bytes",
            acquired_at=ACQUIRED_AT,
        )


# ---------------------------------------------------------------------------
# Metadata serialization test
# ---------------------------------------------------------------------------

def test_to_metadata_does_not_include_raw_payload():
    evidence = capture_raw_payload(
        RAW_JSON_BYTES,
        content_type="application/json",
        encoding="UTF-8",
        acquired_at=ACQUIRED_AT,
    )

    metadata = evidence.to_metadata()

    assert "payload" not in metadata
    assert "raw_payload" not in metadata
    assert metadata["raw_size_bytes"] == len(RAW_JSON_BYTES)
    assert metadata["content_type"] == "application/json"
    assert metadata["encoding"] == "UTF-8"
