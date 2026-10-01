"""
MOD-001 Developer 1
D1-010 — Foundation API

Purpose
-------
Expose the proposed internal MOD-001 foundation endpoints defined in the
Developer 1 implementation specification.

Important architectural boundary
---------------------------------
This API owns the acquisition foundation only. It does not perform:
    - semantic normalization
    - sentiment analysis
    - entity extraction
    - feature engineering
    - prediction
    - risk decisions
    - trade execution

The REST paths implemented here are the proposed Developer 1 endpoints from
Section 7 of the implementation specification.

Storage
-------
The included FoundationStore is intentionally an in-memory reference
implementation. It provides deterministic local behavior for development and
contract testing while keeping persistence behind a small service boundary.

A production implementation can replace FoundationStore with the project's
database/repository implementation without changing the HTTP contract.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from mod001.contracts.validators import (
    validate_acquisition_envelope,
    validate_acquisition_job,
    validate_source_config,
)
from mod001.evidence.hashing import generate_sha256


API_PREFIX = "/api/v1"


def _utc_now_iso() -> str:
    """Return current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


class ValidationResponse(BaseModel):
    """Consistent validator API response."""

    valid: bool
    error: str | None = None


class RegisterSourceResponse(BaseModel):
    """Response returned after successful source registration."""

    source_id: str
    status: str
    config_version: int


class SourceListResponse(BaseModel):
    """Response envelope for source listing."""

    sources: list[dict[str, Any]]


class VersionListResponse(BaseModel):
    """Response envelope for configuration version listing."""

    source_id: str
    versions: list[int]


class JobResponse(BaseModel):
    """Response envelope for AcquisitionJob creation/retrieval."""

    job: dict[str, Any]


class HashResponse(BaseModel):
    """Response returned by the evidence hashing endpoint."""

    payload_hash: str
    raw_size_bytes: int


class HealthResponse(BaseModel):
    """Foundation health response."""

    status: str = "OK"
    module: str = "MOD-001"
    component: str = "foundation-api"


class VersionCreateRequest(BaseModel):
    """
    Request used to explicitly create a source configuration version.

    The payload represents a new immutable configuration snapshot.
    `config_version` is assigned by the service and should not be supplied
    by the client.
    """

    configuration: dict[str, Any] = Field(default_factory=dict)


class FoundationStore:
    """
    Local reference store for Developer 1 foundation state.

    Data is copied on write/read to prevent accidental mutation of stored
    contracts by callers.
    """

    def __init__(self) -> None:
        self._sources: dict[str, dict[str, Any]] = {}
        self._versions: dict[str, dict[int, dict[str, Any]]] = {}
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    # ------------------------------------------------------------------
    # Source lifecycle
    # ------------------------------------------------------------------

    def register_source(self, config: dict[str, Any]) -> dict[str, Any]:
        source_id = str(config["source_id"])

        with self._lock:
            if source_id in self._sources:
                raise KeyError(f"Source already registered: {source_id}")

            stored_config = deepcopy(config)
            version = int(stored_config["config_version"])

            self._sources[source_id] = stored_config
            self._versions[source_id] = {
                version: deepcopy(stored_config)
            }

            return deepcopy(stored_config)

    def list_sources(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                deepcopy(source)
                for source in self._sources.values()
            ]

    def get_source(self, source_id: str) -> dict[str, Any] | None:
        with self._lock:
            source = self._sources.get(source_id)
            return deepcopy(source) if source is not None else None

    def update_source(
        self,
        source_id: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            current = self._sources.get(source_id)

            if current is None:
                raise KeyError(f"Source not found: {source_id}")

            if config["source_id"] != source_id:
                raise ValueError(
                    "source_id in request must match path source_id"
                )

            stored_config = deepcopy(config)
            version = int(stored_config["config_version"])
            current_version = int(current["config_version"])

            if version <= current_version:
                raise ValueError(
                    "config_version must be greater than the current "
                    f"version ({current_version})"
                )

            self._sources[source_id] = stored_config
            self._versions.setdefault(source_id, {})[version] = (
                deepcopy(stored_config)
            )

            return deepcopy(stored_config)

    # ------------------------------------------------------------------
    # Configuration versions
    # ------------------------------------------------------------------

    def create_version(
        self,
        source_id: str,
        configuration: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            current = self._sources.get(source_id)

            if current is None:
                raise KeyError(f"Source not found: {source_id}")

            next_version = (
                max(self._versions[source_id].keys()) + 1
            )

            versioned = deepcopy(configuration)
            versioned["source_id"] = source_id
            versioned["config_version"] = next_version

            # Validate before making the new immutable version visible.
            validation = validate_source_config(versioned)

            if not validation["valid"]:
                raise ValueError(validation["error"])

            self._versions[source_id][next_version] = deepcopy(versioned)

            # The newest valid version becomes the active configuration.
            self._sources[source_id] = deepcopy(versioned)

            return deepcopy(versioned)

    def list_versions(self, source_id: str) -> list[int] | None:
        with self._lock:
            if source_id not in self._sources:
                return None

            return sorted(self._versions[source_id].keys())

    def get_version(
        self,
        source_id: str,
        version: int,
    ) -> dict[str, Any] | None:
        with self._lock:
            source_versions = self._versions.get(source_id)

            if source_versions is None:
                return None

            configuration = source_versions.get(version)

            return (
                deepcopy(configuration)
                if configuration is not None
                else None
            )

    # ------------------------------------------------------------------
    # Acquisition jobs
    # ------------------------------------------------------------------

    def create_job(self, job: dict[str, Any]) -> dict[str, Any]:
        job_id = str(job["job_id"])

        with self._lock:
            if job_id in self._jobs:
                raise KeyError(f"Job already exists: {job_id}")

            stored_job = deepcopy(job)
            self._jobs[job_id] = stored_job

            return deepcopy(stored_job)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return deepcopy(job) if job is not None else None


class FoundationService:
    """
    Service layer coordinating validators and foundation state.

    Keeping these operations outside route functions makes it easier to
    replace the local store with a database-backed repository later.
    """

    def __init__(self, store: FoundationStore | None = None) -> None:
        self.store = store or FoundationStore()

    def validate_source(
        self,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        return validate_source_config(config)

    def register_source(
        self,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        validation = self.validate_source(config)

        if not validation["valid"]:
            raise ValueError(validation["error"])

        return self.store.register_source(config)

    def update_source(
        self,
        source_id: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        validation = self.validate_source(config)

        if not validation["valid"]:
            raise ValueError(validation["error"])

        return self.store.update_source(
            source_id,
            config,
        )

    def create_job(
        self,
        job: dict[str, Any],
    ) -> dict[str, Any]:
        validation = validate_acquisition_job(job)

        if not validation["valid"]:
            raise ValueError(validation["error"])

        if self.store.get_source(job["source_id"]) is None:
            raise ValueError(
                f"Source is not registered: {job['source_id']}"
            )

        source = self.store.get_source(job["source_id"])

        if source is not None:
            if job["source_config_version"] != source["config_version"]:
                raise ValueError(
                    "source_config_version does not match "
                    "the registered source configuration"
                )

        return self.store.create_job(job)

    def validate_envelope(
        self,
        envelope: dict[str, Any],
    ) -> dict[str, Any]:
        return validate_acquisition_envelope(envelope)

    def hash_request_body(self, raw_body: bytes) -> str:
        return generate_sha256(raw_body)


def create_foundation_router(
    service: FoundationService | None = None,
) -> APIRouter:
    """
    Create the MOD-001 foundation API router.

    Dependency injection is supported for tests and for production
    replacement of FoundationStore with a persistent implementation.
    """
    foundation_service = service or FoundationService()

    router = APIRouter(
        prefix=API_PREFIX,
        tags=["MOD-001 Foundation"],
    )

    # ------------------------------------------------------------------
    # Source Registry
    # ------------------------------------------------------------------

    @router.post(
        "/sources",
        response_model=RegisterSourceResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def register_source(
        config: dict[str, Any],
    ) -> RegisterSourceResponse:
        try:
            stored = foundation_service.register_source(config)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc

        return RegisterSourceResponse(
            source_id=stored["source_id"],
            status="REGISTERED",
            config_version=stored["config_version"],
        )

    @router.get(
        "/sources",
        response_model=SourceListResponse,
    )
    def list_sources() -> SourceListResponse:
        return SourceListResponse(
            sources=foundation_service.store.list_sources()
        )

    @router.get(
        "/sources/{source_id}",
    )
    def get_source(source_id: str) -> dict[str, Any]:
        source = foundation_service.store.get_source(source_id)

        if source is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source not found: {source_id}",
            )

        return source

    @router.put(
        "/sources/{source_id}",
    )
    def update_source(
        source_id: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            return foundation_service.update_source(
                source_id,
                config,
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    @router.post(
        "/sources/{source_id}/validate",
        response_model=ValidationResponse,
    )
    def validate_source(
        source_id: str,
    ) -> ValidationResponse:
        source = foundation_service.store.get_source(source_id)

        if source is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source not found: {source_id}",
            )

        result = foundation_service.validate_source(source)

        return ValidationResponse(**result)

    # ------------------------------------------------------------------
    # Configuration Versions
    # ------------------------------------------------------------------

    @router.post(
        "/sources/{source_id}/versions",
        status_code=status.HTTP_201_CREATED,
    )
    def create_source_version(
        source_id: str,
        request: VersionCreateRequest,
    ) -> dict[str, Any]:
        try:
            return foundation_service.store.create_version(
                source_id,
                request.configuration,
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    @router.get(
        "/sources/{source_id}/versions",
        response_model=VersionListResponse,
    )
    def list_source_versions(
        source_id: str,
    ) -> VersionListResponse:
        versions = foundation_service.store.list_versions(source_id)

        if versions is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source not found: {source_id}",
            )

        return VersionListResponse(
            source_id=source_id,
            versions=versions,
        )

    @router.get(
        "/sources/{source_id}/versions/{version}",
    )
    def get_source_version(
        source_id: str,
        version: int,
    ) -> dict[str, Any]:
        configuration = foundation_service.store.get_version(
            source_id,
            version,
        )

        if configuration is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Configuration version not found: "
                    f"{source_id}/v{version}"
                ),
            )

        return configuration

    # ------------------------------------------------------------------
    # AcquisitionJob
    # ------------------------------------------------------------------

    @router.post(
        "/jobs",
        response_model=JobResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_job(
        job: dict[str, Any],
    ) -> JobResponse:
        try:
            stored = foundation_service.create_job(job)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        return JobResponse(job=stored)

    @router.get(
        "/jobs/{job_id}",
        response_model=JobResponse,
    )
    def get_job(job_id: str) -> JobResponse:
        job = foundation_service.store.get_job(job_id)

        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job not found: {job_id}",
            )

        return JobResponse(job=job)

    # ------------------------------------------------------------------
    # AcquisitionEnvelope validation
    # ------------------------------------------------------------------

    @router.post(
        "/envelopes/validate",
        response_model=ValidationResponse,
    )
    def validate_envelope(
        envelope: dict[str, Any],
    ) -> ValidationResponse:
        result = foundation_service.validate_envelope(
            envelope
        )

        return ValidationResponse(**result)

    # ------------------------------------------------------------------
    # Evidence hashing
    # ------------------------------------------------------------------

    @router.post(
        "/evidence/hash",
        response_model=HashResponse,
    )
    async def hash_evidence(
        request: Request,
    ) -> HashResponse:
        """
        Hash the exact HTTP request bytes.

        The endpoint intentionally reads Request.body() instead of accepting
        a parsed JSON object. This preserves the D1-008 requirement that the
        hash be calculated over the exact raw representation.
        """
        raw_body = await request.body()

        return HashResponse(
            payload_hash=foundation_service.hash_request_body(
                raw_body
            ),
            raw_size_bytes=len(raw_body),
        )

    # ------------------------------------------------------------------
    # Foundation health
    # ------------------------------------------------------------------

    @router.get(
        "/health",
        response_model=HealthResponse,
    )
    def health() -> HealthResponse:
        return HealthResponse()

    return router


# Default router for application inclusion.
router = create_foundation_router()
