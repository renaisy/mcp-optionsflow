"""
Alpha Vantage data provider
Free tier: 25 requests/day, 5 requests/minute
"""

import aiohttp
import os
from typing import Optional, List
from datetime import datetime
import logging

from .base import (
    DataProvider, StockInfo, OptionChain, OptionContract,
    RateLimitError, DataProviderError
)

logger = logging.getLogger("options-analytics")


class AlphaVantageProvider(DataProvider):
    """Alpha Vantage data provider (free tier with limits)"""
    
    BASE_URL = "https://www.alphavantage.co/query"
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__("Alpha Vantage", priority=80)
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        self._rate_limit_cooldown = 60  # 1 minute for rate limit
        self._requests_per_day = 0
        self._max_requests_per_day = 25  # Free tier limit
    
    def is_available(self) -> bool:
        """Check if provider has API key and is not rate limited"""
        if not self.api_key:
            return False
        if self._requests_per_day >= self._max_requests_per_day:
            return False
        return super().is_available()
    
    async def _make_request(self, params: dict) -> dict:
        """Make API request to Alpha Vantage"""
        if not self.api_key:
            raise DataProviderError("Alpha Vantage API key not configured")
        
        params['apikey'] = self.api_key
        
        async with aiohttp.ClientSession() as session:
            async with session.get(self.BASE_URL, params=params) as response:
                data = await response.json()
                
                # Check for rate limit
                if 'Note' in data and 'rate limit' in data['Note'].lower():
                    self.mark_rate_limited(self._rate_limit_cooldown)
                    raise RateLimitError(self.name, self._rate_limit_cooldown)
                
                # Check for error
                if 'Error Message' in data:
                    raise DataProviderError(f"Alpha Vantage error: {data['Error Message']}")
                
                self._requests_per_day += 1
                return data
    
    async def get_stock_info(self, symbol: str) -> Optional[StockInfo]:
        """Get stock information"""
        self._request_count += 1
        
        try:
            # Get quote data
            data = await self._make_request({
                'function': 'GLOBAL_QUOTE',
                'symbol': symbol.upper()
            })
            
            quote = data.get('Global Quote', {})
            if not quote:
                raise DataProviderError(f"No data for {symbol}")
            
            return StockInfo(
                symbol=symbol.upper(),
                current_price=float(quote.get('05. price', 0)),
                previous_close=float(quote.get('08. previous close', 0)),
                day_open=float(quote.get('02. open', 0)),
                day_high=float(quote.get('03. high', 0)),
                day_low=float(quote.get('04. low', 0)),
                volume=int(quote.get('06. volume', 0)),
                timestamp=datetime.now()
            )
            
        except RateLimitError:
            raise
        except Exception as e:
            self._error_count += 1
            raise DataProviderError(f"Alpha Vantage error: {e}")
    
    async def get_expiration_dates(self, symbol: str) -> Optional[List[str]]:
        """Alpha Vantage doesn't support options expiration dates well"""
        # Alpha Vantage has limited options support
        raise DataProviderError("Alpha Vantage does not support options expiration dates")
    
    async def get_option_chain(
        self, 
        symbol: str, 
        expiration_date: str
    ) -> Optional[OptionChain]:
        """Alpha Vantage has limited options support"""
        raise DataProviderError("Alpha Vantage does not support full option chains")
    
    async def get_risk_free_rate(self) -> float:
        """Return default rate (Alpha Vantage doesn't provide this)"""
        return 0.05
