"""
MOD-001 — Developer 1
D1-002: Source Registry Tests

Test coverage for the Source Registry responsibilities:
    - Register source
    - Retrieve source
    - List sources
    - Update source
    - Validate SourceConfig
    - Reject duplicate source registration
    - Reject unknown source retrieval/update
    - Preserve registry state through defensive copies

These tests intentionally keep configuration-version lifecycle out of scope;
that responsibility belongs to D1-003.
"""

import pytest

from mod001.contracts.source_config import CollectorType, SourceConfig
from mod001.registry.source_registry import (
    InvalidSourceConfigError,
    SourceAlreadyRegisteredError,
    SourceNotFoundError,
    SourceRegistry,
)


def make_source(
    source_id: str = "gold_api",
    collector_type: CollectorType = CollectorType.API,
    enabled: bool = True,
    config_version: int = 1,
    timeout_ms: int = 5000,
) -> SourceConfig:
    """Create a valid SourceConfig for registry tests."""
    return SourceConfig(
        source_id=source_id,
        collector_type=collector_type,
        enabled=enabled,
        endpoint="https://provider.example/gold",
        auth_ref="secret://gold-api-key",
        request_parameters={"symbol": "XAUUSD"},
        browser_profile=None,
        timeout_ms=timeout_ms,
        retry_policy={"max_attempts": 3},
        config_version=config_version,
    )


# ---------------------------------------------------------------------------
# Basic registry lifecycle
# ---------------------------------------------------------------------------

def test_register_source():
    """A valid SourceConfig must be registered successfully."""
    registry = SourceRegistry()
    source = make_source()

    registered = registry.register(source)

    assert registered.source_id == "gold_api"
    assert registered.collector_type is CollectorType.API
    assert registry.count() == 1


def test_get_registered_source():
    """A registered source must be retrievable by source_id."""
    registry = SourceRegistry()
    source = make_source()

    registry.register(source)
    result = registry.get("gold_api")

    assert result.source_id == source.source_id
    assert result.collector_type is source.collector_type
    assert result.config_version == 1


def test_list_registered_sources():
    """The registry must return all registered sources."""
    registry = SourceRegistry()

    registry.register(make_source("gold_api", CollectorType.API))
    registry.register(make_source("forex_factory", CollectorType.BROWSER))
    registry.register(make_source("cnbc", CollectorType.RSS))

    sources = registry.list_sources()

    assert len(sources) == 3
    assert [source.source_id for source in sources] == [
        "gold_api",
        "forex_factory",
        "cnbc",
    ]


def test_update_registered_source():
    """An existing source configuration must be updateable."""
    registry = SourceRegistry()
    registry.register(make_source())

    updated = make_source(
        enabled=False,
        timeout_ms=10000,
    )

    result = registry.update(updated)

    assert result.source_id == "gold_api"
    assert result.enabled is False
    assert result.timeout_ms == 10000
    assert registry.get("gold_api").enabled is False
    assert registry.count() == 1


# ---------------------------------------------------------------------------
# Duplicate and missing source handling
# ---------------------------------------------------------------------------

def test_duplicate_registration_rejected():
    """Registering the same source_id twice must fail."""
    registry = SourceRegistry()

    registry.register(make_source("gold_api"))

    with pytest.raises(SourceAlreadyRegisteredError):
        registry.register(make_source("gold_api"))


def test_get_missing_source_rejected():
    """Getting an unknown source_id must fail."""
    registry = SourceRegistry()

    with pytest.raises(SourceNotFoundError):
        registry.get("missing_source")


def test_update_missing_source_rejected():
    """Updating an unknown source_id must fail."""
    registry = SourceRegistry()

    with pytest.raises(SourceNotFoundError):
        registry.update(make_source("missing_source"))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_registry_rejects_non_source_config():
    """The registry must reject objects that are not SourceConfig."""
    registry = SourceRegistry()

    with pytest.raises(InvalidSourceConfigError):
        registry.register(
            {
                "source_id": "gold_api",
                "collector_type": "API",
            }
        )


def test_validate_accepts_valid_source_config():
    """A valid SourceConfig must pass registry validation."""
    registry = SourceRegistry()
    source = make_source()

    result = registry.validate(source)

    assert result is source


def test_invalid_source_config_cannot_reach_registry():
    """
    Invalid SourceConfig data must fail before it can be registered.

    SourceConfig owns field-level validation; the registry consumes
    only already-valid SourceConfig instances.
    """
    with pytest.raises(ValueError):
        make_source(timeout_ms=0)


# ---------------------------------------------------------------------------
# Source type coverage from architecture
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "collector_type",
    [
        CollectorType.API,
        CollectorType.BROWSER,
        CollectorType.RSS,
        CollectorType.WEBSOCKET,
    ],
)
def test_registry_supports_all_architecture_collector_types(collector_type):
    """
    The registry must accept SourceConfig objects for every collector type
    defined by the MOD-001 architecture.
    """
    registry = SourceRegistry()

    source = make_source(
        source_id=f"source_{collector_type.value.lower()}",
        collector_type=collector_type,
    )

    registry.register(source)
    result = registry.get(source.source_id)

    assert result.collector_type is collector_type


# ---------------------------------------------------------------------------
# Defensive copy behavior
# ---------------------------------------------------------------------------

def test_register_returns_defensive_copy():
    """Mutating the returned object must not mutate registry state."""
    registry = SourceRegistry()

    source = make_source()
    registered = registry.register(source)

    registered.request_parameters["symbol"] = "EURUSD"

    stored = registry.get("gold_api")

    assert stored.request_parameters["symbol"] == "XAUUSD"


def test_get_returns_defensive_copy():
    """Mutating a retrieved object must not mutate registry state."""
    registry = SourceRegistry()
    registry.register(make_source())

    retrieved = registry.get("gold_api")
    retrieved.request_parameters["symbol"] = "EURUSD"

    stored = registry.get("gold_api")

    assert stored.request_parameters["symbol"] == "XAUUSD"


# ---------------------------------------------------------------------------
# Registry count / state
# ---------------------------------------------------------------------------

def test_empty_registry_count_is_zero():
    """A newly created registry must contain no sources."""
    registry = SourceRegistry()

    assert registry.count() == 0


def test_registry_count_after_multiple_registrations():
    """Registry count must reflect the number of registered source_ids."""
    registry = SourceRegistry()

    registry.register(make_source("gold_api"))
    registry.register(make_source("alpha_vantage"))
    registry.register(make_source("twelve_data"))

    assert registry.count() == 3


# ---------------------------------------------------------------------------
# Source ID lookup validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "invalid_source_id",
    [
        "",
        "   ",
        None,
    ],
)
def test_invalid_source_id_lookup_rejected(invalid_source_id):
    """Blank or non-string source IDs must be rejected."""
    registry = SourceRegistry()

    with pytest.raises(ValueError):
        registry.get(invalid_source_id)
