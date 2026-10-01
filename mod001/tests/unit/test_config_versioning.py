"""
MOD-001 — Developer 1
D1-003: Configuration Versioning Tests

Coverage:
    - Initial configuration registration
    - Explicit version preservation
    - New version creation
    - Monotonic version progression
    - Previous-version preservation
    - Specific-version retrieval
    - Current-version retrieval
    - Version listing
    - Explicit version registration
    - Duplicate/conflicting version handling
    - Missing history/version handling
    - Source/version validation

Configuration versioning is intentionally tested independently of:
    - schedulers
    - retries
    - collectors
    - runtime execution
"""

import pytest

from mod001.contracts.source_config import CollectorType, SourceConfig
from mod001.registry.config_versioning import (
    ConfigurationVersionConflictError,
    ConfigurationVersionError,
    ConfigurationVersionNotFoundError,
    ConfigurationVersionStore,
)


def make_source(
    source_id: str = "gold_api",
    config_version: int = 1,
    enabled: bool = True,
    timeout_ms: int = 5000,
    endpoint: str | None = "https://provider.example/gold",
    collector_type: CollectorType = CollectorType.API,
) -> SourceConfig:
    """Create a valid SourceConfig for versioning tests."""
    return SourceConfig(
        source_id=source_id,
        collector_type=collector_type,
        enabled=enabled,
        endpoint=endpoint,
        auth_ref="secret://gold-api-key",
        request_parameters={"symbol": "XAUUSD"},
        browser_profile=None,
        timeout_ms=timeout_ms,
        retry_policy={"max_attempts": 3},
        config_version=config_version,
    )


# ---------------------------------------------------------------------------
# Initial version
# ---------------------------------------------------------------------------

def test_register_initial_configuration():
    """Initial configuration with an explicit version must be stored."""
    store = ConfigurationVersionStore()
    source = make_source(config_version=1)

    result = store.register_initial(source)

    assert result.source_id == "gold_api"
    assert result.config_version == 1
    assert store.count_versions("gold_api") == 1


def test_initial_configuration_version_is_preserved():
    """The supplied initial version must not be silently changed."""
    store = ConfigurationVersionStore()
    source = make_source(config_version=3)

    result = store.register_initial(source)

    assert result.config_version == 3
    assert store.get_current("gold_api").config_version == 3
    assert store.list_versions("gold_api") == [3]


def test_initial_configuration_cannot_be_registered_twice():
    """A second initial registration must be rejected."""
    store = ConfigurationVersionStore()
    store.register_initial(make_source(config_version=1))

    with pytest.raises(ConfigurationVersionConflictError):
        store.register_initial(make_source(config_version=1))


# ---------------------------------------------------------------------------
# New-version creation
# ---------------------------------------------------------------------------

def test_create_new_version_increments_version():
    """A material configuration revision must receive the next version."""
    store = ConfigurationVersionStore()

    store.register_initial(make_source(config_version=1))

    changed = make_source(
        config_version=1,
        enabled=False,
    )

    result = store.create_new_version(changed)

    assert result.config_version == 2
    assert store.list_versions("gold_api") == [1, 2]


def test_create_multiple_versions_progresses_monotonically():
    """Versions must progress 1 -> 2 -> 3 without gaps from the store."""
    store = ConfigurationVersionStore()

    version_1 = make_source(config_version=1)
    store.register_initial(version_1)

    version_2_input = make_source(
        config_version=1,
        enabled=False,
    )
    version_2 = store.create_new_version(version_2_input)

    version_3_input = make_source(
        config_version=999,
        enabled=False,
        timeout_ms=10000,
    )
    version_3 = store.create_new_version(version_3_input)

    assert version_2.config_version == 2
    assert version_3.config_version == 3
    assert store.list_versions("gold_api") == [1, 2, 3]


# ---------------------------------------------------------------------------
# Version history preservation
# ---------------------------------------------------------------------------

def test_previous_version_is_preserved():
    """Creating a new version must not overwrite the previous version."""
    store = ConfigurationVersionStore()

    source_v1 = make_source(
        config_version=1,
        enabled=True,
        timeout_ms=5000,
    )
    store.register_initial(source_v1)

    source_v2_input = make_source(
        config_version=1,
        enabled=False,
        timeout_ms=10000,
    )
    store.create_new_version(source_v2_input)

    stored_v1 = store.get_version("gold_api", 1)
    stored_v2 = store.get_version("gold_api", 2)

    assert stored_v1.config_version == 1
    assert stored_v1.enabled is True
    assert stored_v1.timeout_ms == 5000

    assert stored_v2.config_version == 2
    assert stored_v2.enabled is False
    assert stored_v2.timeout_ms == 10000


def test_current_returns_highest_version():
    """Current configuration must be the highest registered version."""
    store = ConfigurationVersionStore()

    store.register_initial(make_source(config_version=1))
    store.create_new_version(
        make_source(
            config_version=1,
            timeout_ms=7500,
        )
    )

    current = store.get_current("gold_api")

    assert current.config_version == 2
    assert current.timeout_ms == 7500


def test_list_versions_returns_sorted_versions():
    """Version listing must be returned in ascending order."""
    store = ConfigurationVersionStore()

    store.register_explicit_version(make_source(config_version=3))
    store.register_explicit_version(make_source(config_version=1))
    store.register_explicit_version(make_source(config_version=2))

    assert store.list_versions("gold_api") == [1, 2, 3]


# ---------------------------------------------------------------------------
# Explicit version registration
# ---------------------------------------------------------------------------

def test_register_explicit_version():
    """Existing explicitly versioned configurations can be restored."""
    store = ConfigurationVersionStore()

    result = store.register_explicit_version(
        make_source(config_version=7)
    )

    assert result.config_version == 7
    assert store.get_version("gold_api", 7).config_version == 7


def test_explicit_version_can_be_re_registered_identically():
    """
    Re-registering the exact same version and content is idempotent.
    """
    store = ConfigurationVersionStore()
    source = make_source(config_version=1)

    first = store.register_explicit_version(source)
    second = store.register_explicit_version(source)

    assert first.to_dict() == second.to_dict()
    assert store.list_versions("gold_api") == [1]


def test_conflicting_existing_version_is_rejected():
    """The same version cannot represent different configuration content."""
    store = ConfigurationVersionStore()

    store.register_explicit_version(
        make_source(
            config_version=1,
            enabled=True,
        )
    )

    with pytest.raises(ConfigurationVersionConflictError):
        store.register_explicit_version(
            make_source(
                config_version=1,
                enabled=False,
            )
        )


# ---------------------------------------------------------------------------
# Missing source/version handling
# ---------------------------------------------------------------------------

def test_create_new_version_requires_existing_history():
    """A new version cannot be created without an initial/history version."""
    store = ConfigurationVersionStore()

    with pytest.raises(ConfigurationVersionError):
        store.create_new_version(
            make_source(config_version=1)
        )


def test_get_missing_version_rejected():
    """Requesting an unknown version must fail clearly."""
    store = ConfigurationVersionStore()
    store.register_initial(make_source(config_version=1))

    with pytest.raises(ConfigurationVersionNotFoundError):
        store.get_version("gold_api", 99)


def test_get_missing_source_history_rejected():
    """Requesting a source with no version history must fail clearly."""
    store = ConfigurationVersionStore()

    with pytest.raises(ConfigurationVersionNotFoundError):
        store.get_current("unknown_source")


def test_list_missing_source_history_rejected():
    """Listing versions for an unknown source must fail clearly."""
    store = ConfigurationVersionStore()

    with pytest.raises(ConfigurationVersionNotFoundError):
        store.list_versions("unknown_source")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_non_source_config_is_rejected():
    """Versioning operations must accept only SourceConfig instances."""
    store = ConfigurationVersionStore()

    with pytest.raises(ValueError):
        store.register_initial(
            {
                "source_id": "gold_api",
                "config_version": 1,
            }
        )


@pytest.mark.parametrize(
    "invalid_version",
    [
        0,
        -1,
        None,
        "1",
        True,
    ],
)
def test_invalid_requested_version_is_rejected(invalid_version):
    """Version lookup must require an integer version >= 1."""
    store = ConfigurationVersionStore()
    store.register_initial(make_source(config_version=1))

    with pytest.raises(ValueError):
        store.get_version("gold_api", invalid_version)


def test_blank_source_id_lookup_is_rejected():
    """Blank source IDs must not be accepted for history lookup."""
    store = ConfigurationVersionStore()
    store.register_initial(make_source(config_version=1))

    with pytest.raises(ValueError):
        store.get_current("   ")


# ---------------------------------------------------------------------------
# Defensive copy / immutability-oriented behavior
# ---------------------------------------------------------------------------

def test_stored_configuration_is_not_mutated_through_return_value():
    """
    Mutating the returned SourceConfig's nested configuration must not
    mutate the stored historical version.
    """
    store = ConfigurationVersionStore()

    source = make_source(
        config_version=1,
    )
    store.register_initial(source)

    returned = store.get_version("gold_api", 1)
    returned.request_parameters["symbol"] = "EURUSD"

    stored = store.get_version("gold_api", 1)

    assert stored.request_parameters["symbol"] == "XAUUSD"


def test_new_version_uses_new_configuration_content():
    """New version must preserve the changed configuration content."""
    store = ConfigurationVersionStore()

    store.register_initial(
        make_source(
            config_version=1,
            enabled=True,
            timeout_ms=5000,
        )
    )

    result = store.create_new_version(
        make_source(
            config_version=123,
            enabled=False,
            timeout_ms=12000,
        )
    )

    assert result.config_version == 2
    assert result.enabled is False
    assert result.timeout_ms == 12000
