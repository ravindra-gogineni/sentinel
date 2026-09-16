import pytest
from app.risk.models import SituationModel, SituationUpdate
from app.risk.risk_engine import calculate_severity
from app.risk.engine import process_situation_update, ACTIVE_SITUATIONS


@pytest.fixture(autouse=True)
def clear_state():
    """Clear the active situations before each test."""
    ACTIVE_SITUATIONS.clear()


# ─────────────────────────────────────────────────────────────────────────────
# A. Direct calculate_severity unit tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCalculateSeverity:
    def test_empty_situation_is_low(self):
        situation = SituationModel(session_id="test")
        risk = calculate_severity(situation)
        assert risk.severity == "LOW"
        assert risk.reasons == []
        assert risk.immediate_actions == []

    def test_abnormal_vibration_alone_is_medium(self):
        situation = SituationModel(session_id="test", abnormal_vibration=True)
        risk = calculate_severity(situation)
        assert risk.severity == "MEDIUM"
        assert any("vibration" in r.lower() for r in risk.reasons)

    def test_machine_running_and_vibration_is_medium(self):
        situation = SituationModel(
            session_id="test",
            machine_running=True,
            abnormal_vibration=True,
        )
        risk = calculate_severity(situation)
        assert risk.severity == "MEDIUM"

    def test_machine_running_vibration_increasing_is_high(self):
        situation = SituationModel(
            session_id="test",
            machine_running=True,
            abnormal_vibration=True,
            vibration_increasing=True,
        )
        risk = calculate_severity(situation)
        assert risk.severity == "HIGH"
        assert len(risk.immediate_actions) > 0

    def test_sparks_is_critical(self):
        situation = SituationModel(session_id="test", sparks=True)
        risk = calculate_severity(situation)
        assert risk.severity == "CRITICAL"
        assert "Sparks detected" in risk.reasons

    def test_smoke_is_critical(self):
        situation = SituationModel(session_id="test", smoke=True)
        risk = calculate_severity(situation)
        assert risk.severity == "CRITICAL"
        assert "Smoke detected" in risk.reasons

    def test_sparks_and_smoke_has_both_reasons(self):
        situation = SituationModel(session_id="test", sparks=True, smoke=True)
        risk = calculate_severity(situation)
        assert risk.severity == "CRITICAL"
        assert "Sparks detected" in risk.reasons
        assert "Smoke detected" in risk.reasons

    def test_multiple_conditions_highest_wins(self):
        situation = SituationModel(
            session_id="test",
            machine_running=True,
            abnormal_vibration=True,
            vibration_increasing=True,
            sparks=True,
        )
        risk = calculate_severity(situation)
        assert risk.severity == "CRITICAL"

    def test_vibration_increasing_without_vibration_is_low(self):
        situation = SituationModel(
            session_id="test",
            vibration_increasing=True,
        )
        risk = calculate_severity(situation)
        assert risk.severity == "LOW"

    def test_people_nearby_does_not_affect_risk(self):
        situation = SituationModel(session_id="test", people_nearby=5)
        risk = calculate_severity(situation)
        assert risk.severity == "LOW"

    def test_critical_immediate_actions_are_conservative(self):
        situation = SituationModel(session_id="test", sparks=True)
        risk = calculate_severity(situation)
        assert "Move away from the equipment" in risk.immediate_actions
        assert "Do not touch or approach the equipment" in risk.immediate_actions
        assert "Stay clear of the affected area" in risk.immediate_actions

    def test_high_immediate_actions(self):
        situation = SituationModel(
            session_id="test",
            machine_running=True,
            abnormal_vibration=True,
            vibration_increasing=True,
        )
        risk = calculate_severity(situation)
        assert "Keep clear of the affected equipment" in risk.immediate_actions
        assert "Do not attempt repairs" in risk.immediate_actions
        assert "Notify the responsible safety supervisor" in risk.immediate_actions


# ─────────────────────────────────────────────────────────────────────────────
# B. Engine integration tests (via process_situation_update)
# ─────────────────────────────────────────────────────────────────────────────


class TestEngineIntegration:
    def test_critical_overrides_next_question_goal(self):
        resp = process_situation_update(
            "sess_1",
            SituationUpdate(
                equipment="Machine 4",
                machine_running=True,
                sparks=True,
            ),
        )
        assert resp.severity == "CRITICAL"
        assert resp.next_question_goal == "Verify that the worker is safely away from the equipment"
        assert resp.priority == "critical"

    def test_highest_severity_upgrades_across_updates(self):
        process_situation_update(
            "sess_1",
            SituationUpdate(abnormal_vibration=True),
        )
        assert ACTIVE_SITUATIONS["sess_1"].highest_severity == "MEDIUM"

        process_situation_update(
            "sess_1",
            SituationUpdate(sparks=True),
        )
        assert ACTIVE_SITUATIONS["sess_1"].highest_severity == "CRITICAL"

    def test_highest_severity_never_downgrades(self):
        process_situation_update(
            "sess_1",
            SituationUpdate(sparks=True),
        )
        assert ACTIVE_SITUATIONS["sess_1"].highest_severity == "CRITICAL"

        process_situation_update(
            "sess_1",
            SituationUpdate(sparks=False),
        )
        assert ACTIVE_SITUATIONS["sess_1"].highest_severity == "CRITICAL"

    def test_risk_does_not_downgrade_on_unrelated_update(self):
        process_situation_update(
            "sess_1",
            SituationUpdate(sparks=True),
        )
        assert ACTIVE_SITUATIONS["sess_1"].highest_severity == "CRITICAL"

        process_situation_update(
            "sess_1",
            SituationUpdate(location="Zone A"),
        )
        assert ACTIVE_SITUATIONS["sess_1"].highest_severity == "CRITICAL"

    def test_tool_response_contains_risk_fields(self):
        resp = process_situation_update(
            "sess_1",
            SituationUpdate(abnormal_vibration=True),
        )
        assert resp.severity == "MEDIUM"
        assert isinstance(resp.reasons, list)
        assert isinstance(resp.immediate_actions, list)

    def test_phase3_next_question_goal_unchanged(self):
        resp = process_situation_update(
            "sess_1",
            SituationUpdate(equipment="Machine 4"),
        )
        assert resp.next_question_goal == "Determine whether the machine is currently running"
        assert resp.severity == "LOW"

        resp2 = process_situation_update(
            "sess_1",
            SituationUpdate(machine_running=True),
        )
        assert resp2.next_question_goal == "Determine whether anyone is currently near the machine"
        assert resp2.severity == "LOW"

    def test_smoke_triggers_critical_through_engine(self):
        resp = process_situation_update(
            "sess_1",
            SituationUpdate(equipment="Boiler", smoke=True),
        )
        assert resp.severity == "CRITICAL"
        assert resp.next_question_goal == "Verify that the worker is safely away from the equipment"
        assert ACTIVE_SITUATIONS["sess_1"].highest_severity == "CRITICAL"
