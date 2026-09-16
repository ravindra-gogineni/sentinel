"""
SENTINEL Backend — Token + Agent API Routes

GET  /api/agent  → returns the SENTINEL agent ID
GET  /api/token  → mints a short-lived AssemblyAI session token (safe for browser)
"""
import logging
import httpx

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.agents.sentinel_agent import get_or_create_agent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

AAI_TOKEN_URL = "https://agents.assemblyai.com/v1/token"


class AgentResponse(BaseModel):
    agent_id: str


class TokenResponse(BaseModel):
    token: str
    agent_id: str


@router.get("/agent", response_model=AgentResponse)
async def get_agent() -> AgentResponse:
    """
    Returns the SENTINEL agent ID.
    Creates the agent on AssemblyAI if it doesn't exist yet.
    """
    try:
        agent_id = await get_or_create_agent()
        return AgentResponse(agent_id=agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except httpx.HTTPStatusError as exc:
        logger.error(f"AssemblyAI error: {exc.response.status_code} {exc.response.text}")
        raise HTTPException(
            status_code=502,
            detail=f"AssemblyAI API error: {exc.response.status_code}",
        )


@router.get("/token", response_model=TokenResponse)
async def get_token() -> TokenResponse:
    """
    Mints a short-lived AssemblyAI session token.
    The token is safe to pass to the browser — it never exposes the API key.
    Each token is single-use and starts exactly one voice session.
    """
    settings = get_settings()
    api_key = settings.assemblyai_api_key

    if not api_key or api_key == "your_assemblyai_api_key_here":
        raise HTTPException(
            status_code=500,
            detail="ASSEMBLYAI_API_KEY not configured. See backend/.env.example",
        )

    try:
        agent_id = await get_or_create_agent()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Mint a token valid for 5 minutes (300s).
    # max_session_duration_seconds caps the voice session to 30 minutes.
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            AAI_TOKEN_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            params={
                "expires_in_seconds": "300",
                "max_session_duration_seconds": "1800",
            },
        )
        if not resp.is_success:
            logger.error(f"Token mint failed: {resp.status_code} {resp.text}")
            raise HTTPException(
                status_code=502,
                detail=f"Failed to mint AssemblyAI token: {resp.status_code}",
            )
        data = resp.json()

    return TokenResponse(token=data["token"], agent_id=agent_id)
