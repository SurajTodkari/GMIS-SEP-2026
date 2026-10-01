"""
MOD-001 — Developer 1
D1-002: Source Registry

Purpose:
    Register, retrieve, list, update, and validate SourceConfig objects.

Architecture boundary:
    Source Registry provides the common source configuration foundation
    consumed by the acquisition/runtime components.

Out of scope for D1-002:
    - Collector implementation
    - Scheduler/runtime execution
    - Retry/backoff execution
    - Rate limiting
    - Raw evidence handling
    - Semantic normalization
    - Prediction/trading logic

Note:
    The Developer 1 specification defines the registry responsibilities
    but does not prescribe a persistence mechanism. This implementation
    uses an in-memory registry as the local foundation.
"""

from __future__ import annotations

from copy import deepcopy

from mod001.contracts.source_config import SourceConfig


class SourceRegistryError(Exception):
    """Base exception for Source Registry errors."""


class SourceAlreadyRegisteredError(SourceRegistryError):
    """Raised when a source_id is already registered."""


class SourceNotFoundError(SourceRegistryError):
    """Raised when a requested source_id is not registered."""


class InvalidSourceConfigError(SourceRegistryError):
    """Raised when the supplied configuration is invalid."""


class SourceRegistry:
    """
    Registry for validated SourceConfig instances.

    D1-002 responsibilities:
        1. Register a source
        2. Retrieve a source
        3. List registered sources
        4. Update a source
        5. Validate a source configuration
    """

    def __init__(self) -> None:
        self._sources: dict[str, SourceConfig] = {}

    @staticmethod
    def validate(source_config: SourceConfig) -> SourceConfig:
        """
        Validate and return a SourceConfig.

        SourceConfig is responsible for field-level validation.
        The registry ensures that only SourceConfig instances are accepted.
        """
        if not isinstance(source_config, SourceConfig):
            raise InvalidSourceConfigError(
                "source_config must be an instance of SourceConfig"
            )

        return source_config

    def register(self, source_config: SourceConfig) -> SourceConfig:
        """
        Register a new source configuration.

        Raises:
            InvalidSourceConfigError:
                Supplied object is not a SourceConfig.
            SourceAlreadyRegisteredError:
                source_id is already registered.
        """
        self.validate(source_config)

        source_id = source_config.source_id

        if source_id in self._sources:
            raise SourceAlreadyRegisteredError(
                f"Source '{source_id}' is already registered"
            )

        # Defensive copy prevents callers from changing nested dictionaries
        # after registration.
        stored_config = deepcopy(source_config)
        self._sources[source_id] = stored_config

        return deepcopy(stored_config)

    def get(self, source_id: str) -> SourceConfig:
        """
        Retrieve a registered source by source_id.

        Raises:
            SourceNotFoundError:
                source_id is not registered.
        """
        self._validate_source_id(source_id)

        if source_id not in self._sources:
            raise SourceNotFoundError(
                f"Source '{source_id}' is not registered"
            )

        return deepcopy(self._sources[source_id])

    def list_sources(self) -> list[SourceConfig]:
        """Return all registered source configurations."""
        return [
            deepcopy(source_config)
            for source_config in self._sources.values()
        ]

    def update(self, source_config: SourceConfig) -> SourceConfig:
        """
        Update an existing registered source.

        The source_id remains the registry key. No automatic configuration
        version increment is performed here; configuration version lifecycle
        belongs to D1-003.
        """
        self.validate(source_config)

        source_id = source_config.source_id

        if source_id not in self._sources:
            raise SourceNotFoundError(
                f"Source '{source_id}' is not registered"
            )

        stored_config = deepcopy(source_config)
        self._sources[source_id] = stored_config

        return deepcopy(stored_config)

    def count(self) -> int:
        """Return the number of registered sources."""
        return len(self._sources)

    @staticmethod
    def _validate_source_id(source_id: str) -> None:
        """Validate a source registry lookup key."""
        if not isinstance(source_id, str):
            raise ValueError("source_id must be a string")

        if not source_id.strip():
            raise ValueError("source_id must not be blank")


__all__ = [
    "InvalidSourceConfigError",
    "SourceAlreadyRegisteredError",
    "SourceNotFoundError",
    "SourceRegistry",
    "SourceRegistryError",
]
