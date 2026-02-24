"""
Finnhub data provider - Free tier: 60 calls/min
Stock quote, company profile. Options require paid tier.
Get free API key: https://finnhub.io/register
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


class FinnhubProvider(DataProvider):
    """Finnhub.io data provider (free: 60 calls/min, stock data only in free tier)"""

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__("Finnhub", priority=99)  # 仅次于 Yahoo，Yahoo 限流时优先用 Finnhub 获取股票报价
        self.api_key = api_key or os.getenv("FINNHUB_API_KEY")
        self._rate_limit_cooldown = 60

    def is_available(self) -> bool:
        """Check if provider has API key and is not rate limited"""
        if not self.api_key:
            return False
        return super().is_available()

    async def _make_request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        endpoint = endpoint.lstrip("/")
        url = f"{self.BASE_URL.rstrip('/')}/{endpoint}"
        params = params or {}
        params["token"] = self.api_key

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 429:
                    self.mark_rate_limited(self._rate_limit_cooldown)
                    raise RateLimitError(self.name, self._rate_limit_cooldown)
                if response.status != 200:
                    text = await response.text()
                    raise DataProviderError(f"Finnhub error {response.status}: {text}")

                data = await response.json()
                if isinstance(data, dict) and data.get("s") == "no_data":
                    raise DataProviderError(f"No data for symbol")
                return data

    def _finnhub_symbol(self, symbol: str) -> str:
        """Finnhub 使用无前缀的 symbol，如 VIX 而非 ^VIX"""
        s = symbol.strip().upper()
        return s.lstrip("^$") if s.startswith("^") or s.startswith("$") else s

    async def get_stock_info(self, symbol: str) -> Optional[StockInfo]:
        """Get stock quote from Finnhub"""
        self._request_count += 1

        try:
            sym = self._finnhub_symbol(symbol)
            quote = await self._make_request("quote", {"symbol": sym})
            # quote: {c: current, d: change, dp: percent, h: high, l: low, o: open, pc: prev close, t: timestamp}
            current = quote.get("c")
            if current is None:
                raise DataProviderError(f"No price for {symbol}")

            # Get company profile for name (指数无 profile，会静默失败)
            profile = {}
            try:
                profile = await self._make_request("stock/profile2", {"symbol": sym})
            except Exception:
                pass

            return StockInfo(
                symbol=symbol.upper(),
                current_price=float(current),
                previous_close=quote.get("pc"),
                day_open=quote.get("o"),
                day_high=quote.get("h"),
                day_low=quote.get("l"),
                volume=None,  # Quote doesn't include volume
                market_cap=profile.get("marketCapitalization"),
                company_name=profile.get("name"),
                timestamp=datetime.now(),
            )
        except RateLimitError:
            raise
        except DataProviderError:
            raise
        except Exception as e:
            self._error_count += 1
            raise DataProviderError(f"Finnhub error: {e}")

    async def get_expiration_dates(self, symbol: str) -> Optional[List[str]]:
        """Finnhub free tier does not include options - delegate to next provider"""
        raise DataProviderError("Finnhub free tier: options not included")

    async def get_option_chain(
        self, symbol: str, expiration_date: str
    ) -> Optional[OptionChain]:
        """Finnhub free tier does not include options"""
        raise DataProviderError("Finnhub free tier: options not included")

    async def get_risk_free_rate(self) -> float:
        """Use 13-week Treasury from quote - Finnhub has ^IRX"""
        self._request_count += 1
        try:
            quote = await self._make_request("quote", {"symbol": "^IRX"})
            c = quote.get("c")
            if c is not None and float(c) > 0:
                return float(c) / 100.0
        except Exception:
            pass
        return 0.05
