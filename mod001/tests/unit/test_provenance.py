"""
MOD-001 Developer 1
D1-009 — Provenance Metadata Unit Tests

Coverage:
    - Source identity
    - Collector identity/version
    - Configuration versioning
    - Job and tracing metadata
    - Timestamp preservation
    - acquired_at system-clock behavior
    - No silent effective_at inference
    - No invented processed_at
    - Envelope attachment
    - Envelope reconstruction
    - Validation and serialization behavior
"""

from datetime import datetime, timezone

import pytest

from mod001.evidence.provenance import (
    ProvenanceMetadata,
    attach_provenance,
    create_provenance,
    provenance_from_envelope,
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


BASE_PROVENANCE_KWARGS = {
    "source_id": "gold_api",
    "collector_type": "API",
    "collector_version": "1.0.0",
    "config_version": 1,
    "source_config_version": 1,
    "job_id": "JOB-000001",
    "trace_id": "TRACE-001",
    "request_id": "REQ-001",
    "schedule_id": "SCHEDULE-001",
    "attempt_no": 1,
    "source_timestamp": "2026-10-01T10:01:00Z",
    "published_at": "2026-10-01T10:00:59Z",
    "acquired_at": ACQUIRED_AT,
    "completed_at": "2026-10-01T10:01:01.200Z",
    "effective_at": "2026-10-01T10:01:00Z",
}


def make_provenance(**overrides):
    values = dict(BASE_PROVENANCE_KWARGS)
    values.update(overrides)
    return ProvenanceMetadata(**values)


# ---------------------------------------------------------------------------
# Basic provenance creation
# ---------------------------------------------------------------------------

def test_valid_provenance_is_created():
    provenance = make_provenance()

    assert provenance.source_id == "gold_api"
    assert provenance.collector_type == "API"
    assert provenance.collector_version == "1.0.0"
    assert provenance.config_version == 1
    assert provenance.source_config_version == 1


def test_job_and_trace_metadata_are_preserved():
    provenance = make_provenance()

    assert provenance.job_id == "JOB-000001"
    assert provenance.schedule_id == "SCHEDULE-001"
    assert provenance.attempt_no == 1
    assert provenance.trace_id == "TRACE-001"
    assert provenance.request_id == "REQ-001"


# ---------------------------------------------------------------------------
# Temporal correctness
# ---------------------------------------------------------------------------

def test_source_timestamp_is_preserved_exactly():
    value = "2026-10-01T10:01:00.123456Z"

    provenance = make_provenance(
        source_timestamp=value,
    )

    assert provenance.source_timestamp == value


def test_published_at_is_preserved_exactly():
    value = "2026-10-01T10:00:59.987654Z"

    provenance = make_provenance(
        published_at=value,
    )

    assert provenance.published_at == value


def test_acquired_at_is_preserved_when_explicitly_supplied():
    provenance = make_provenance(
        acquired_at=ACQUIRED_AT,
    )

    assert provenance.acquired_at == ACQUIRED_AT


def test_completed_at_is_preserved_when_supplied():
    value = "2026-10-01T10:01:01.200Z"

    provenance = make_provenance(
        completed_at=value,
    )

    assert provenance.completed_at == value


def test_effective_at_is_preserved_when_supplied():
    value = "2026-10-01T10:02:00Z"

    provenance = make_provenance(
        effective_at=value,
    )

    assert provenance.effective_at == value


def test_missing_effective_at_is_not_inferred():
    provenance = make_provenance(
        effective_at=None,
    )

    assert provenance.effective_at is None


def test_processed_at_is_not_created():
    provenance = make_provenance()

    data = provenance.to_dict()

    assert "processed_at" not in data


def test_missing_source_timestamp_remains_missing():
    provenance = make_provenance(
        source_timestamp=None,
    )

    assert provenance.source_timestamp is None


def test_missing_published_at_remains_missing():
    provenance = make_provenance(
        published_at=None,
    )

    assert provenance.published_at is None


# ---------------------------------------------------------------------------
# System-clock acquisition time
# ---------------------------------------------------------------------------

def test_create_provenance_sets_acquired_at_when_not_supplied():
    provenance = create_provenance(
        source_id="gold_api",
        collector_type="API",
        collector_version="1.0.0",
        config_version=1,
        source_config_version=1,
        job_id="JOB-000001",
        trace_id="TRACE-001",
    )

    assert isinstance(provenance.acquired_at, datetime)
    assert provenance.acquired_at.tzinfo is not None
    assert provenance.acquired_at.tzinfo.utcoffset(
        provenance.acquired_at
    ) is not None


def test_create_provenance_preserves_explicit_acquired_at():
    provenance = create_provenance(
        source_id="gold_api",
        collector_type="API",
        collector_version="1.0.0",
        config_version=1,
        source_config_version=1,
        job_id="JOB-000001",
        trace_id="TRACE-001",
        acquired_at=ACQUIRED_AT,
    )

    assert provenance.acquired_at == ACQUIRED_AT


# ---------------------------------------------------------------------------
# Collector types
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "collector_type",
    ["API", "BROWSER", "RSS", "WEBSOCKET"],
)
def test_supported_collector_types_are_accepted(collector_type):
    provenance = make_provenance(
        collector_type=collector_type,
    )

    assert provenance.collector_type == collector_type


def test_invalid_collector_type_is_rejected():
    with pytest.raises(ValueError, match="Invalid collector_type"):
        make_provenance(
            collector_type="INVALID",
        )


# ---------------------------------------------------------------------------
# Required field validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("source_id", ""),
        ("job_id", ""),
        ("trace_id", ""),
        ("collector_version", ""),
    ],
)
def test_required_string_fields_reject_empty_values(field_name, value):
    with pytest.raises(ValueError):
        make_provenance(**{field_name: value})


def test_config_version_must_be_at_least_one():
    with pytest.raises(ValueError, match="config_version"):
        make_provenance(config_version=0)


def test_source_config_version_must_be_at_least_one():
    with pytest.raises(ValueError, match="source_config_version"):
        make_provenance(source_config_version=0)


def test_attempt_number_must_be_at_least_one():
    with pytest.raises(ValueError, match="attempt_no"):
        make_provenance(attempt_no=0)


def test_naive_acquired_at_is_rejected():
    naive = datetime(2026, 10, 1, 10, 1, 1)

    with pytest.raises(ValueError, match="timezone-aware"):
        make_provenance(acquired_at=naive)


def test_malformed_timestamp_is_rejected():
    with pytest.raises(
        ValueError,
        match="valid ISO-8601 timestamp",
    ):
        make_provenance(
            source_timestamp="not-a-timestamp",
        )


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def test_to_dict_contains_provenance_fields():
    provenance = make_provenance()

    data = provenance.to_dict()

    assert data["source_id"] == "gold_api"
    assert data["collector_type"] == "API"
    assert data["collector_version"] == "1.0.0"
    assert data["config_version"] == 1
    assert data["source_config_version"] == 1
    assert data["job_id"] == "JOB-000001"
    assert data["trace_id"] == "TRACE-001"
    assert data["request_id"] == "REQ-001"
    assert data["schedule_id"] == "SCHEDULE-001"


def test_to_dict_preserves_temporal_values_without_rewriting():
    provenance = make_provenance(
        source_timestamp="2026-10-01T10:01:00.123456Z",
        published_at="2026-10-01T10:00:59.123456Z",
        effective_at="2026-10-01T10:02:00.123456Z",
    )

    data = provenance.to_dict()

    assert data["source_timestamp"] == (
        "2026-10-01T10:01:00.123456Z"
    )
    assert data["published_at"] == (
        "2026-10-01T10:00:59.123456Z"
    )
    assert data["effective_at"] == (
        "2026-10-01T10:02:00.123456Z"
    )


# ---------------------------------------------------------------------------
# Envelope attachment
# ---------------------------------------------------------------------------

def test_attach_provenance_does_not_mutate_original_envelope():
    raw_payload = b'{"symbol":"XAUUSD","price":3850.25}'
    envelope = {
        "acquisition_id": "ACQ-000001",
        "raw_payload": raw_payload,
        "payload_hash": "sha256:example",
    }

    provenance = make_provenance()

    result = attach_provenance(
        envelope,
        provenance,
    )

    assert "provenance" not in envelope
    assert "provenance" in result


def test_attach_provenance_preserves_raw_payload_identity():
    raw_payload = b'{"symbol":"XAUUSD","price":3850.25}'
    envelope = {
        "raw_payload": raw_payload,
    }

    provenance = make_provenance()
    result = attach_provenance(envelope, provenance)

    assert result["raw_payload"] is raw_payload
    assert result["raw_payload"] == raw_payload


def test_attach_provenance_attaches_expected_values():
    envelope = {
        "acquisition_id": "ACQ-000001",
        "raw_payload": b"raw",
    }

    provenance = make_provenance(
        source_id="gold_api",
        trace_id="TRACE-999",
    )

    result = attach_provenance(
        envelope,
        provenance,
    )

    assert result["provenance"]["source_id"] == "gold_api"
    assert result["provenance"]["trace_id"] == "TRACE-999"
    assert result["provenance"]["config_version"] == 1


def test_attach_provenance_does_not_add_processed_at():
    envelope = {"raw_payload": b"raw"}
    provenance = make_provenance()

    result = attach_provenance(
        envelope,
        provenance,
    )

    assert "processed_at" not in result["provenance"]


# ---------------------------------------------------------------------------
# Reconstruction from envelope
# ---------------------------------------------------------------------------

def test_provenance_can_be_reconstructed_from_envelope():
    envelope = {
        "source_id": "gold_api",
        "collector_type": "API",
        "collector_version": "1.0.0",
        "config_version": 1,
        "source_config_version": 1,
        "job_id": "JOB-000001",
        "trace_id": "TRACE-001",
        "request_id": "REQ-001",
        "schedule_id": "SCHEDULE-001",
        "attempt_no": 1,
        "source_timestamp": "2026-10-01T10:01:00Z",
        "published_at": "2026-10-01T10:00:59Z",
        "acquired_at": ACQUIRED_AT,
        "completed_at": "2026-10-01T10:01:01.200Z",
        "effective_at": "2026-10-01T10:01:00Z",
    }

    provenance = provenance_from_envelope(envelope)

    assert provenance.source_id == "gold_api"
    assert provenance.job_id == "JOB-000001"
    assert provenance.trace_id == "TRACE-001"
    assert provenance.source_timestamp == (
        "2026-10-01T10:01:00Z"
    )
    assert provenance.effective_at == (
        "2026-10-01T10:01:00Z"
    )
    assert provenance.acquired_at == ACQUIRED_AT


def test_reconstruction_does_not_invent_effective_at():
    envelope = {
        "source_id": "gold_api",
        "collector_type": "API",
        "collector_version": "1.0.0",
        "config_version": 1,
        "source_config_version": 1,
        "job_id": "JOB-000001",
        "trace_id": "TRACE-001",
        "acquired_at": ACQUIRED_AT,
    }

    provenance = provenance_from_envelope(envelope)

    assert provenance.effective_at is None


def test_reconstruction_requires_core_provenance_fields():
    envelope = {
        "source_id": "gold_api",
        "collector_type": "API",
        "collector_version": "1.0.0",
    }

    with pytest.raises(
        ValueError,
        match="Missing required envelope provenance fields",
    ):
        provenance_from_envelope(envelope)


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------

def test_provenance_metadata_is_immutable():
    provenance = make_provenance()

    with pytest.raises(AttributeError):
        provenance.source_id = "other_source"
