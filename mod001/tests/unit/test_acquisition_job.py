"""
MOD-001 — Developer 1
D1-004: AcquisitionJob Tests

Coverage:
    - Valid AcquisitionJob creation
    - Required identity fields
    - Collector type validation
    - attempt_no validation
    - Timestamp validation
    - Traceability/version validation
    - ISO-8601 serialization
    - Support for all architecture collector types

The tests follow the AcquisitionJob contract defined in the
Developer 1 implementation specification.
"""

import pytest
from datetime import datetime, timezone

from mod001.contracts.acquisition_job import (
    AcquisitionJob,
    AcquisitionJobValidationError,
)
from mod001.contracts.source_config import CollectorType


def make_job(**overrides) -> AcquisitionJob:
    """Create a valid baseline AcquisitionJob."""
    data = {
        "job_id": "JOB-000001",
        "source_id": "gold_api",
        "collector_type": CollectorType.API,
        "schedule_id": "SCHEDULE-001",
        "attempt_no": 1,
        "created_at": "2026-10-01T10:00:00Z",
        "scheduled_for": "2026-10-01T10:01:00Z",
        "trace_id": "TRACE-001",
        "config_version": 1,
        "source_config_version": 1,
    }

    data.update(overrides)
    return AcquisitionJob(**data)


# ---------------------------------------------------------------------------
# D1-T05 — Create valid AcquisitionJob
# ---------------------------------------------------------------------------

def test_d1_t05_valid_acquisition_job():
    """A valid AcquisitionJob must be accepted."""
    job = make_job()

    assert job.job_id == "JOB-000001"
    assert job.source_id == "gold_api"
    assert job.collector_type is CollectorType.API
    assert job.schedule_id == "SCHEDULE-001"
    assert job.attempt_no == 1
    assert job.trace_id == "TRACE-001"
    assert job.config_version == 1
    assert job.source_config_version == 1


# ---------------------------------------------------------------------------
# D1-T06 — Missing trace_id
# ---------------------------------------------------------------------------

def test_d1_t06_missing_trace_id():
    """A missing trace_id must be rejected."""
    with pytest.raises(AcquisitionJobValidationError):
        make_job(trace_id=None)


def test_blank_trace_id_rejected():
    """A blank trace_id must be rejected."""
    with pytest.raises(AcquisitionJobValidationError):
        make_job(trace_id="   ")


# ---------------------------------------------------------------------------
# Required identity fields
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "field_name",
    [
        "job_id",
        "source_id",
        "schedule_id",
        "trace_id",
    ],
)
def test_required_string_fields_reject_blank_values(field_name):
    """Required string fields must not accept blank values."""
    with pytest.raises(AcquisitionJobValidationError):
        make_job(**{field_name: "   "})


@pytest.mark.parametrize(
    "field_name",
    [
        "job_id",
        "source_id",
        "schedule_id",
        "trace_id",
    ],
)
def test_required_string_fields_reject_non_strings(field_name):
    """Required string fields must contain strings."""
    with pytest.raises(AcquisitionJobValidationError):
        make_job(**{field_name: 123})


# ---------------------------------------------------------------------------
# Collector type
# ---------------------------------------------------------------------------

def test_invalid_collector_type_rejected():
    """An unsupported collector type must be rejected."""
    with pytest.raises(AcquisitionJobValidationError):
        make_job(collector_type="INVALID")


@pytest.mark.parametrize(
    "collector_type",
    [
        CollectorType.API,
        CollectorType.BROWSER,
        CollectorType.RSS,
        CollectorType.WEBSOCKET,
    ],
)
def test_all_architecture_collector_types_supported(collector_type):
    """
    All four collector types represented in the architecture must be
    supported by AcquisitionJob.
    """
    job = make_job(
        collector_type=collector_type,
    )

    assert job.collector_type is collector_type


# ---------------------------------------------------------------------------
# Attempt number
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
    with pytest.raises(AcquisitionJobValidationError):
        make_job(attempt_no=attempt_no)


@pytest.mark.parametrize(
    "attempt_no",
    [
        1,
        2,
        3,
        10,
    ],
)
def test_valid_attempt_numbers_accepted(attempt_no):
    """Positive attempt numbers must be accepted."""
    job = make_job(attempt_no=attempt_no)

    assert job.attempt_no == attempt_no


def test_boolean_attempt_number_rejected():
    """bool must not be accepted as an integer attempt number."""
    with pytest.raises(AcquisitionJobValidationError):
        make_job(attempt_no=True)


# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------

def test_timestamp_strings_are_parsed():
    """ISO-8601 timestamp strings must be parsed into datetimes."""
    job = make_job()

    assert isinstance(job.created_at, datetime)
    assert isinstance(job.scheduled_for, datetime)


def test_z_timestamps_are_timezone_aware():
    """Z timestamps must produce timezone-aware datetime values."""
    job = make_job()

    assert job.created_at.tzinfo is not None
    assert job.scheduled_for.tzinfo is not None


def test_datetime_timestamps_are_accepted():
    """datetime inputs must be accepted."""
    created_at = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
    scheduled_for = datetime(2026, 10, 1, 10, 1, tzinfo=timezone.utc)

    job = make_job(
        created_at=created_at,
        scheduled_for=scheduled_for,
    )

    assert job.created_at == created_at
    assert job.scheduled_for == scheduled_for


def test_naive_datetime_is_normalized_to_utc():
    """A naive datetime is assigned UTC for contract consistency."""
    created_at = datetime(2026, 10, 1, 10, 0)
    scheduled_for = datetime(2026, 10, 1, 10, 1)

    job = make_job(
        created_at=created_at,
        scheduled_for=scheduled_for,
    )

    assert job.created_at.tzinfo == timezone.utc
    assert job.scheduled_for.tzinfo == timezone.utc


@pytest.mark.parametrize(
    "field_name",
    [
        "created_at",
        "scheduled_for",
    ],
)
def test_malformed_timestamp_rejected(field_name):
    """
    Malformed timestamps must be rejected.

    This corresponds to the temporal validation requirement in the
    Developer 1 specification.
    """
    with pytest.raises(AcquisitionJobValidationError):
        make_job(**{field_name: "not-a-timestamp"})


@pytest.mark.parametrize(
    "field_name",
    [
        "created_at",
        "scheduled_for",
    ],
)
def test_empty_timestamp_rejected(field_name):
    """Empty timestamp strings must be rejected."""
    with pytest.raises(AcquisitionJobValidationError):
        make_job(**{field_name: "   "})


# ---------------------------------------------------------------------------
# Version fields
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "field_name",
    [
        "config_version",
        "source_config_version",
    ],
)
def test_version_must_be_at_least_one(field_name):
    """Configuration versions must be >= 1."""
    with pytest.raises(AcquisitionJobValidationError):
        make_job(**{field_name: 0})


@pytest.mark.parametrize(
    "field_name",
    [
        "config_version",
        "source_config_version",
    ],
)
def test_version_negative_value_rejected(field_name):
    """Negative configuration versions must be rejected."""
    with pytest.raises(AcquisitionJobValidationError):
        make_job(**{field_name: -1})


def test_boolean_version_rejected():
    """bool must not be accepted as a version number."""
    with pytest.raises(AcquisitionJobValidationError):
        make_job(config_version=True)


def test_source_config_version_traceability():
    """source_config_version must remain explicitly traceable."""
    job = make_job(
        config_version=7,
        source_config_version=12,
    )

    assert job.config_version == 7
    assert job.source_config_version == 12


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def test_to_dict_contains_all_contract_fields():
    """Serialization must contain every AcquisitionJob contract field."""
    job = make_job()

    result = job.to_dict()

    expected_keys = {
        "job_id",
        "source_id",
        "collector_type",
        "schedule_id",
        "attempt_no",
        "created_at",
        "scheduled_for",
        "trace_id",
        "config_version",
        "source_config_version",
    }

    assert set(result.keys()) == expected_keys


def test_to_dict_serializes_collector_type_as_string():
    """CollectorType must serialize to its architecture value."""
    result = make_job().to_dict()

    assert result["collector_type"] == "API"


def test_to_dict_serializes_timestamps_as_iso8601():
    """Datetime fields must serialize as ISO-8601 strings."""
    result = make_job().to_dict()

    assert result["created_at"] == "2026-10-01T10:00:00+00:00"
    assert result["scheduled_for"] == "2026-10-01T10:01:00+00:00"


# ---------------------------------------------------------------------------
# Contract immutability
# ---------------------------------------------------------------------------

def test_acquisition_job_is_immutable():
    """
    AcquisitionJob is a frozen dataclass and therefore acts as an
    immutable contract object after creation.
    """
    job = make_job()

    with pytest.raises(AttributeError):
        job.attempt_no = 2


# ---------------------------------------------------------------------------
# Contract example from the specification
# ---------------------------------------------------------------------------

def test_specification_example_contract():
    """
    Verify the field values represented by the AcquisitionJob example
    in the Developer 1 specification.
    """
    job = AcquisitionJob(
        job_id="JOB-000001",
        source_id="gold_api",
        collector_type=CollectorType.API,
        schedule_id="SCHEDULE-001",
        attempt_no=1,
        created_at="2026-10-01T10:00:00Z",
        scheduled_for="2026-10-01T10:01:00Z",
        trace_id="TRACE-001",
        config_version=1,
        source_config_version=1,
    )

    assert job.to_dict() == {
        "job_id": "JOB-000001",
        "source_id": "gold_api",
        "collector_type": "API",
        "schedule_id": "SCHEDULE-001",
        "attempt_no": 1,
        "created_at": "2026-10-01T10:00:00+00:00",
        "scheduled_for": "2026-10-01T10:01:00+00:00",
        "trace_id": "TRACE-001",
        "config_version": 1,
        "source_config_version": 1,
    }
