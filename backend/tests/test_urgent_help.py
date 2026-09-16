"""
Tests for SENTINEL Urgent Help / SOS Voice Flow
"""
import pytest
from app.risk.engine import is_urgent_help_request, process_situation_update, ACTIVE_SITUATIONS
from app.risk.models import SituationUpdate


def test_urgent_help_detection_phrases():
    # 1. "Help!" -> urgent help detected
    assert is_urgent_help_request("Help!") is True
    assert is_urgent_help_request("help") is True

    # 2. "I need help!" -> urgent help detected
    assert is_urgent_help_request("I need help!") is True

    # 3. "I'm in danger!" -> urgent help detected
    assert is_urgent_help_request("I'm in danger!") is True
    assert is_urgent_help_request("Someone help me!") is True
    assert is_urgent_help_request("Something is wrong, help!") is True

    # 4. "Can you help me?" -> does not trigger SOS
    assert is_urgent_help_request("Can you help me?") is False

    # 5. "Can you help me find the maintenance number?" -> normal / False
    assert is_urgent_help_request("Can you help me find the maintenance number?") is False
    assert is_urgent_help_request("Can you help with Machine 4?") is False
    assert is_urgent_help_request("Help me understand this.") is False


def test_urgent_help_does_not_force_critical():
    ACTIVE_SITUATIONS.clear()
    session_id = "test_sos_01"

    # 8. Urgent help alone does NOT force CRITICAL
    res = process_situation_update(session_id, SituationUpdate(observation="Help! I need help!"))
    assert res.urgent_help_detected is True
    assert res.severity == "LOW"  # Severity remains LOW until actual risk facts emerge
    assert res.next_question_goal == "Verify whether the worker is in immediate danger right now"


def test_urgent_help_followed_by_sparks_becomes_critical():
    ACTIVE_SITUATIONS.clear()
    session_id = "test_sos_02"

    # Worker requests help
    res1 = process_situation_update(session_id, SituationUpdate(observation="Help!"))
    assert res1.urgent_help_detected is True
    assert res1.severity == "LOW"

    # Worker reports sparks
    res2 = process_situation_update(session_id, SituationUpdate(sparks=True, equipment="Machine 4"))
    assert res2.severity == "CRITICAL"
    assert res2.incident_status == "CRITICAL"
    assert res2.immediate_actions == [
        "Move away from the equipment",
        "Do not touch or approach the equipment",
        "Stay clear of the affected area",
    ]


def test_urgent_help_followed_by_no_danger_continues_investigation():
    ACTIVE_SITUATIONS.clear()
    session_id = "test_sos_03"

    # Urgent help request
    process_situation_update(session_id, SituationUpdate(observation="I need help!"))

    # Worker clarifies no immediate danger, but abnormal vibration on Machine 4
    res = process_situation_update(session_id, SituationUpdate(equipment="Machine 4", abnormal_vibration=True))
    assert res.severity == "MEDIUM"
    assert res.incident_status == "INVESTIGATING"
