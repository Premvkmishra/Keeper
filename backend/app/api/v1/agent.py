from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.security.auth import AuthenticatedUser, get_current_user
from backend.app.services.agent_service import AgentService

router = APIRouter(prefix="/agent", tags=["agent"])


class ChatTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=4000)


class ChatBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: Optional[List[ChatTurn]] = None


@router.post("/chat")
def agent_chat(
    body: ChatBody,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = AgentService()
    history = [{"role": t.role, "content": t.content} for t in (body.history or [])]
    return svc.chat(
        db=db,
        household_id=user.household_id,
        user_email=user.email,
        message=body.message,
        history=history,
    )
