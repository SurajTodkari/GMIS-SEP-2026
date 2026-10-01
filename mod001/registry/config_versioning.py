"""
MOD-001 — Developer 1
D1-003: Configuration Versioning

Purpose:
    Provide explicit, deterministic configuration version handling for
    SourceConfig instances.

Architectural responsibilities:
    - Identify the current configuration version for a source.
    - Create the next explicit configuration version.
    - Preserve previous configuration versions.
    - Ensure each material configuration revision has an explicit version.
    - Keep configuration history traceable.

Out of scope:
    - Scheduler/runtime execution
    - Retry/backoff execution
    - Rate limiting
    - Collector implementation
    - AcquisitionJob execution
    - AcquisitionEnvelope creation
    - Semantic normalization
    - Prediction/trading logic

Design note:
    The Developer 1 specification requires explicit configuration
    versioning but does not prescribe a database/persistence technology.
    This implementation keeps version history in memory as the foundation
    contract. Persistence can be added by a higher-level component later
    without changing the versioning semantics.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from mod001.contracts.source_config import SourceConfig


class ConfigurationVersionError(Exception):
    """Base exception for configuration versioning errors."""


class ConfigurationVersionNotFoundError(ConfigurationVersionError):
    """Raised when a requested configuration version does not exist."""


class ConfigurationVersionConflictError(ConfigurationVersionError):
    """Raised when a supplied version conflicts with existing history."""


class SourceVersionHistory:
    """
    Immutable-style version history for a single source.

    The history stores SourceConfig objects keyed by their explicit
    config_version.
    """

    def __init__(self, source_id: str) -> None:
        if not isinstance(source_id, str):
            raise ValueError("source_id must be a string")

        if not source_id.strip():
            raise ValueError("source_id must not be blank")

        self.source_id = source_id
        self._versions: dict[int, SourceConfig] = {}

    def add(self, config: SourceConfig) -> SourceConfig:
        """
        Add an explicit configuration version to the history.

        Raises:
            ValueError:
                The configuration belongs to another source.
            ConfigurationVersionConflictError:
                The version already exists with different content.
        """
        _validate_source_config(config)

        if config.source_id != self.source_id:
            raise ValueError(
                f"Configuration source_id '{config.source_id}' does not "
                f"match history source_id '{self.source_id}'"
            )

        version = config.config_version

        existing = self._versions.get(version)

        if existing is not None:
            if existing.to_dict() != config.to_dict():
                raise ConfigurationVersionConflictError(
                    f"Version {version} already exists for source "
                    f"'{self.source_id}' with different configuration"
                )

            return deepcopy(existing)

        stored = deepcopy(config)
        self._versions[version] = stored

        return deepcopy(stored)

    def get(self, version: int) -> SourceConfig:
        """Return a specific configuration version."""
        _validate_version(version)

        if version not in self._versions:
            raise ConfigurationVersionNotFoundError(
                f"Version {version} not found for source '{self.source_id}'"
            )

        return deepcopy(self._versions[version])

    def current(self) -> SourceConfig:
        """Return the highest registered configuration version."""
        if not self._versions:
            raise ConfigurationVersionNotFoundError(
                f"No configuration versions registered for source "
                f"'{self.source_id}'"
            )

        current_version = max(self._versions)
        return deepcopy(self._versions[current_version])

    def versions(self) -> list[int]:
        """Return registered configuration versions in ascending order."""
        return sorted(self._versions)

    def count(self) -> int:
        """Return the number of stored configuration versions."""
        return len(self._versions)


@dataclass
class ConfigurationVersionStore:
    """
    Foundation store for configuration version histories.

    Each source has an independent version sequence. A material
    configuration revision receives an explicit version and previous
    versions remain available for traceability.
    """

    _histories: dict[str, SourceVersionHistory]

    def __init__(self) -> None:
        self._histories = {}

    def register_initial(self, config: SourceConfig) -> SourceConfig:
        """
        Register the initial configuration version.

        The supplied SourceConfig must carry an explicit version.
        This method does not silently assign one.
        """
        _validate_source_config(config)

        history = self._history_for(config.source_id)

        if history.count() > 0:
            raise ConfigurationVersionConflictError(
                f"Initial configuration already exists for source "
                f"'{config.source_id}'"
            )

        return history.add(config)

    def create_new_version(
        self,
        config: SourceConfig,
    ) -> SourceConfig:
        """
        Create the next explicit configuration version.

        The caller supplies the changed configuration content. The store
        assigns the next version number for that source.

        Example:
            Version 1 -> material change -> Version 2
        """
        _validate_source_config(config)

        history = self._history_for(config.source_id)

        if history.count() == 0:
            raise ConfigurationVersionError(
                f"Cannot create a new version before an initial "
                f"configuration exists for source '{config.source_id}'"
            )

        current = history.current()
        next_version = current.config_version + 1

        versioned_config = _replace_config_version(
            config,
            config_version=next_version,
        )

        return history.add(versioned_config)

    def register_explicit_version(
        self,
        config: SourceConfig,
    ) -> SourceConfig:
        """
        Register a configuration with an explicitly supplied version.

        This is useful when loading an existing versioned configuration
        history or restoring known configuration state.
        """
        _validate_source_config(config)

        history = self._history_for(config.source_id)
        return history.add(config)

    def get_version(
        self,
        source_id: str,
        version: int,
    ) -> SourceConfig:
        """Retrieve a specific configuration version."""
        history = self._get_history(source_id)
        return history.get(version)

    def get_current(
        self,
        source_id: str,
    ) -> SourceConfig:
        """Retrieve the highest registered version for a source."""
        history = self._get_history(source_id)
        return history.current()

    def list_versions(
        self,
        source_id: str,
    ) -> list[int]:
        """Return all registered versions for a source."""
        history = self._get_history(source_id)
        return history.versions()

    def count_versions(
        self,
        source_id: str,
    ) -> int:
        """Return the number of registered versions for a source."""
        history = self._get_history(source_id)
        return history.count()

    def _history_for(self, source_id: str) -> SourceVersionHistory:
        """Get or create the version history for a source."""
        if source_id not in self._histories:
            self._histories[source_id] = SourceVersionHistory(source_id)

        return self._histories[source_id]

    def _get_history(self, source_id: str) -> SourceVersionHistory:
        """Get an existing source history or raise a clear error."""
        _validate_source_id(source_id)

        if source_id not in self._histories:
            raise ConfigurationVersionNotFoundError(
                f"No configuration history exists for source '{source_id}'"
            )

        return self._histories[source_id]


def _replace_config_version(
    config: SourceConfig,
    *,
    config_version: int,
) -> SourceConfig:
    """
    Create a new SourceConfig with a different explicit version.

    SourceConfig is intentionally treated as immutable by this component.
    """
    data: Mapping[str, Any] = config.to_dict()

    data = dict(data)
    data["collector_type"] = config.collector_type
    data["retry_policy"] = (
        deepcopy(config.retry_policy)
        if config.retry_policy is not None
        else None
    )
    data["request_parameters"] = (
        deepcopy(config.request_parameters)
        if config.request_parameters is not None
        else None
    )
    data["config_version"] = config_version

    return SourceConfig(**data)


def _validate_source_config(config: SourceConfig) -> None:
    """Validate that the supplied object is a SourceConfig."""
    if not isinstance(config, SourceConfig):
        raise ValueError(
            "config must be an instance of SourceConfig"
        )


def _validate_source_id(source_id: str) -> None:
    """Validate source_id used by store lookup methods."""
    if not isinstance(source_id, str):
        raise ValueError("source_id must be a string")

    if not source_id.strip():
        raise ValueError("source_id must not be blank")


def _validate_version(version: int) -> None:
    """Validate an explicit configuration version number."""
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError("version must be an integer")

    if version < 1:
        raise ValueError("version must be >= 1")


__all__ = [
    "ConfigurationVersionConflictError",
    "ConfigurationVersionError",
    "ConfigurationVersionNotFoundError",
    "ConfigurationVersionStore",
    "SourceVersionHistory",
]
