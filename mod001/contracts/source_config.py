"""
MOD-001 — Developer 1
D1-001: Source Configuration Contract

This module defines the common SourceConfig contract for external
market/economic data sources entering the MOD-001 acquisition boundary.

Architecture-aware collector types:
    API
    BROWSER
    RSS
    WEBSOCKET

Scope:
    - Source configuration
    - Configuration validation
    - Explicit configuration versioning

Out of scope:
    - Collector implementation
    - Scheduling
    - Retry execution
    - Rate limiting
    - Anti-bot implementation
    - Semantic normalization
    - Prediction/trading logic
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class CollectorType(str, Enum):
    """Collector types defined by the MOD-001 architecture."""

    API = "API"
    BROWSER = "BROWSER"
    RSS = "RSS"
    WEBSOCKET = "WEBSOCKET"


@dataclass(frozen=True)
class SourceConfig:
    """
    Registered and versioned configuration for an external source.

    Fields are aligned with the Developer 1 implementation specification:
        source_id
        collector_type
        enabled
        endpoint
        auth_ref
        request_parameters
        browser_profile
        timeout_ms
        retry_policy
        config_version
    """

    source_id: str
    collector_type: CollectorType
    enabled: bool
    endpoint: str | None = None
    auth_ref: str | None = None
    request_parameters: dict[str, Any] | None = None
    browser_profile: str | None = None
    timeout_ms: int = 5000
    retry_policy: dict[str, Any] | None = None
    config_version: int = 1

    def __post_init__(self) -> None:
        """Validate the SourceConfig contract."""

        # source_id
        if not isinstance(self.source_id, str):
            raise ValueError("source_id must be a string")

        if not self.source_id.strip():
            raise ValueError("source_id must not be blank")

        # collector_type
        if not isinstance(self.collector_type, CollectorType):
            raise ValueError(
                "collector_type must be one of: "
                "API, BROWSER, RSS, WEBSOCKET"
            )

        # enabled
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")

        # Optional string fields
        for field_name, value in (
            ("endpoint", self.endpoint),
            ("auth_ref", self.auth_ref),
            ("browser_profile", self.browser_profile),
        ):
            if value is not None:
                if not isinstance(value, str):
                    raise ValueError(f"{field_name} must be a string or None")
                if not value.strip():
                    raise ValueError(f"{field_name} must not be blank")

        # request_parameters
        if self.request_parameters is not None:
            if not isinstance(self.request_parameters, dict):
                raise ValueError(
                    "request_parameters must be a dictionary"
                )

        # timeout_ms
        if not isinstance(self.timeout_ms, int):
            raise ValueError("timeout_ms must be an integer")

        if self.timeout_ms <= 0:
            raise ValueError("timeout_ms must be greater than 0")

        # retry_policy
        if self.retry_policy is not None:
            if not isinstance(self.retry_policy, dict):
                raise ValueError("retry_policy must be a dictionary")

            max_attempts = self.retry_policy.get("max_attempts")

            if max_attempts is None:
                raise ValueError(
                    "retry_policy must contain max_attempts"
                )

            if (
                not isinstance(max_attempts, int)
                or isinstance(max_attempts, bool)
            ):
                raise ValueError(
                    "retry_policy.max_attempts must be an integer"
                )

            if max_attempts < 1:
                raise ValueError(
                    "retry_policy.max_attempts must be >= 1"
                )

        # config_version
        if not isinstance(self.config_version, int):
            raise ValueError("config_version must be an integer")

        if self.config_version < 1:
            raise ValueError("config_version must be >= 1")

    def to_dict(self) -> dict[str, Any]:
        """
        Return a serializable representation of the configuration.
        """

        return {
            "source_id": self.source_id,
            "collector_type": self.collector_type.value,
            "enabled": self.enabled,
            "endpoint": self.endpoint,
            "auth_ref": self.auth_ref,
            "request_parameters": self.request_parameters,
            "browser_profile": self.browser_profile,
            "timeout_ms": self.timeout_ms,
            "retry_policy": self.retry_policy,
            "config_version": self.config_version,
        }
