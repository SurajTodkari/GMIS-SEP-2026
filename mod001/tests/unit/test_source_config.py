"""
MOD-001 — Developer 1
D1-001: SourceConfig Tests

Initial validation gate:
    D1-T01 — Register valid API source
    D1-T02 — Missing source_id
    D1-T03 — Invalid collector_type
    D1-T04 — Invalid timeout

These tests are based on Section 14 of the Developer 1
Implementation Specification.
"""

import pytest

from mod001.contracts.source_config import CollectorType, SourceConfig


def valid_source_config(**overrides):
    """Return a valid baseline SourceConfig test payload."""
    data = {
        "source_id": "gold_api",
        "collector_type": CollectorType.API,
        "enabled": True,
        "endpoint": "https://provider.example/gold",
        "auth_ref": "secret://gold-api-key",
        "request_parameters": {
            "symbol": "XAUUSD",
        },
        "browser_profile": None,
        "timeout_ms": 5000,
        "retry_policy": {
            "max_attempts": 3,
        },
        "config_version": 1,
    }

    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# D1-T01 — Register valid API source
# ---------------------------------------------------------------------------

def test_d1_t01_valid_api_source():
    """A valid API source configuration must be accepted."""
    config = SourceConfig(**valid_source_config())

    assert config.source_id == "gold_api"
    assert config.collector_type is CollectorType.API
    assert config.enabled is True
    assert config.timeout_ms == 5000
    assert config.retry_policy["max_attempts"] == 3
    assert config.config_version == 1


# ---------------------------------------------------------------------------
# D1-T02 — Missing source_id
# ---------------------------------------------------------------------------

def test_d1_t02_missing_source_id():
    """A missing source_id must be rejected."""
    data = valid_source_config()
    data.pop("source_id")

    with pytest.raises((TypeError, ValueError)):
        SourceConfig(**data)


# ---------------------------------------------------------------------------
# D1-T03 — Invalid collector_type
# ---------------------------------------------------------------------------

def test_d1_t03_invalid_collector_type():
    """An unsupported collector type must be rejected."""
    data = valid_source_config(
        collector_type="INVALID",
    )

    with pytest.raises(ValueError):
        SourceConfig(**data)


# ---------------------------------------------------------------------------
# D1-T04 — Invalid timeout
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "timeout_ms",
    [
        0,
        -1,
    ],
)
def test_d1_t04_invalid_timeout(timeout_ms):
    """Zero or negative timeout must be rejected."""
    data = valid_source_config(
        timeout_ms=timeout_ms,
    )

    with pytest.raises(ValueError):
        SourceConfig(**data)


# ---------------------------------------------------------------------------
# Supporting validation tests
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
def test_all_architecture_collector_types(collector_type):
    """
    All collector types represented in the architecture must be accepted.
    """
    config = SourceConfig(
        **valid_source_config(
            collector_type=collector_type,
        )
    )

    assert config.collector_type is collector_type


def test_blank_source_id_rejected():
    """Whitespace-only source_id must be rejected."""
    data = valid_source_config(
        source_id="   ",
    )

    with pytest.raises(ValueError):
        SourceConfig(**data)


def test_invalid_retry_policy_rejected():
    """retry_policy must contain a positive integer max_attempts."""
    data = valid_source_config(
        retry_policy={
            "max_attempts": 0,
        },
    )

    with pytest.raises(ValueError):
        SourceConfig(**data)


def test_invalid_config_version_rejected():
    """config_version must be >= 1."""
    data = valid_source_config(
        config_version=0,
    )

    with pytest.raises(ValueError):
        SourceConfig(**data)


def test_to_dict_serialization():
    """SourceConfig must serialize without losing contract fields."""
    config = SourceConfig(**valid_source_config())

    result = config.to_dict()

    assert result["source_id"] == "gold_api"
    assert result["collector_type"] == "API"
    assert result["enabled"] is True
    assert result["endpoint"] == "https://provider.example/gold"
    assert result["auth_ref"] == "secret://gold-api-key"
    assert result["request_parameters"]["symbol"] == "XAUUSD"
    assert result["timeout_ms"] == 5000
    assert result["retry_policy"]["max_attempts"] == 3
    assert result["config_version"] == 1
