"""
MOD-001 — Developer 1
D1-005: AcquisitionEnvelope Tests

Coverage:
    D1-T07 — Create valid AcquisitionEnvelope
    D1-T08 — Missing raw payload on SUCCESS
    D1-T09 — Missing hash when required
    D1-T12 — Invalid status
    D1-T13 — Malformed timestamp

Additional contract coverage:
    - All MOD-001 status values
    - Identity validation
    - Source metadata validation
    - Timing field validation
    - Attempt/retry validation
    - Payload metadata validation
    - Versioning/tracing validation
    - Failure context
    - Serialization
    - Raw payload preservation
    - Contract immutability
    - SUCCESS vs non-SUCCESS evidence requirements
"""

from datetime import datetime, timezone

import pytest

from mod001.contracts.acquisition_envelope import (
    AcquisitionEnvelope,
    AcquisitionEnvelopeValidationError,
    AcquisitionStatus,
)


def make_envelope(**overrides) -> AcquisitionEnvelope:
    """Create a valid baseline successful AcquisitionEnvelope."""
    data = {
        "acquisition_id": "ACQ-000001",
        "job_id": "JOB-000001",
        "source_id": "gold_api",
        "collector_type": "API",
        "source_message_id": None,
        "source_sequence": None,
        "source_timestamp": "2026-10-01T10:01:00Z",
        "published_at": None,
        "acquired_at": "2026-10-01T10:01:01Z",
        "completed_at": "2026-10-01T10:01:01.200Z",
        "effective_at": None,
        "status": AcquisitionStatus.SUCCESS,
        "attempt_no": 1,
        "retry_count": 0,
        "content_type": "application/json",
        "encoding": "UTF-8",
        "raw_payload": {
            "symbol": "XAUUSD",
            "price": 3850.25,
        },
        "payload_hash": "sha256:abc123",
        "raw_size_bytes": 42,
        "collector_version": "1.0.0",
        "config_version": 1,
        "trace_id": "TRACE-001",
        "request_id": "REQ-001",
        "error_code": None,
        "error_message": None,
    }

    data.update(overrides)
    return AcquisitionEnvelope(**data)


# ---------------------------------------------------------------------------
# D1-T07 — Create valid AcquisitionEnvelope
# ---------------------------------------------------------------------------

def test_d1_t07_valid_acquisition_envelope():
    """A valid AcquisitionEnvelope must be accepted."""
    envelope = make_envelope()

    assert envelope.acquisition_id == "ACQ-000001"
    assert envelope.job_id == "JOB-000001"
    assert envelope.source_id == "gold_api"
    assert envelope.collector_type == "API"
    assert envelope.status is AcquisitionStatus.SUCCESS
    assert envelope.attempt_no == 1
    assert envelope.retry_count == 0
    assert envelope.raw_payload["symbol"] == "XAUUSD"
    assert envelope.payload_hash == "sha256:abc123"
    assert envelope.config_version == 1
    assert envelope.trace_id == "TRACE-001"


# ---------------------------------------------------------------------------
# D1-T08 — Missing raw payload on SUCCESS
# ---------------------------------------------------------------------------

def test_d1_t08_missing_raw_payload_on_success():
    """SUCCESS requires a raw_payload."""
    with pytest.raises(AcquisitionEnvelopeValidationError):
        make_envelope(raw_payload=None)


# ---------------------------------------------------------------------------
# D1-T09 — Missing hash when required
# ---------------------------------------------------------------------------

def test_d1_t09_missing_hash_on_success():
    """SUCCESS requires a payload_hash."""
    with pytest.raises(AcquisitionEnvelopeValidationError):
        make_envelope(payload_hash=None)


def test_d1_t09_blank_hash_on_success():
    """SUCCESS must reject a blank payload_hash."""
    with pytest.raises(AcquisitionEnvelopeValidationError):
        make_envelope(payload_hash="   ")


# ---------------------------------------------------------------------------
# D1-T12 — Invalid status
# ---------------------------------------------------------------------------

def test_d1_t12_invalid_status():
    """Unsupported acquisition status must be rejected."""
    with pytest.raises(AcquisitionEnvelopeValidationError):
        make_envelope(status="INVALID")


@pytest.mark.parametrize(
    "status",
    [
        AcquisitionStatus.SUCCESS,
        AcquisitionStatus.RETRY,
        AcquisitionStatus.FAILED,
        AcquisitionStatus.DEGRADED,
    ],
)
def test_all_defined_status_values_supported(status):
    """All statuses defined by MOD-001 must be supported."""
    if status is AcquisitionStatus.SUCCESS:
        envelope = make_envelope(status=status)
    else:
        envelope = make_envelope(
            status=status,
            raw_payload=None,
            payload_hash=None,
            error_code="SOURCE_ERROR",
            error_message="Acquisition outcome is not successful.",
        )

    assert envelope.status is status


# ---------------------------------------------------------------------------
# D1-T13 — Malformed timestamp
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "field_name",
    [
        "source_timestamp",
        "published_at",
        "acquired_at",
        "completed_at",
        "effective_at",
    ],
)
def test_d1_t13_malformed_timestamp_rejected(field_name):
    """Malformed timestamps must be rejected."""
    with pytest.raises(AcquisitionEnvelopeValidationError):
        make_envelope(**{field_name: "not-a-timestamp"})


@pytest.mark.parametrize(
    "field_name",
    [
        "source_timestamp",
        "published_at",
        "acquired_at",
        "completed_at",
        "effective_at",
    ],
)
def test_blank_timestamp_rejected(field_name):
    """Blank timestamp strings must be rejected."""
    with pytest.raises(AcquisitionEnvelopeValidationError):
        make_envelope(**{field_name: "   "})


def test_timestamp_datetime_value_is_accepted():
    """datetime timestamp values must be accepted."""
    timestamp = datetime(
        2026,
        10,
        1,
        10,
        1,
        tzinfo=timezone.utc,
    )

    envelope = make_envelope(
        acquired_at=timestamp,
    )

    assert envelope.acquired_at == timestamp


def test_naive_datetime_value_is_preserved():
    """
    A naive datetime is accepted as a parseable datetime and preserved
    by the contract rather than silently rewritten.
    """
    timestamp = datetime(
        2026,
        10,
        1,
        10,
        1,
    )

    envelope = make_envelope(
        acquired_at=timestamp,
    )

    assert envelope.acquired_at == timestamp
    assert envelope.acquired_at.tzinfo is None


def test_optional_timestamps_can_be_none():
    """Optional timing fields may legitimately be unavailable."""
    envelope = make_envelope(
        source_timestamp=None,
        published_at=None,
        effective_at=None,
    )

    assert envelope.source_timestamp is None
    assert envelope.published_at is None
    assert envelope.effective_at is None


# ---------------------------------------------------------------------------
# Identity validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "field_name",
    [
        "acquisition_id",
        "job_id",
        "source_id",
        "collector_type",
    ],
)
def test_required_identity_fields_reject_blank_values(field_name):
    """Required identity fields must not be blank."""
    with pytest.raises(AcquisitionEnvelopeValidationError):
        make_envelope(**{field_name: "   "})


@pytest.mark.parametrize(
    "field_name",
    [
        "acquisition_id",
        "job_id",
        "source_id",
        "collector_type",
    ],
)
def test_required_identity_fields_reject_non_strings(field_name):
    """Required identity fields must contain strings."""
    with pytest.raises(AcquisitionEnvelopeValidationError):
        make_envelope(**{field_name: 123})


# ---------------------------------------------------------------------------
# Source metadata
# ---------------------------------------------------------------------------

def test_source_message_id_accepts_string():
    """source_message_id may contain a source-provided message ID."""
    envelope = make_envelope(
        source_message_id="MSG-000001",
    )

    assert envelope.source_message_id == "MSG-000001"


def test_source_message_id_rejects_non_string():
    """source_message_id must be a string or None."""
    with pytest.raises(AcquisitionEnvelopeValidationError):
        make_envelope(source_message_id=123)


@pytest.mark.parametrize(
    "value",
    [
        1,
        0,
        "SEQ-001",
    ],
)
def test_source_sequence_accepts_string_or_integer(value):
    """source_sequence may be represented as string or integer."""
    envelope = make_envelope(source_sequence=value)

    assert envelope.source_sequence == value


# ---------------------------------------------------------------------------
# Execution validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "attempt_no",
    [
        0,
        -1,
    ],
)
def test_invalid_attempt_number_rejected(attempt_no):
    """attempt_no must be >= 1."""
    with pytest.raises(AcquisitionEnvelopeValidationError):
        make_envelope(attempt_no=attempt_no)


def test_boolean_attempt_number_rejected():
    """bool must not be accepted as an integer attempt number."""
    with pytest.raises(AcquisitionEnvelopeValidationError):
        make_envelope(attempt_no=True)


@pytest.mark.parametrize(
    "retry_count",
    [
        -1,
        -10,
    ],
)
def test_negative_retry_count_rejected(retry_count):
    """retry_count must be >= 0."""
    with pytest.raises(AcquisitionEnvelopeValidationError):
        make_envelope(retry_count=retry_count)


def test_boolean_retry_count_rejected():
    """bool must not be accepted as an integer retry count."""
    with pytest.raises(AcquisitionEnvelopeValidationError):
        make_envelope(retry_count=True)


# ---------------------------------------------------------------------------
# Payload metadata
# ---------------------------------------------------------------------------

def test_content_type_and_encoding_are_preserved():
    """Payload metadata must remain unchanged."""
    envelope = make_envelope(
        content_type="application/json",
        encoding="UTF-8",
    )

    assert envelope.content_type == "application/json"
    assert envelope.encoding == "UTF-8"


def test_raw_size_bytes_accepts_zero():
    """Zero is a valid non-negative raw payload size."""
    envelope = make_envelope(raw_size_bytes=0)

    assert envelope.raw_size_bytes == 0


def test_negative_raw_size_rejected():
    """raw_size_bytes must be >= 0."""
    with pytest.raises(AcquisitionEnvelopeValidationError):
        make_envelope(raw_size_bytes=-1)


def test_raw_size_boolean_rejected():
    """bool must not be accepted as raw_size_bytes."""
    with pytest.raises(AcquisitionEnvelopeValidationError):
        make_envelope(raw_size_bytes=True)


# ---------------------------------------------------------------------------
# Versioning and tracing
# ---------------------------------------------------------------------------

def test_config_version_must_be_positive():
    """config_version must be >= 1."""
    with pytest.raises(AcquisitionEnvelopeValidationError):
        make_envelope(config_version=0)


def test_collector_version_must_not_be_blank():
    """collector_version is required for provenance."""
    with pytest.raises(AcquisitionEnvelopeValidationError):
        make_envelope(collector_version="   ")


def test_trace_id_must_not_be_blank():
    """trace_id is required for tracing."""
    with pytest.raises(AcquisitionEnvelopeValidationError):
        make_envelope(trace_id="   ")


def test_request_id_is_optional():
    """request_id may be unavailable."""
    envelope = make_envelope(request_id=None)

    assert envelope.request_id is None


# ---------------------------------------------------------------------------
# Failure information
# ---------------------------------------------------------------------------

def test_retry_status_can_carry_failure_context():
    """RETRY can preserve failure information for the next attempt."""
    envelope = make_envelope(
        status=AcquisitionStatus.RETRY,
        raw_payload=None,
        payload_hash=None,
        error_code="TIMEOUT",
        error_message="Source request timed out.",
        attempt_no=2,
        retry_count=1,
    )

    assert envelope.status is AcquisitionStatus.RETRY
    assert envelope.error_code == "TIMEOUT"
    assert envelope.error_message == "Source request timed out."
    assert envelope.attempt_no == 2
    assert envelope.retry_count == 1


def test_failed_status_can_carry_failure_context():
    """FAILED can preserve error information."""
    envelope = make_envelope(
        status=AcquisitionStatus.FAILED,
        raw_payload=None,
        payload_hash=None,
        error_code="AUTH_ERROR",
        error_message="Source authentication failed.",
    )

    assert envelope.status is AcquisitionStatus.FAILED
    assert envelope.error_code == "AUTH_ERROR"
    assert envelope.error_message == "Source authentication failed."


def test_degraded_status_can_carry_failure_context():
    """DEGRADED can preserve partial/impaired acquisition context."""
    envelope = make_envelope(
        status=AcquisitionStatus.DEGRADED,
        raw_payload=None,
        payload_hash=None,
        error_code="PARTIAL_SOURCE",
        error_message="Source returned incomplete data.",
    )

    assert envelope.status is AcquisitionStatus.DEGRADED
    assert envelope.error_code == "PARTIAL_SOURCE"


# ---------------------------------------------------------------------------
# Raw evidence preservation
# ---------------------------------------------------------------------------

def test_raw_payload_is_preserved_without_semantic_transformation():
    """The envelope must return the raw payload unchanged."""
    raw_payload = {
        "symbol": "XAUUSD",
        "price": 3850.25,
        "nested": {
            "provider_field": "original",
        },
        "items": [1, 2, 3],
    }

    envelope = make_envelope(
        raw_payload=raw_payload,
    )

    assert envelope.raw_payload == raw_payload
    assert envelope.raw_payload["nested"]["provider_field"] == "original"
    assert envelope.raw_payload["items"] == [1, 2, 3]


def test_non_success_status_does_not_require_payload_or_hash():
    """
    RETRY, FAILED, and DEGRADED outcomes may be represented without
    a successful raw payload/hash pair.
    """
    for status in (
        AcquisitionStatus.RETRY,
        AcquisitionStatus.FAILED,
        AcquisitionStatus.DEGRADED,
    ):
        envelope = make_envelope(
            status=status,
            raw_payload=None,
            payload_hash=None,
        )

        assert envelope.raw_payload is None
        assert envelope.payload_hash is None


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def test_to_dict_contains_all_contract_fields():
    """Serialization must include every AcquisitionEnvelope field."""
    envelope = make_envelope()

    result = envelope.to_dict()

    expected_keys = {
        "acquisition_id",
        "job_id",
        "source_id",
        "collector_type",
        "source_message_id",
        "source_sequence",
        "source_timestamp",
        "published_at",
        "acquired_at",
        "completed_at",
        "effective_at",
        "status",
        "attempt_no",
        "retry_count",
        "content_type",
        "encoding",
        "raw_payload",
        "payload_hash",
        "raw_size_bytes",
        "collector_version",
        "config_version",
        "trace_id",
        "request_id",
        "error_code",
        "error_message",
    }

    assert set(result.keys()) == expected_keys


def test_to_dict_serializes_status_as_string():
    """AcquisitionStatus must serialize to its contract value."""
    result = make_envelope().to_dict()

    assert result["status"] == "SUCCESS"


def test_to_dict_preserves_raw_payload():
    """Serialization must not semantically modify raw_payload."""
    raw_payload = {
        "symbol": "XAUUSD",
        "price": 3850.25,
    }

    result = make_envelope(
        raw_payload=raw_payload,
    ).to_dict()

    assert result["raw_payload"] == raw_payload


def test_to_dict_serializes_datetime_as_iso8601():
    """datetime timestamp values must serialize as ISO-8601 strings."""
    timestamp = datetime(
        2026,
        10,
        1,
        10,
        1,
        tzinfo=timezone.utc,
    )

    result = make_envelope(
        acquired_at=timestamp,
    ).to_dict()

    assert result["acquired_at"] == "2026-10-01T10:01:00+00:00"


def test_source_timestamp_string_representation_is_preserved():
    """
    A supplied ISO-8601 source timestamp string must remain unchanged.
    """
    timestamp = "2026-10-01T10:01:00Z"

    result = make_envelope(
        source_timestamp=timestamp,
    ).to_dict()

    assert result["source_timestamp"] == timestamp


# ---------------------------------------------------------------------------
# Contract immutability
# ---------------------------------------------------------------------------

def test_acquisition_envelope_is_immutable():
    """AcquisitionEnvelope is a frozen contract object."""
    envelope = make_envelope()

    with pytest.raises(AttributeError):
        envelope.status = AcquisitionStatus.FAILED


# ---------------------------------------------------------------------------
# Specification example
# ---------------------------------------------------------------------------

def test_specification_example_contract():
    """
    Verify the main AcquisitionEnvelope example values from the
    Developer 1 specification.
    """
    envelope = AcquisitionEnvelope(
        acquisition_id="ACQ-000001",
        job_id="JOB-000001",
        source_id="gold_api",
        collector_type="API",
        source_message_id=None,
        source_timestamp="2026-10-01T10:01:00Z",
        acquired_at="2026-10-01T10:01:01Z",
        completed_at="2026-10-01T10:01:01.200Z",
        status=AcquisitionStatus.SUCCESS,
        attempt_no=1,
        retry_count=0,
        content_type="application/json",
        encoding="UTF-8",
        raw_payload={
            "symbol": "XAUUSD",
            "price": 3850.25,
        },
        payload_hash="sha256:...",
        raw_size_bytes=42,
        collector_version="1.0.0",
        config_version=1,
        trace_id="TRACE-001",
        request_id="REQ-001",
        error_code=None,
        error_message=None,
    )

    result = envelope.to_dict()

    assert result["acquisition_id"] == "ACQ-000001"
    assert result["job_id"] == "JOB-000001"
    assert result["source_id"] == "gold_api"
    assert result["collector_type"] == "API"
    assert result["status"] == "SUCCESS"
    assert result["raw_payload"] == {
        "symbol": "XAUUSD",
        "price": 3850.25,
    }
    assert result["payload_hash"] == "sha256:..."
    assert result["trace_id"] == "TRACE-001"
