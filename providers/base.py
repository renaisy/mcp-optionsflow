"""
Base class for options data providers
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import time


class DataProviderError(Exception):
    """Base error for data providers"""
    pass


class RateLimitError(DataProviderError):
    """Rate limit exceeded error"""
    def __init__(self, provider: str, retry_after: Optional[int] = None):
        self.provider = provider
        self.retry_after = retry_after
        super().__init__(f"{provider} rate limit exceeded. Retry after {retry_after}s")


@dataclass
class StockInfo:
    """Stock information data class"""
    symbol: str
    current_price: float
    previous_close: Optional[float] = None
    day_open: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    volume: Optional[int] = None
    market_cap: Optional[int] = None
    pe_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    company_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    timestamp: Optional[datetime] = None


@dataclass
class OptionContract:
    """Option contract data class"""
    strike: float
    last_price: float
    bid: float
    ask: float
    volume: int
    open_interest: int
    implied_volatility: float
    option_type: str  # 'call' or 'put'
    contract_symbol: str
    in_the_money: bool = False
    expiration_date: Optional[str] = None


@dataclass
class OptionChain:
    """Option chain data class"""
    symbol: str
    expiration_date: str
    underlying_price: float
    days_to_expiration: int
    calls: List[OptionContract]
    puts: List[OptionContract]
    risk_free_rate: Optional[float] = None
    dividend_yield: Optional[float] = None
    timestamp: Optional[datetime] = None


class DataProvider(ABC):
    """Abstract base class for data providers"""
    
    def __init__(self, name: str, priority: int = 0):
        self.name = name
        self.priority = priority  # Higher priority = preferred
        self._last_error: Optional[Exception] = None
        self._rate_limited_until: float = 0
        self._request_count: int = 0
        self._error_count: int = 0
    
    @abstractmethod
    async def get_stock_info(self, symbol: str) -> Optional[StockInfo]:
        """Get stock information"""
        pass
    
    @abstractmethod
    async def get_expiration_dates(self, symbol: str) -> Optional[List[str]]:
        """Get available expiration dates"""
        pass
    
    @abstractmethod
    async def get_option_chain(
        self, 
        symbol: str, 
        expiration_date: str
    ) -> Optional[OptionChain]:
        """Get option chain for specific expiration"""
        pass
    
    @abstractmethod
    async def get_risk_free_rate(self) -> float:
        """Get current risk-free rate"""
        pass
    
    def is_available(self) -> bool:
        """Check if provider is available (not rate limited)"""
        return time.time() > self._rate_limited_until
    
    def mark_rate_limited(self, duration_seconds: int = 300):
        """Mark provider as rate limited"""
        self._rate_limited_until = time.time() + duration_seconds
        self._error_count += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get provider statistics"""
        return {
            "name": self.name,
            "priority": self.priority,
            "is_available": self.is_available(),
            "request_count": self._request_count,
            "error_count": self._error_count,
            "rate_limited_until": self._rate_limited_until
        }
