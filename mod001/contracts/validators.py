"""
MOD-001 Developer 1
D1-006 Contract Validators

Purpose:
    Validate stable contracts used by MOD-001 acquisition foundation.

Validated Objects:
    - SourceConfig
    - AcquisitionJob
    - AcquisitionEnvelope
    - Payload Hash
    - Timestamp fields

Boundary:
    Reject invalid contracts before downstream handoff.
"""


from datetime import datetime
import hashlib
import json


# ============================================================
# Allowed Contract Values
# ============================================================

VALID_COLLECTOR_TYPES = {
    "API",
    "BROWSER",
    "RSS",
    "WEBSOCKET"
}


VALID_ENVELOPE_STATUS = {
    "SUCCESS",
    "RETRY",
    "FAILED",
    "DEGRADED"
}


# ============================================================
# Generic Validation Helpers
# ============================================================

def validation_error(message: str):
    """
    Standard validation error response.
    """
    return {
        "valid": False,
        "error": message
    }


def validation_success():
    """
    Standard validation success response.
    """
    return {
        "valid": True,
        "error": None
    }


# ============================================================
# SourceConfig Validation
# ============================================================

def validate_source_config(config: dict) -> dict:
    """
    Validate SourceConfig contract.

    Required:
        source_id
        collector_type
        enabled
        timeout_ms
        retry_policy
        config_version

    Based on MOD-001 D1-006 rules.
    """

    required_fields = [
        "source_id",
        "collector_type",
        "enabled",
        "timeout_ms",
        "retry_policy",
        "config_version"
    ]


    for field in required_fields:
        if field not in config:
            return validation_error(
                f"Missing required field: {field}"
            )


    if not isinstance(config["enabled"], bool):
        return validation_error(
            "enabled must be boolean"
        )


    if config["collector_type"] not in VALID_COLLECTOR_TYPES:
        return validation_error(
            f"Invalid collector_type: {config['collector_type']}"
        )


    if not isinstance(config["timeout_ms"], int):
        return validation_error(
            "timeout_ms must be integer"
        )


    if config["timeout_ms"] <= 0:
        return validation_error(
            "timeout_ms must be positive"
        )


    if not isinstance(config["retry_policy"], dict):
        return validation_error(
            "retry_policy must be object"
        )


    if "max_attempts" not in config["retry_policy"]:
        return validation_error(
            "retry_policy.max_attempts missing"
        )


    if config["config_version"] < 1:
        return validation_error(
            "config_version must be >= 1"
        )


    return validation_success()



# ============================================================
# AcquisitionJob Validation
# ============================================================

def validate_acquisition_job(job: dict) -> dict:
    """
    Validate AcquisitionJob contract.

    Required:
        job_id
        source_id
        collector_type
        trace_id
        attempt_no
        config_version
    """

    required_fields = [
        "job_id",
        "source_id",
        "collector_type",
        "trace_id",
        "attempt_no",
        "config_version"
    ]


    for field in required_fields:
        if field not in job:
            return validation_error(
                f"Missing required field: {field}"
            )


    if job["collector_type"] not in VALID_COLLECTOR_TYPES:
        return validation_error(
            "Invalid collector_type"
        )


    if job["attempt_no"] < 1:
        return validation_error(
            "attempt_no must be >= 1"
        )


    if job["config_version"] < 1:
        return validation_error(
            "Invalid config_version"
        )


    return validation_success()



# ============================================================
# AcquisitionEnvelope Validation
# ============================================================

def validate_acquisition_envelope(
        envelope: dict
) -> dict:
    """
    Validate AcquisitionEnvelope contract.

    Checks:
        - Identity fields
        - Status
        - Timestamp format
        - Payload existence
        - Hash existence
    """


    required_fields = [
        "acquisition_id",
        "job_id",
        "source_id",
        "collector_type",
        "status"
    ]


    for field in required_fields:
        if field not in envelope:
            return validation_error(
                f"Missing required field: {field}"
            )


    if envelope["status"] not in VALID_ENVELOPE_STATUS:
        return validation_error(
            "Invalid envelope status"
        )


    if envelope["collector_type"] not in VALID_COLLECTOR_TYPES:
        return validation_error(
            "Invalid collector_type"
        )


    # SUCCESS requires evidence
    if envelope["status"] == "SUCCESS":

        if not envelope.get("raw_payload"):
            return validation_error(
                "SUCCESS envelope requires raw_payload"
            )


        if not envelope.get("payload_hash"):
            return validation_error(
                "SUCCESS envelope requires payload_hash"
            )


    timestamp_fields = [
        "source_timestamp",
        "acquired_at",
        "completed_at"
    ]


    for field in timestamp_fields:

        if field in envelope and envelope[field]:

            if not validate_timestamp(
                envelope[field]
            ):
                return validation_error(
                    f"Invalid timestamp: {field}"
                )


    return validation_success()



# ============================================================
# Timestamp Validation
# ============================================================

def validate_timestamp(
        timestamp: str
) -> bool:
    """
    Validate ISO timestamp format.
    """

    try:
        datetime.fromisoformat(
            timestamp.replace(
                "Z",
                "+00:00"
            )
        )

        return True

    except ValueError:

        return False



# ============================================================
# Hash Validation
# ============================================================

def generate_payload_hash(
        payload: dict
) -> str:
    """
    Generate deterministic SHA-256 hash.

    Same payload:
        Same hash

    Modified payload:
        Different hash
    """

    canonical_payload = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":")
    )


    digest = hashlib.sha256(
        canonical_payload.encode(
            "utf-8"
        )
    ).hexdigest()


    return f"sha256:{digest}"



def validate_payload_hash(
        payload: dict,
        expected_hash: str
) -> dict:
    """
    Verify payload integrity.
    """

    calculated_hash = generate_payload_hash(
        payload
    )


    if calculated_hash != expected_hash:

        return validation_error(
            "Payload hash mismatch"
        )


    return validation_success()