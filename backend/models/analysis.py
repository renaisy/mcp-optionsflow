"""
Pydantic models for analysis history
"""
from pydantic import BaseModel, validator
from datetime import datetime
from typing import Optional, Dict, Any


class AnalysisCreate(BaseModel):
    """Create analysis record"""
    symbol: str
    strategy_type: str  # ccs, pcs, csp, cc
    expiration_date: str
    current_price: float
    analysis_result: Dict[str, Any]

    @validator('strategy_type')
    def validate_strategy(cls, v):
        valid_strategies = ['ccs', 'pcs', 'csp', 'cc']
        if v.lower() not in valid_strategies:
            raise ValueError(f'Strategy must be one of: {", ".join(valid_strategies)}')
        return v.lower()

    @validator('symbol')
    def validate_symbol(cls, v):
        if not v or not v.replace(' ', '').isalnum():
            raise ValueError('Symbol must be alphanumeric')
        return v.upper()


class AnalysisResponse(BaseModel):
    """Analysis record response"""
    id: int
    user_id: int
    symbol: str
    strategy_type: str
    expiration_date: str
    current_price: float
    analysis_result: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisListResponse(BaseModel):
    """List of analysis records"""
    total: int
    items: list[AnalysisResponse]
