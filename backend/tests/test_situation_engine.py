import pytest
from app.risk.models import SituationUpdate
from app.risk.engine import process_situation_update, ACTIVE_SITUATIONS

@pytest.fixture(autouse=True)
def clear_state():
    """Clear the active situations before each test."""
    ACTIVE_SITUATIONS.clear()

def test_initial_situation_contains_unknowns():
    # 1. Initial situation contains unknowns
    resp = process_situation_update("sess_1", SituationUpdate(equipment="Machine 4"))
    assert "machine_running" in resp.unknowns
    assert "sparks" in resp.unknowns
    assert "smoke" in resp.unknowns

def test_adding_equipment_updates_equipment():
    # 2. Adding equipment updates equipment
    process_situation_update("sess_1", SituationUpdate(equipment="Machine 4"))
    situation = ACTIVE_SITUATIONS["sess_1"]
    assert situation.equipment == "Machine 4"

def test_adding_machine_running_updates_correctly():
    # 3. Adding machine_running=true updates correctly
    process_situation_update("sess_1", SituationUpdate(machine_running=True))
    assert ACTIVE_SITUATIONS["sess_1"].machine_running is True

def test_unknown_fields_not_false():
    # 4. Unknown fields are not treated as false
    process_situation_update("sess_1", SituationUpdate(equipment="Machine 4"))
    assert ACTIVE_SITUATIONS["sess_1"].sparks is None
    assert ACTIVE_SITUATIONS["sess_1"].sparks is not False

def test_existing_facts_not_overwritten_by_null():
    # 5. Existing facts are not overwritten by null
    process_situation_update("sess_1", SituationUpdate(machine_running=True))
    process_situation_update("sess_1", SituationUpdate(equipment="Machine 4")) # Should not nullify machine_running
    assert ACTIVE_SITUATIONS["sess_1"].machine_running is True

def test_next_question_priority_changes():
    # 6. Next-question priority changes as facts become known
    resp = process_situation_update("sess_1", SituationUpdate(equipment="Machine 4"))
    assert resp.next_question_goal == "Determine whether the machine is currently running"
    
    resp2 = process_situation_update("sess_1", SituationUpdate(machine_running=True))
    assert resp2.next_question_goal == "Determine whether anyone is currently near the machine"

def test_answered_questions_not_suggested_again():
    # 7. Already answered questions are not suggested again
    process_situation_update("sess_1", SituationUpdate(equipment="Machine 4", machine_running=True))
    process_situation_update("sess_1", SituationUpdate(people_nearby=2))
    
    # After giving people_nearby, it should ask the broad symptom question
    resp = process_situation_update("sess_1", SituationUpdate())
    assert resp.next_question_goal == "Determine exactly what the worker is noticing (e.g., unusual vibration, noise, heat, smoke, or sparks)"
    
    # If we answer abnormal_vibration, the next should be whether it's getting worse, NOT the broad question again
    resp2 = process_situation_update("sess_1", SituationUpdate(abnormal_vibration=True))
    assert resp2.next_question_goal == "Determine whether the vibration is getting worse"

def test_multiple_facts_merged():
    # 8. Multiple facts can be merged in one update
    process_situation_update("sess_1", SituationUpdate(
        machine_running=True,
        abnormal_vibration=True,
        people_nearby=2
    ))
    assert ACTIVE_SITUATIONS["sess_1"].machine_running is True
    assert ACTIVE_SITUATIONS["sess_1"].abnormal_vibration is True
    assert ACTIVE_SITUATIONS["sess_1"].people_nearby == 2

def test_different_session_ids_maintain_separate_situations():
    # 9. Different session IDs maintain separate situations
    process_situation_update("sess_1", SituationUpdate(equipment="Machine 4"))
    process_situation_update("sess_2", SituationUpdate(equipment="Generator 2"))
    
    assert ACTIVE_SITUATIONS["sess_1"].equipment == "Machine 4"
    assert ACTIVE_SITUATIONS["sess_2"].equipment == "Generator 2"
