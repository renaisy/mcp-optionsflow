"""
Pydantic models for LLM/Agent configuration
"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any


ProviderType = str  # "openai" | "glm" | "ollama" | "vllm"


class LLMConfigBase(BaseModel):
    """Base LLM config model"""
    provider: str  # openai, glm, ollama, vllm
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: str
    enabled: bool = True


class LLMConfigCreate(LLMConfigBase):
    """LLM config creation model"""
    pass


class LLMConfigUpdate(BaseModel):
    """LLM config update model - all optional"""
    provider: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    enabled: Optional[bool] = None


class LLMConfigResponse(BaseModel):
    """LLM config response - api_key masked or omitted"""
    id: int
    user_id: int
    provider: str
    base_url: Optional[str] = None
    model: str
    enabled: bool

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    """Chat request with messages"""
    messages: List[Dict[str, Any]] = []
    model: Optional[str] = None  # Override config model for this request
