"""Copilot Persistence Service."""

from __future__ import annotations
from typing import TYPE_CHECKING
import json
import structlog
from sqlalchemy import select, desc, func
from app.models.copilot import (
    CopilotSession, Conversation, ConversationMessage, CopilotFeedback,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class CopilotService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Sessions ---

    async def create_session(self, user_id: int = 0) -> dict:
        s = CopilotSession(user_id=user_id, status="active")
        self.session.add(s); await self.session.flush()
        return {"id": s.id, "user_id": s.user_id, "status": s.status}

    async def get_session(self, session_id: int) -> dict | None:
        result = await self.session.execute(select(CopilotSession).where(CopilotSession.id == session_id))
        s = result.scalar_one_or_none()
        if not s:
            return None
        return {"id": s.id, "user_id": s.user_id, "status": s.status,
                "context": json.loads(s.context_json) if s.context_json else {}}

    async def update_session(self, session_id: int, updates: dict):
        result = await self.session.execute(select(CopilotSession).where(CopilotSession.id == session_id))
        s = result.scalar_one_or_none()
        if s:
            for k, v in updates.items():
                if hasattr(s, k): setattr(s, k, v)
            await self.session.flush()

    # --- Conversations ---

    async def create_conversation(self, session_id: int, title: str = "New Conversation") -> dict:
        c = Conversation(session_id=session_id, title=title)
        self.session.add(c); await self.session.flush()
        return {"id": c.id, "session_id": c.session_id, "title": c.title}

    async def get_conversations(self, session_id: int) -> list[dict]:
        result = await self.session.execute(
            select(Conversation).where(Conversation.session_id == session_id)
            .order_by(desc(Conversation.created_at))
        )
        return [{"id": c.id, "session_id": c.session_id, "title": c.title}
                for c in result.scalars().all()]

    # --- Messages ---

    async def add_message(self, conversation_id: int, role: str, content: str,
                          intent: str = "", source_services: str = "") -> dict:
        m = ConversationMessage(
            conversation_id=conversation_id, role=role, content=content,
            intent=intent, source_services=source_services,
        )
        self.session.add(m); await self.session.flush()
        return {"id": m.id, "role": m.role, "content": m.content[:100] + "..." if len(m.content) > 100 else m.content}

    async def get_messages(self, conversation_id: int, limit: int = 100) -> list[dict]:
        result = await self.session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at).limit(limit)
        )
        return [{"id": m.id, "role": m.role, "content": m.content,
                 "intent": m.intent, "source_services": m.source_services}
                for m in result.scalars().all()]

    async def search_messages(self, query: str, limit: int = 50) -> list[dict]:
        result = await self.session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.content.contains(query))
            .order_by(desc(ConversationMessage.created_at)).limit(limit)
        )
        return [{"id": m.id, "role": m.role, "content": m.content[:200]}
                for m in result.scalars().all()]

    # --- Feedback ---

    async def add_feedback(self, message_id: int, rating: int, comment: str = "") -> dict:
        f = CopilotFeedback(message_id=message_id, rating=rating, comment=comment)
        self.session.add(f); await self.session.flush()
        return {"id": f.id, "message_id": f.message_id, "rating": f.rating}

    async def get_feedback(self, message_id: int) -> list[dict]:
        result = await self.session.execute(
            select(CopilotFeedback).where(CopilotFeedback.message_id == message_id)
        )
        return [{"id": f.id, "rating": f.rating, "comment": f.comment}
                for f in result.scalars().all()]
