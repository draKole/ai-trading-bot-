"""Copilot API — chat, sessions, history, search, feedback, suggested questions."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.copilot.engine import CopilotController, CopilotContext
from app.services.copilot.service import CopilotService

router = APIRouter()


def get_controller() -> CopilotController:
    return CopilotController()


async def get_service(session: AsyncSession = Depends(get_db)) -> CopilotService:
    return CopilotService(session)


# --- Chat ---

@router.post("/chat")
async def chat(
    prompt: str = Query(..., description="Natural language query"),
    session_id: str | None = Query(None, description="Active session"),
    controller: CopilotController = Depends(get_controller),
):
    """Process a natural-language query and return advisory response."""
    ctx = controller.get_context(session_id) if session_id else None
    response = controller.handle_query(prompt, session_id=session_id, context=ctx)
    return response.to_dict()


# --- Sessions ---

@router.post("/sessions")
async def create_session(service: CopilotService = Depends(get_service)):
    """Create a new copilot session."""
    return await service.create_session()


@router.get("/sessions/{session_id}")
async def get_session(session_id: int, service: CopilotService = Depends(get_service)):
    """Get session details."""
    s = await service.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


@router.delete("/sessions/{session_id}")
async def end_session(
    session_id: int,
    controller: CopilotController = Depends(get_controller),
    service: CopilotService = Depends(get_service),
):
    """End a copilot session."""
    await service.update_session(session_id, {"status": "ended"})
    controller.clear_context(str(session_id))
    return {"status": "ended", "session_id": session_id}


# --- Context ---

@router.get("/sessions/{session_id}/context")
async def get_context(session_id: int, controller: CopilotController = Depends(get_controller)):
    """Get current session context."""
    ctx = controller.get_context(str(session_id))
    return ctx.to_dict()


@router.post("/sessions/{session_id}/context")
async def set_context(
    session_id: int,
    portfolio_id: int | None = Query(None),
    strategy_id: int | None = Query(None),
    account_id: int | None = Query(None),
    time_range: str = Query("today"),
    watchlist_name: str | None = Query(None),
    controller: CopilotController = Depends(get_controller),
):
    """Update session context."""
    controller.set_context(str(session_id), portfolio_id=portfolio_id,
                           strategy_id=strategy_id, account_id=account_id,
                           time_range=time_range, watchlist_name=watchlist_name)
    return controller.get_context(str(session_id)).to_dict()


# --- History ---

@router.get("/history/{session_id}")
async def get_history(session_id: int, controller: CopilotController = Depends(get_controller)):
    """Get conversation history for a session."""
    return controller.get_conversations(str(session_id))


# --- Search ---

@router.get("/search")
async def search_messages(
    q: str = Query(..., description="Search query"),
    limit: int = Query(50, ge=1, le=200),
    service: CopilotService = Depends(get_service),
):
    """Search message history."""
    return await service.search_messages(q, limit=limit)


# --- Feedback ---

@router.post("/feedback")
async def submit_feedback(
    message_id: int = Query(...),
    rating: int = Query(..., ge=1, le=5),
    comment: str = Query(""),
    service: CopilotService = Depends(get_service),
):
    """Submit feedback on a copilot response."""
    return await service.add_feedback(message_id, rating=rating, comment=comment)


@router.get("/feedback/{message_id}")
async def get_feedback(message_id: int, service: CopilotService = Depends(get_service)):
    """Get feedback for a message."""
    return await service.get_feedback(message_id)


# --- Suggested Questions ---

@router.get("/suggestions")
async def suggested_questions(
    session_id: str | None = Query(None),
    controller: CopilotController = Depends(get_controller),
):
    """Get context-aware suggested questions."""
    ctx = controller.get_context(session_id) if session_id else None
    return controller.suggested_questions(context=ctx)


# --- System Context ---

@router.get("/system")
async def system_context(controller: CopilotController = Depends(get_controller)):
    """Get copilot system context (available intents, domains, etc.)."""
    return controller.system_context()
