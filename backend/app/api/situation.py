from fastapi import APIRouter, Path
from app.risk.models import SituationUpdate, ToolResponse
from app.risk.engine import process_situation_update

router = APIRouter(prefix="/api/situation", tags=["situation"])

@router.post("/{session_id}", response_model=ToolResponse)
async def update_situation(
    update: SituationUpdate,
    session_id: str = Path(..., description="The AssemblyAI session ID")
):
    """
    Called by the frontend proxy when the AssemblyAI agent emits a tool.call with new facts.
    """
    return process_situation_update(session_id, update)
