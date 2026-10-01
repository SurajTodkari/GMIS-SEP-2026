"""
MOD-001 Developer 1
D1-006 — Contract Validator Unit Tests

These tests verify the validator behavior defined in:
    MOD-001_DEV-01_Implementation_Specification_v1

Primary coverage:
    - SourceConfig validation
    - AcquisitionJob validation
    - AcquisitionEnvelope validation
    - Timestamp validation
    - Deterministic payload hashing
    - Payload hash verification
"""

import copy
import json

import pytest

from mod001.contracts.validators import (
    VALID_COLLECTOR_TYPES,
    VALID_ENVELOPE_STATUS,
    generate_payload_hash,
    validate_acquisition_envelope,
    validate_acquisition_job,
    validate_payload_hash,
    validate_source_config,
    validate_timestamp,
)


# ---------------------------------------------------------------------------
# Shared valid fixtures
# ---------------------------------------------------------------------------

VALID_SOURCE_CONFIG = {
    "source_id": "gold_api",
    "collector_type": "API",
    "enabled": True,
    "endpoint": "https://provider.example/gold",
    "auth_ref": "secret://gold-api-key",
    "request_parameters": {
        "symbol": "XAUUSD",
    },
    "timeout_ms": 5000,
    "retry_policy": {
        "max_attempts": 3,
    },
    "config_version": 1,
}


VALID_ACQUISITION_JOB = {
    "job_id": "JOB-000001",
    "source_id": "gold_api",
    "collector_type": "API",
    "schedule_id": "SCHEDULE-001",
    "attempt_no": 1,
    "created_at": "2026-10-01T10:00:00Z",
    "scheduled_for": "2026-10-01T10:01:00Z",
    "trace_id": "TRACE-001",
    "config_version": 1,
    "source_config_version": 1,
}


VALID_RAW_PAYLOAD = {
    "symbol": "XAUUSD",
    "price": 3850.25,
}


VALID_ACQUISITION_ENVELOPE = {
    "acquisition_id": "ACQ-000001",
    "job_id": "JOB-000001",
    "source_id": "gold_api",
    "collector_type": "API",
    "source_message_id": None,
    "source_timestamp": "2026-10-01T10:01:00Z",
    "acquired_at": "2026-10-01T10:01:01Z",
    "completed_at": "2026-10-01T10:01:01.200Z",
    "status": "SUCCESS",
    "attempt_no": 1,
    "retry_count": 0,
    "content_type": "application/json",
    "encoding": "UTF-8",
    "raw_payload": VALID_RAW_PAYLOAD,
    "payload_hash": generate_payload_hash(VALID_RAW_PAYLOAD),
    "raw_size_bytes": 42,
    "collector_version": "1.0.0",
    "config_version": 1,
    "trace_id": "TRACE-001",
    "request_id": "REQ-001",
    "error_code": None,
    "error_message": None,
}


# ---------------------------------------------------------------------------
# SourceConfig tests
# ---------------------------------------------------------------------------

def test_valid_source_config_is_accepted():
    result = validate_source_config(copy.deepcopy(VALID_SOURCE_CONFIG))

    assert result["valid"] is True
    assert result["error"] is None


def test_missing_source_id_is_rejected():
    source = copy.deepcopy(VALID_SOURCE_CONFIG)
    del source["source_id"]

    result = validate_source_config(source)

    assert result["valid"] is False
    assert "source_id" in result["error"]


def test_invalid_collector_type_is_rejected():
    source = copy.deepcopy(VALID_SOURCE_CONFIG)
    source["collector_type"] = "INVALID"

    result = validate_source_config(source)

    assert result["valid"] is False
    assert "collector_type" in result["error"]


def test_invalid_timeout_is_rejected():
    source = copy.deepcopy(VALID_SOURCE_CONFIG)
    source["timeout_ms"] = 0

    result = validate_source_config(source)

    assert result["valid"] is False
    assert "timeout_ms" in result["error"]


@pytest.mark.parametrize("collector_type", sorted(VALID_COLLECTOR_TYPES))
def test_supported_collector_types_are_accepted(collector_type):
    source = copy.deepcopy(VALID_SOURCE_CONFIG)
    source["collector_type"] = collector_type

    result = validate_source_config(source)

    assert result["valid"] is True


def test_non_boolean_enabled_is_rejected():
    source = copy.deepcopy(VALID_SOURCE_CONFIG)
    source["enabled"] = "true"

    result = validate_source_config(source)

    assert result["valid"] is False
    assert "enabled" in result["error"]


def test_missing_retry_policy_is_rejected():
    source = copy.deepcopy(VALID_SOURCE_CONFIG)
    del source["retry_policy"]

    result = validate_source_config(source)

    assert result["valid"] is False
    assert "retry_policy" in result["error"]


def test_missing_retry_policy_max_attempts_is_rejected():
    source = copy.deepcopy(VALID_SOURCE_CONFIG)
    source["retry_policy"] = {}

    result = validate_source_config(source)

    assert result["valid"] is False
    assert "max_attempts" in result["error"]


def test_invalid_config_version_is_rejected():
    source = copy.deepcopy(VALID_SOURCE_CONFIG)
    source["config_version"] = 0

    result = validate_source_config(source)

    assert result["valid"] is False
    assert "config_version" in result["error"]


# ---------------------------------------------------------------------------
# AcquisitionJob tests
# ---------------------------------------------------------------------------

def test_valid_acquisition_job_is_accepted():
    result = validate_acquisition_job(copy.deepcopy(VALID_ACQUISITION_JOB))

    assert result["valid"] is True
    assert result["error"] is None


def test_missing_trace_id_rejects_job():
    job = copy.deepcopy(VALID_ACQUISITION_JOB)
    del job["trace_id"]

    result = validate_acquisition_job(job)

    assert result["valid"] is False
    assert "trace_id" in result["error"]


def test_attempt_number_must_be_at_least_one():
    job = copy.deepcopy(VALID_ACQUISITION_JOB)
    job["attempt_no"] = 0

    result = validate_acquisition_job(job)

    assert result["valid"] is False
    assert "attempt_no" in result["error"]


def test_invalid_job_collector_type_is_rejected():
    job = copy.deepcopy(VALID_ACQUISITION_JOB)
    job["collector_type"] = "INVALID"

    result = validate_acquisition_job(job)

    assert result["valid"] is False
    assert "collector_type" in result["error"]


def test_invalid_job_config_version_is_rejected():
    job = copy.deepcopy(VALID_ACQUISITION_JOB)
    job["config_version"] = 0

    result = validate_acquisition_job(job)

    assert result["valid"] is False
    assert "config_version" in result["error"]


# ---------------------------------------------------------------------------
# AcquisitionEnvelope tests
# ---------------------------------------------------------------------------

def test_valid_success_envelope_is_accepted():
    envelope = copy.deepcopy(VALID_ACQUISITION_ENVELOPE)

    result = validate_acquisition_envelope(envelope)

    assert result["valid"] is True
    assert result["error"] is None


def test_success_envelope_without_raw_payload_is_rejected():
    envelope = copy.deepcopy(VALID_ACQUISITION_ENVELOPE)
    envelope["raw_payload"] = None

    result = validate_acquisition_envelope(envelope)

    assert result["valid"] is False
    assert "raw_payload" in result["error"]


def test_success_envelope_without_hash_is_rejected():
    envelope = copy.deepcopy(VALID_ACQUISITION_ENVELOPE)
    envelope["payload_hash"] = None

    result = validate_acquisition_envelope(envelope)

    assert result["valid"] is False
    assert "payload_hash" in result["error"]


def test_invalid_envelope_status_is_rejected():
    envelope = copy.deepcopy(VALID_ACQUISITION_ENVELOPE)
    envelope["status"] = "INVALID"

    result = validate_acquisition_envelope(envelope)

    assert result["valid"] is False
    assert "status" in result["error"]


@pytest.mark.parametrize("status", sorted(VALID_ENVELOPE_STATUS))
def test_supported_envelope_status_values_are_recognized(status):
    envelope = copy.deepcopy(VALID_ACQUISITION_ENVELOPE)
    envelope["status"] = status

    # Only SUCCESS requires payload + hash in the current validator.
    if status != "SUCCESS":
        envelope.pop("raw_payload", None)
        envelope.pop("payload_hash", None)

    result = validate_acquisition_envelope(envelope)

    assert result["valid"] is True


def test_invalid_envelope_collector_type_is_rejected():
    envelope = copy.deepcopy(VALID_ACQUISITION_ENVELOPE)
    envelope["collector_type"] = "INVALID"

    result = validate_acquisition_envelope(envelope)

    assert result["valid"] is False
    assert "collector_type" in result["error"]


def test_malformed_timestamp_is_rejected():
    envelope = copy.deepcopy(VALID_ACQUISITION_ENVELOPE)
    envelope["acquired_at"] = "not-a-timestamp"

    result = validate_acquisition_envelope(envelope)

    assert result["valid"] is False
    assert "acquired_at" in result["error"]


# ---------------------------------------------------------------------------
# Timestamp tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-10-01T10:00:00Z",
        "2026-10-01T10:00:00+00:00",
        "2026-10-01T10:00:00.200Z",
        "2026-10-01T10:00:00.200+05:30",
    ],
)
def test_valid_timestamps_are_accepted(timestamp):
    assert validate_timestamp(timestamp) is True


@pytest.mark.parametrize(
    "timestamp",
    [
        "",
        "not-a-timestamp",
        "2026-99-99T99:99:99Z",
    ],
)
def test_invalid_timestamps_are_rejected(timestamp):
    assert validate_timestamp(timestamp) is False


# ---------------------------------------------------------------------------
# Hashing / integrity tests
# ---------------------------------------------------------------------------

def test_same_payload_produces_same_deterministic_hash():
    payload = {"symbol": "XAUUSD", "price": 3850.25}

    first_hash = generate_payload_hash(payload)
    second_hash = generate_payload_hash(payload)

    assert first_hash == second_hash
    assert first_hash.startswith("sha256:")


def test_changed_payload_produces_different_hash():
    original = {"symbol": "XAUUSD", "price": 3850.25}
    changed = {"symbol": "XAUUSD", "price": 3851.25}

    original_hash = generate_payload_hash(original)
    changed_hash = generate_payload_hash(changed)

    assert original_hash != changed_hash


def test_payload_hash_validation_accepts_matching_hash():
    payload = {"symbol": "XAUUSD", "price": 3850.25}
    expected_hash = generate_payload_hash(payload)

    result = validate_payload_hash(payload, expected_hash)

    assert result["valid"] is True
    assert result["error"] is None


def test_payload_hash_validation_rejects_mismatch():
    payload = {"symbol": "XAUUSD", "price": 3850.25}
    incorrect_hash = "sha256:" + ("0" * 64)

    result = validate_payload_hash(payload, incorrect_hash)

    assert result["valid"] is False
    assert "mismatch" in result["error"].lower()


def test_payload_key_order_does_not_change_canonical_hash():
    payload_a = {
        "symbol": "XAUUSD",
        "price": 3850.25,
    }

    payload_b = {
        "price": 3850.25,
        "symbol": "XAUUSD",
    }

    assert generate_payload_hash(payload_a) == generate_payload_hash(payload_b)


# ---------------------------------------------------------------------------
# Contract serialization round-trip
# ---------------------------------------------------------------------------

def test_envelope_json_serialization_round_trip_preserves_data():
    envelope = copy.deepcopy(VALID_ACQUISITION_ENVELOPE)

    serialized = json.dumps(
        envelope,
        sort_keys=True,
        separators=(",", ":"),
    )

    restored = json.loads(serialized)

    assert restored == envelope
