"""AI Trading Copilot — advisory natural-language interface."""

from app.services.copilot.engine import (
    CopilotController, CopilotResponse, CopilotContext,
    classify_intent, INTENT_KEYWORDS,
)
from app.services.copilot.service import CopilotService

__all__ = [
    "CopilotController", "CopilotResponse", "CopilotContext",
    "classify_intent", "INTENT_KEYWORDS", "CopilotService",
]
