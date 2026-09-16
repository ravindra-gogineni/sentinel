"""
SENTINEL Backend — FastAPI Application Entry Point
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.voice import router as voice_router
from app.api.situation import router as situation_router
from app.api.verify import router as verify_router
from app.api.supervisor import router as supervisor_router, ws_router as supervisor_ws_router
from app.api.knowledge import router as knowledge_router
from app.api.factory import router as factory_router
from app.agents.sentinel_agent import ensure_agent_tools

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="SENTINEL API",
    description="Conversational Safety Intelligence — AssemblyAI Voice Agent Hackathon 2026",
    version="0.1.0",
)

settings = get_settings()

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(voice_router)
app.include_router(situation_router)
app.include_router(verify_router)
app.include_router(supervisor_router)
app.include_router(supervisor_ws_router)
app.include_router(knowledge_router)
app.include_router(factory_router)


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "SENTINEL",
        "agent_configured": bool(settings.sentinel_agent_id),
        "api_key_set": bool(
            settings.assemblyai_api_key
            and settings.assemblyai_api_key != "your_assemblyai_api_key_here"
        ),
    }


@app.on_event("startup")
async def startup_event() -> None:
    logger.info("=" * 60)
    logger.info("  SENTINEL backend starting up")
    logger.info(f"  Environment : {settings.environment}")
    logger.info(f"  API key set : {bool(settings.assemblyai_api_key and settings.assemblyai_api_key != 'your_assemblyai_api_key_here')}")
    logger.info(f"  Agent ID    : {settings.sentinel_agent_id or '(will be created on first /api/token call)'}")
    logger.info(f"  DB path     : {settings.sentinel_db_path}")
    logger.info(f"  Webhook     : {settings.supervisor_webhook_url or '(none — simulated supervisor notifications)'}")
    logger.info("=" * 60)

    # Phase 5: the stored agent must expose the verify_worker_safety tool.
    # Best-effort — a failure is logged loudly but must not crash the app.
    try:
        await ensure_agent_tools()
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Failed to ensure SENTINEL agent tools (%s). "
            "The verify_worker_safety tool may be missing on the AssemblyAI agent.",
            exc,
        )
