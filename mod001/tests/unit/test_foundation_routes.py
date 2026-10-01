"""
MOD-001 Developer 1
D1-010 — Foundation API Contract Tests

These tests verify the proposed internal API surface from the Developer 1
implementation specification.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mod001.api.foundation_routes import (
    FoundationService,
    FoundationStore,
    create_foundation_router,
)
from mod001.evidence.hashing import generate_sha256


VALID_SOURCE = {
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


VALID_JOB = {
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


VALID_ENVELOPE = {
    "acquisition_id": "ACQ-000001",
    "job_id": "JOB-000001",
    "source_id": "gold_api",
    "collector_type": "API",
    "source_timestamp": "2026-10-01T10:01:00Z",
    "acquired_at": "2026-10-01T10:01:01Z",
    "completed_at": "2026-10-01T10:01:01.200Z",
    "status": "SUCCESS",
    "attempt_no": 1,
    "retry_count": 0,
    "content_type": "application/json",
    "encoding": "UTF-8",
    "raw_payload": {
        "symbol": "XAUUSD",
        "price": 3850.25,
    },
    "payload_hash": "sha256:placeholder",
    "raw_size_bytes": 42,
    "collector_version": "1.0.0",
    "config_version": 1,
    "trace_id": "TRACE-001",
    "request_id": "REQ-001",
    "error_code": None,
    "error_message": None,
}


def build_client() -> TestClient:
    service = FoundationService(
        store=FoundationStore()
    )

    app = FastAPI()
    app.include_router(
        create_foundation_router(service)
    )

    return TestClient(app)


def test_health_endpoint():
    client = build_client()

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "OK"
    assert response.json()["module"] == "MOD-001"


def test_register_source():
    client = build_client()

    response = client.post(
        "/api/v1/sources",
        json=VALID_SOURCE,
    )

    assert response.status_code == 201
    body = response.json()

    assert body["source_id"] == "gold_api"
    assert body["status"] == "REGISTERED"
    assert body["config_version"] == 1


def test_register_duplicate_source_is_rejected():
    client = build_client()

    first = client.post(
        "/api/v1/sources",
        json=VALID_SOURCE,
    )
    second = client.post(
        "/api/v1/sources",
        json=VALID_SOURCE,
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_register_invalid_source_is_rejected():
    client = build_client()

    invalid_source = dict(VALID_SOURCE)
    invalid_source.pop("source_id")

    response = client.post(
        "/api/v1/sources",
        json=invalid_source,
    )

    assert response.status_code == 400


def test_list_sources():
    client = build_client()

    client.post(
        "/api/v1/sources",
        json=VALID_SOURCE,
    )

    response = client.get("/api/v1/sources")

    assert response.status_code == 200
    assert len(response.json()["sources"]) == 1
    assert response.json()["sources"][0]["source_id"] == "gold_api"


def test_get_source():
    client = build_client()

    client.post(
        "/api/v1/sources",
        json=VALID_SOURCE,
    )

    response = client.get(
        "/api/v1/sources/gold_api"
    )

    assert response.status_code == 200
    assert response.json()["source_id"] == "gold_api"


def test_get_missing_source_returns_404():
    client = build_client()

    response = client.get(
        "/api/v1/sources/not_registered"
    )

    assert response.status_code == 404


def test_update_source():
    client = build_client()

    client.post(
        "/api/v1/sources",
        json=VALID_SOURCE,
    )

    updated = dict(VALID_SOURCE)
    updated["timeout_ms"] = 7500
    updated["config_version"] = 2

    response = client.put(
        "/api/v1/sources/gold_api",
        json=updated,
    )

    assert response.status_code == 200
    assert response.json()["timeout_ms"] == 7500
    assert response.json()["config_version"] == 2


def test_validate_registered_source():
    client = build_client()

    client.post(
        "/api/v1/sources",
        json=VALID_SOURCE,
    )

    response = client.post(
        "/api/v1/sources/gold_api/validate"
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_create_source_version():
    client = build_client()

    client.post(
        "/api/v1/sources",
        json=VALID_SOURCE,
    )

    configuration = dict(VALID_SOURCE)
    configuration["timeout_ms"] = 10000
    configuration.pop("config_version")

    response = client.post(
        "/api/v1/sources/gold_api/versions",
        json={
            "configuration": configuration
        },
    )

    assert response.status_code == 201
    assert response.json()["source_id"] == "gold_api"
    assert response.json()["config_version"] == 2


def test_list_source_versions():
    client = build_client()

    client.post(
        "/api/v1/sources",
        json=VALID_SOURCE,
    )

    response = client.get(
        "/api/v1/sources/gold_api/versions"
    )

    assert response.status_code == 200
    assert response.json()["versions"] == [1]


def test_get_source_version():
    client = build_client()

    client.post(
        "/api/v1/sources",
        json=VALID_SOURCE,
    )

    response = client.get(
        "/api/v1/sources/gold_api/versions/1"
    )

    assert response.status_code == 200
    assert response.json()["config_version"] == 1


def test_create_job_from_registered_source():
    client = build_client()

    client.post(
        "/api/v1/sources",
        json=VALID_SOURCE,
    )

    response = client.post(
        "/api/v1/jobs",
        json=VALID_JOB,
    )

    assert response.status_code == 201
    assert response.json()["job"]["job_id"] == "JOB-000001"


def test_create_job_from_unknown_source_is_rejected():
    client = build_client()

    response = client.post(
        "/api/v1/jobs",
        json=VALID_JOB,
    )

    assert response.status_code == 400


def test_get_job():
    client = build_client()

    client.post(
        "/api/v1/sources",
        json=VALID_SOURCE,
    )
    client.post(
        "/api/v1/jobs",
        json=VALID_JOB,
    )

    response = client.get(
        "/api/v1/jobs/JOB-000001"
    )

    assert response.status_code == 200
    assert response.json()["job"]["source_id"] == "gold_api"


def test_validate_envelope():
    client = build_client()

    response = client.post(
        "/api/v1/envelopes/validate",
        json=VALID_ENVELOPE,
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_invalid_envelope_is_reported():
    client = build_client()

    invalid_envelope = dict(VALID_ENVELOPE)
    invalid_envelope["status"] = "INVALID"

    response = client.post(
        "/api/v1/envelopes/validate",
        json=invalid_envelope,
    )

    assert response.status_code == 200
    assert response.json()["valid"] is False


def test_evidence_hash_endpoint_hashes_exact_request_body():
    client = build_client()

    raw_body = b'{"symbol":"XAUUSD","price":3850.25}'

    response = client.post(
        "/api/v1/evidence/hash",
        content=raw_body,
        headers={
            "content-type": "application/json"
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["payload_hash"] == generate_sha256(raw_body)
    assert body["raw_size_bytes"] == len(raw_body)


def test_evidence_hash_changes_when_raw_bytes_change():
    client = build_client()

    first = client.post(
        "/api/v1/evidence/hash",
        content=b'{"price":3850.25}',
        headers={
            "content-type": "application/json"
        },
    )

    second = client.post(
        "/api/v1/evidence/hash",
        content=b'{"price":3850.26}',
        headers={
            "content-type": "application/json"
        },
    )

    assert first.json()["payload_hash"] != (
        second.json()["payload_hash"]
    )
