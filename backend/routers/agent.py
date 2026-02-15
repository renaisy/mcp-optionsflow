"""
Agent routes - LLM chat with tools, config CRUD
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Annotated, List, Dict, Any
import sys
import os
import json
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import get_db, LLMConfig
from backend.models.llm_config import LLMConfigCreate, LLMConfigResponse, ChatRequest
from backend.services.agent_service import chat_with_tools_stream, list_available_models
from backend.routers.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])
security = HTTPBearer()


def _config_to_dict(row: LLMConfig, include_api_key: bool = False) -> Dict[str, Any]:
    out = {
        "id": row.id,
        "user_id": row.user_id,
        "provider": row.provider,
        "base_url": row.base_url,
        "model": row.model,
        "enabled": row.enabled,
    }
    if include_api_key:
        out["api_key"] = row.api_key
    return out


@router.get("/config")
async def get_config(
    user_id: Annotated[int, Depends(get_current_user_id)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get current user's LLM config (api_key not returned)"""
    row = db.query(LLMConfig).filter(LLMConfig.user_id == user_id).first()
    if not row:
        return None
    return _config_to_dict(row, include_api_key=False)


@router.put("/config", response_model=LLMConfigResponse)
async def put_config(
    data: LLMConfigCreate,
    user_id: Annotated[int, Depends(get_current_user_id)],
    db: Annotated[Session, Depends(get_db)],
):
    """Create or update LLM config for current user"""
    row = db.query(LLMConfig).filter(LLMConfig.user_id == user_id).first()
    api_key_val = data.api_key if data.api_key else None
    if row:
        row.provider = data.provider
        row.api_key = api_key_val
        row.base_url = data.base_url
        row.model = data.model
        row.enabled = data.enabled
    else:
        row = LLMConfig(
            user_id=user_id,
            provider=data.provider,
            api_key=api_key_val,
            base_url=data.base_url,
            model=data.model,
            enabled=data.enabled,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return LLMConfigResponse(
        id=row.id,
        user_id=row.user_id,
        provider=row.provider,
        base_url=row.base_url,
        model=row.model,
        enabled=row.enabled,
    )


@router.get("/models")
async def get_models(
    user_id: Annotated[int, Depends(get_current_user_id)],
    db: Annotated[Session, Depends(get_db)],
):
    """List available models for current user's provider with status"""
    row = db.query(LLMConfig).filter(LLMConfig.user_id == user_id).first()
    if not row:
        return []
    config = {
        "provider": row.provider,
        "api_key": row.api_key,
        "base_url": row.base_url,
        "model": row.model,
    }
    return await list_available_models(config)


@router.post("/chat")
async def chat(
    request: ChatRequest,
    user_id: Annotated[int, Depends(get_current_user_id)],
    db: Annotated[Session, Depends(get_db)],
):
    """Stream chat completion with tools. Request: { messages: [{ role, content }], model?: override }"""
    messages = request.messages or []
    if not messages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="messages required")

    row = db.query(LLMConfig).filter(LLMConfig.user_id == user_id, LLMConfig.enabled == True).first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LLM config not set. Configure in Settings first.",
        )

    model_override = (request.model or "").strip() or None
    config = {
        "provider": row.provider,
        "api_key": row.api_key,
        "base_url": row.base_url,
        "model": model_override or row.model,
    }

    def generate():
        try:
            for item in chat_with_tools_stream(messages, config):
                payload = json.dumps(item) if isinstance(item, dict) else json.dumps({"type": "chunk", "content": str(item)})
                yield f"data: {payload}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.exception("Agent chat stream error: %s", e)
            err_payload = json.dumps({"type": "error", "message": str(e)})
            yield f"data: {err_payload}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
