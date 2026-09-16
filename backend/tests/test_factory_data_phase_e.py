"""
SENTINEL 2.0 Phase E — Factory Data & Live Machine Intelligence Tests
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.context.models import FactoryContext
from app.context.context_engine import get_or_create_context, update_context_from_utterance, clear_context
from app.intent.models import IntentCategory, Capability
from app.intent.intent_engine import analyze_intent
from app.factory_data import (
    get_machine_info,
    get_machine_status,
    get_maintenance_history,
    get_active_work_orders,
    format_machine_status_response,
    format_maintenance_response,
    format_work_orders_response,
    FactoryDataResult,
    DataCategory,
    DataFreshness,
    DataSource,
)
from app.risk.engine import ACTIVE_SITUATIONS

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_sessions():
    yield
    for s_id in list(ACTIVE_SITUATIONS.keys()):
        clear_context(s_id, target="all")


def test_1_machine_info():
    res = get_machine_info(machine_id="Machine 4")
    assert res.found is True
    assert res.machine_id == "Machine 4"
    assert res.data_type == DataCategory.HISTORICAL.value
    assert res.data.machine_type == "Milling Station"
    assert res.data.model == "M4-Pro"
    assert res.data.location == "Bay A, Line 2"


def test_2_machine_status():
    res = get_machine_status(machine_id="Machine 4")
    assert res.found is True
    assert res.machine_id == "Machine 4"
    assert res.data_type == DataCategory.LIVE.value
    assert res.data.temperature == 68.4
    assert res.data.vibration == 2.7
    assert res.data.pressure == 4.2
    assert res.data.status == "RUNNING"


def test_3_maintenance_history():
    res = get_maintenance_history(machine_id="Machine 4")
    assert res.found is True
    assert len(res.data) >= 1
    latest = res.data[0]
    assert latest.service_date == "2026-08-28"
    assert latest.technician == "Alex Rivera"
    assert "bearings inspected" in latest.findings.lower()


def test_4_active_work_orders():
    res_m4 = get_active_work_orders(machine_id="Machine 4")
    assert res_m4.found is True
    assert len(res_m4.data) == 1
    assert res_m4.data[0].work_order_id == "WO-M4-102"
    assert "Motor Belt Replacement" in res_m4.data[0].title

    res_m7 = get_active_work_orders(machine_id="Machine 7")
    assert res_m7.found is True
    assert len(res_m7.data) == 0
    assert "no active work orders for Machine 7" in res_m7.message


def test_5_current_live_data_distinction():
    res = get_machine_status(machine_id="Machine 4")
    assert res.data_type == DataCategory.LIVE.value
    assert res.source == "FACTORY_DATA"
    assert res.freshness == DataFreshness.CURRENT.value
    assert res.data.data_source == DataSource.SIMULATED.value


def test_6_historical_data_distinction():
    res = get_maintenance_history(machine_id="Machine 4")
    assert res.data_type == DataCategory.HISTORICAL.value
    assert res.source == "FACTORY_DATA"


def test_7_source_provenance():
    res = get_machine_status(machine_id="Machine 7")
    assert res.source == "FACTORY_DATA"
    assert res.data.data_source == "SIMULATED"
    assert res.data.last_updated is not None


def test_8_data_freshness():
    res = get_machine_status(machine_id="Machine 4")
    assert res.freshness == DataFreshness.CURRENT.value
    assert res.data.data_freshness == "CURRENT"


def test_9_missing_machine_context():
    # Calling services without explicit machine or context
    res = get_machine_status(machine_id=None, context=None)
    assert res.found is False
    assert "specify which machine" in res.message.lower()


def test_10_unknown_machine():
    res = get_machine_status(machine_id="Machine 99")
    assert res.found is False
    assert res.machine_not_found is True
    assert "don't have a current Machine 99 status reading" in res.message


def test_11_phase_b_context_integration():
    ctx = get_or_create_context("test_e_sess_11")
    update_context_from_utterance("test_e_sess_11", "I'm working on Machine 4.")

    res = get_machine_status(context=ctx)
    assert res.found is True
    assert res.machine_id == "Machine 4"
    assert res.data.temperature == 68.4


def test_12_machine_override():
    ctx = get_or_create_context("test_e_sess_12")
    update_context_from_utterance("test_e_sess_12", "I'm working on Machine 4.")
    update_context_from_utterance("test_e_sess_12", "Actually, I'm working on Machine 7 now.")

    res = get_machine_status(context=ctx)
    assert res.found is True
    assert res.machine_id == "Machine 7"
    assert res.data.temperature == 72.1  # Machine 7 data, NOT Machine 4!


def test_13_phase_c_capability_integration():
    ctx = get_or_create_context("test_e_sess_13")
    update_context_from_utterance("test_e_sess_13", "I'm working on Machine 4.")

    # GET_MACHINE_STATUS
    an_status = analyze_intent("What's the status?", ctx)
    assert an_status.capability == Capability.GET_MACHINE_STATUS

    # GET_MAINTENANCE_HISTORY
    an_maint = analyze_intent("When was it serviced?", ctx)
    assert an_maint.capability == Capability.GET_MAINTENANCE_HISTORY


def test_14_concise_result_data():
    res = get_machine_status("Machine 4")
    assert "simulated as running at 68.4" in res.message
    assert "vibration at 2.7 mm/s" in res.message
    # Verify concise response (short single line)
    assert len(res.message) < 150


def test_15_no_mutation_of_risk_engine():
    ctx = get_or_create_context("test_e_sess_15")
    initial_sev = ctx.current_severity

    # Querying live status or maintenance must NOT mutate RiskEngine state
    get_machine_status("Machine 4", context=ctx)
    get_maintenance_history("Machine 4", context=ctx)

    assert ctx.current_severity == initial_sev
    assert ctx.highest_severity == "LOW"


def test_16_no_severity_calculation():
    # FactoryDataResult contains no severity calculation or risk score fields
    res = get_machine_status("Machine 4")
    assert not hasattr(res, "severity")
    assert not hasattr(res, "risk_score")


def test_17_no_incident_creation():
    ACTIVE_SITUATIONS.clear()
    get_machine_status("Machine 4")
    get_maintenance_history("Machine 4")
    # Verify no incidents created in ACTIVE_SITUATIONS
    assert len(ACTIVE_SITUATIONS) == 0


def test_18_read_only_guarantee():
    # Verify module exports only read-only query methods
    from app import factory_data
    exported_names = dir(factory_data)
    for forbidden in ["start_machine", "stop_machine", "set_temperature", "disable_safety"]:
        assert forbidden not in exported_names


def test_19_rag_boundary():
    ctx = get_or_create_context("test_e_sess_19")
    update_context_from_utterance("test_e_sess_19", "I'm working on Machine 4.")

    # "What torque should I use?" -> Route to Phase C / Phase D RAG, NOT Factory Data
    analysis = analyze_intent("What torque should I use?", ctx)
    assert analysis.intent == IntentCategory.FACTORY_KNOWLEDGE
    assert analysis.capability in [Capability.SEARCH_EQUIPMENT_MANUAL, Capability.GET_REQUIRED_TOOLS]


def test_20_machine_4_vs_machine_7_data_separation():
    st4 = get_machine_status("Machine 4").data
    st7 = get_machine_status("Machine 7").data

    assert st4.temperature != st7.temperature
    assert st4.vibration != st7.vibration
    assert st4.pressure != st7.pressure
    assert st4.runtime_hours != st7.runtime_hours

    maint4 = get_maintenance_history("Machine 4").data
    maint7 = get_maintenance_history("Machine 7").data

    assert maint4[0].technician != maint7[0].technician
    assert maint4[0].service_date != maint7[0].service_date


def test_21_rest_api_endpoints():
    # GET /api/factory/machines/Machine 4
    r_info = client.get("/api/factory/machines/Machine%204")
    assert r_info.status_code == 200
    assert r_info.json()["data"]["model"] == "M4-Pro"

    # GET /api/factory/machines/Machine 4/status
    r_status = client.get("/api/factory/machines/Machine%204/status")
    assert r_status.status_code == 200
    assert r_status.json()["data"]["temperature"] == 68.4

    # GET /api/factory/machines/Machine 4/maintenance
    r_maint = client.get("/api/factory/machines/Machine%204/maintenance")
    assert r_maint.status_code == 200
    assert len(r_maint.json()["data"]) >= 1

    # GET /api/factory/machines/Machine 4/work-orders
    r_wo = client.get("/api/factory/machines/Machine%204/work-orders")
    assert r_wo.status_code == 200
    assert len(r_wo.json()["data"]) == 1

    # GET /api/factory/machines/Machine 99 (Not Found test)
    r_nf = client.get("/api/factory/machines/Machine%2099/status")
    assert r_nf.status_code == 404
