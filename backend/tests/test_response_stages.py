"""
Decision 7 / Decision 2 — Deterministic response-stage unit tests (no I/O).
"""
from app.risk.response import determine_response_stage, verification_guidance


def test_below_critical_stays_investigating():
    for severity in ("LOW", "MEDIUM", "HIGH"):
        assert determine_response_stage(None, severity, None) == "INVESTIGATING"


def test_critical_with_unknown_worker_safe_enters_critical():
    assert determine_response_stage(None, "CRITICAL", None) == "CRITICAL"


def test_critical_with_worker_safe_false_enters_verifying_safety():
    assert determine_response_stage(None, "CRITICAL", False) == "VERIFYING_SAFETY"
    assert determine_response_stage("CRITICAL", "CRITICAL", False) == "VERIFYING_SAFETY"


def test_critical_with_worker_safe_true_is_escalation_eligible():
    assert determine_response_stage(None, "CRITICAL", True) == "ESCALATED"
    assert determine_response_stage("VERIFYING_SAFETY", "CRITICAL", True) == "ESCALATED"


def test_escalated_never_downgrades():
    assert determine_response_stage("ESCALATED", "LOW", None) == "ESCALATED"
    assert determine_response_stage("ESCALATED", "CRITICAL", None) == "ESCALATED"


def test_critical_flow_survives_non_critical_severity():
    # Severity is sticky in the real engine (facts persist), but the response
    # layer must ALSO refuse to downgrade a session already in the critical flow.
    assert determine_response_stage("CRITICAL", "LOW", None) == "CRITICAL"
    assert determine_response_stage("VERIFYING_SAFETY", "LOW", None) == "VERIFYING_SAFETY"


def test_verification_guidance_only_for_critical_flow():
    assert "safely away" in verification_guidance("CRITICAL")
    assert "single" in verification_guidance("VERIFYING_SAFETY")
    assert "supervisor" in verification_guidance("ESCALATED")
    assert verification_guidance("INVESTIGATING") is None
    assert verification_guidance(None) is None