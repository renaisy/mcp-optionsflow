"""
Pydantic models for strategy analysis
"""
from pydantic import BaseModel, validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class StrategyAnalysisRequest(BaseModel):
    """Request for strategy analysis"""
    symbol: str
    strategy_type: str  # ccs, pcs, csp, cc
    expiration_date: Optional[str] = None
    delta_target: Optional[float] = None
    width_pct: Optional[float] = None
    save_result: Optional[bool] = False
    
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
    
    @validator('width_pct')
    def validate_width_pct(cls, v):
        if v is not None and (v <= 0 or v >= 1):
            raise ValueError('width_pct must be between 0 and 1')
        return v
    
    @validator('delta_target')
    def validate_delta_target(cls, v):
        if v is not None and (v <= 0 or v >= 1):
            raise ValueError('delta_target must be between 0 and 1')
        return v


class MultiStrategyRequest(BaseModel):
    """Request for multiple strategy analysis"""
    symbol: str
    strategies: List[Dict[str, Any]]
    save_results: Optional[bool] = False
    
    @validator('symbol')
    def validate_symbol(cls, v):
        if not v or not v.replace(' ', '').isalnum():
            raise ValueError('Symbol must be alphanumeric')
        return v.upper()
    
    @validator('strategies')
    def validate_strategies(cls, v):
        if not v or len(v) == 0:
            raise ValueError('strategies list cannot be empty')
        return v


class StrategyAnalysisResponse(BaseModel):
    """Strategy analysis response"""
    symbol: str
    strategy_type: str
    expiration_date: Optional[str] = None
    current_price: Optional[float] = None
    timestamp: str
    
    # Strategy-specific results
    short_strike: Optional[float] = None
    long_strike: Optional[float] = None
    premium: Optional[float] = None
    max_profit: Optional[float] = None
    max_loss: Optional[float] = None
    breakeven: Optional[float] = None
    probability_of_profit: Optional[float] = None
    
    # Greeks
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None
    
    # Additional info
    days_to_expiration: Optional[int] = None
    implied_volatility: Optional[float] = None
    
    # Full result
    full_analysis: Optional[Dict[str, Any]] = None


class StrategyComparisonResponse(BaseModel):
    """Response for multiple strategy comparison"""
    symbol: str
    strategies: List[Dict[str, Any]]
    timestamp: str


class PnlScenariosRequest(BaseModel):
    """Request for P&L scenario analysis"""
    symbol: str
    strategy: str  # ccs, pcs, csp, cc
    expiration_date: str
    price_range_pct: Optional[float] = 0.20
    steps: Optional[int] = 20

    @validator('strategy')
    def validate_strategy(cls, v):
        if v.lower() not in ['ccs', 'pcs', 'csp', 'cc']:
            raise ValueError('Strategy must be one of: ccs, pcs, csp, cc')
        return v.lower()

    @validator('symbol')
    def validate_symbol(cls, v):
        if not v or not v.replace(' ', '').isalnum():
            raise ValueError('Symbol must be alphanumeric')
        return v.upper()


class FindBestStrategiesRequest(BaseModel):
    """Request for find best strategies"""
    symbol: str
    expiration_date: Optional[str] = None
    min_probability_profit: Optional[float] = 0.60
    max_risk_reward_ratio: Optional[float] = 3.0
    strategy_preference: Optional[str] = "any"

    @validator('symbol')
    def validate_symbol(cls, v):
        if not v or not v.replace(' ', '').isalnum():
            raise ValueError('Symbol must be alphanumeric')
        return v.upper()

    @validator('strategy_preference')
    def validate_preference(cls, v):
        if v and v.lower() not in ['bullish', 'bearish', 'neutral', 'any']:
            raise ValueError('Preference must be one of: bullish, bearish, neutral, any')
        return (v or 'any').lower()
