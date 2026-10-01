"""
MOD-001 Developer 1
D1-012 — Contract Fixture Tests

These tests exercise the D1-011 fixtures against the stable contract
validators and D1-008 exact-byte hashing behavior.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mod001.contracts.validators import (
    validate_acquisition_envelope,
    validate_acquisition_job,
    validate_source_config,
)
from mod001.evidence.hashing import generate_sha256


FIXTURES_DIR = (
    Path(__file__).resolve().parents[2] / "fixtures"
)


def load_json_fixture(name: str) -> dict:
    path = FIXTURES_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "fixture_name",
    [
        "source_valid_api.json",
        "source_valid_rss.json",
        "source_valid_browser.json",
        "source_valid_websocket.json",
    ],
)
def test_valid_source_fixtures_are_accepted(fixture_name):
    source = load_json_fixture(fixture_name)

    result = validate_source_config(source)

    assert result["valid"] is True, result


def test_invalid_source_fixture_is_rejected():
    source = load_json_fixture("source_invalid.json")

    result = validate_source_config(source)

    assert result["valid"] is False
    assert result["error"]


def test_valid_job_fixture_is_accepted():
    job = load_json_fixture("job_valid.json")

    result = validate_acquisition_job(job)

    assert result["valid"] is True, result


def test_invalid_job_fixture_is_rejected():
    job = load_json_fixture("job_invalid.json")

    result = validate_acquisition_job(job)

    assert result["valid"] is False
    assert result["error"]


def test_success_envelope_fixture_is_accepted():
    envelope = load_json_fixture("envelope_success.json")

    result = validate_acquisition_envelope(envelope)

    assert result["valid"] is True, result


@pytest.mark.parametrize(
    "fixture_name",
    [
        "envelope_retry.json",
        "envelope_failed.json",
        "envelope_degraded.json",
    ],
)
def test_non_success_envelope_fixtures_are_accepted(fixture_name):
    envelope = load_json_fixture(fixture_name)

    result = validate_acquisition_envelope(envelope)

    assert result["valid"] is True, result


def test_envelope_statuses_are_complete():
    statuses = {
        load_json_fixture("envelope_success.json")["status"],
        load_json_fixture("envelope_retry.json")["status"],
        load_json_fixture("envelope_failed.json")["status"],
        load_json_fixture("envelope_degraded.json")["status"],
    }

    assert statuses == {
        "SUCCESS",
        "RETRY",
        "FAILED",
        "DEGRADED",
    }


def test_payload_sample_can_be_hashed_as_exact_file_bytes():
    path = FIXTURES_DIR / "payload_sample.json"
    raw_bytes = path.read_bytes()

    payload_hash = generate_sha256(raw_bytes)

    assert payload_hash.startswith("sha256:")
    assert len(payload_hash) == len("sha256:") + 64


def test_payload_sample_hash_is_deterministic():
    path = FIXTURES_DIR / "payload_sample.json"
    raw_bytes = path.read_bytes()

    first = generate_sha256(raw_bytes)
    second = generate_sha256(raw_bytes)

    assert first == second


def test_payload_sample_whitespace_is_part_of_raw_representation(
    tmp_path: Path,
):
    path = FIXTURES_DIR / "payload_sample.json"
    original = path.read_bytes()
    changed = original.replace(
        b'"price": 3850.25',
        b'"price":    3850.25',
    )

    original_hash = generate_sha256(original)
    changed_hash = generate_sha256(changed)

    assert original_hash != changed_hash


def test_fixture_directory_contains_all_required_files():
    required_files = {
        "source_valid_api.json",
        "source_valid_rss.json",
        "source_valid_browser.json",
        "source_valid_websocket.json",
        "source_invalid.json",
        "job_valid.json",
        "job_invalid.json",
        "envelope_success.json",
        "envelope_retry.json",
        "envelope_failed.json",
        "envelope_degraded.json",
        "payload_sample.json",
    }

    actual_files = {
        path.name
        for path in FIXTURES_DIR.iterdir()
        if path.is_file()
    }

    assert required_files.issubset(actual_files)
