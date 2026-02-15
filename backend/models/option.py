"""
Pydantic models for options data
"""
from pydantic import BaseModel, validator
from datetime import datetime
from typing import Optional, List, Dict, Any


class StockInfoResponse(BaseModel):
    """Stock information response"""
    symbol: str
    currentPrice: Optional[float] = None
    previousClose: Optional[float] = None
    open: Optional[float] = None
    dayHigh: Optional[float] = None
    dayLow: Optional[float] = None
    volume: Optional[int] = None
    marketCap: Optional[int] = None
    dividendYield: Optional[float] = None
    fiftyTwoWeekHigh: Optional[float] = None
    fiftyTwoWeekLow: Optional[float] = None
    companyName: Optional[str] = None


class OptionData(BaseModel):
    """Individual option data"""
    contractSymbol: str
    strike: float
    lastPrice: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    change: Optional[float] = None
    percentChange: Optional[float] = None
    volume: Optional[int] = None
    openInterest: Optional[int] = None
    impliedVolatility: Optional[float] = None
    inTheMoney: Optional[bool] = None
    contractSize: Optional[str] = None
    expiration: Optional[str] = None
    lastTradeDate: Optional[str] = None
    option_type: Optional[str] = None
    underlying_price: Optional[float] = None
    
    # Greeks (calculated later)
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None


class OptionChainResponse(BaseModel):
    """Option chain response"""
    symbol: str
    expiration_date: str
    underlying_price: Optional[float] = None
    calls: List[Dict[str, Any]] = []
    puts: List[Dict[str, Any]] = []
    timestamp: str


class ExpirationDatesResponse(BaseModel):
    """Expiration dates response"""
    symbol: str
    expiration_dates: List[str]


class FilteredOptionsRequest(BaseModel):
    """Request for filtered options"""
    symbol: str
    expiration_date: Optional[str] = None
    option_type: str = "call"  # 'call' or 'put'
    min_volume: Optional[int] = None
    min_open_interest: Optional[int] = None
    min_delta: Optional[float] = None
    max_delta: Optional[float] = None
    strike_min: Optional[float] = None
    strike_max: Optional[float] = None
    
    @validator('option_type')
    def validate_option_type(cls, v):
        if v.lower() not in ['call', 'put']:
            raise ValueError('option_type must be "call" or "put"')
        return v.lower()
    
    @validator('symbol')
    def validate_symbol(cls, v):
        if not v or not v.replace(' ', '').isalnum():
            raise ValueError('Symbol must be alphanumeric')
        return v.upper()
    
    def get_strike_range(self) -> Optional[tuple]:
        """Get strike range tuple"""
        if self.strike_min is not None and self.strike_max is not None:
            return (self.strike_min, self.strike_max)
        return None
