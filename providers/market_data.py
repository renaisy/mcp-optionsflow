"""
MarketData.app data provider
Free tier: Limited requests, good for options data
"""

import aiohttp
import os
from typing import Optional, List
from datetime import datetime, timedelta
import logging
import json

from .base import (
    DataProvider, StockInfo, OptionChain, OptionContract,
    RateLimitError, DataProviderError
)

logger = logging.getLogger("options-analytics")


class MarketDataProvider(DataProvider):
    """MarketData.app data provider (free tier available)"""
    
    BASE_URL = "https://api.marketdata.app/v1"
    
    def __init__(self, api_token: Optional[str] = None):
        super().__init__("MarketData.app", priority=90)
        self.api_token = api_token or os.getenv("MARKET_DATA_API_KEY")
        self._rate_limit_cooldown = 60

    def is_available(self) -> bool:
        """Check if provider has API token and is not rate limited"""
        if not self.api_token:
            return False
        return super().is_available()
    
    async def _make_request(self, endpoint: str) -> dict:
        """Make API request to MarketData.app"""
        url = f"{self.BASE_URL}{endpoint}"
        
        headers = {}
        if self.api_token:
            headers['Authorization'] = f'Bearer {self.api_token}'
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 429:
                    self.mark_rate_limited(self._rate_limit_cooldown)
                    raise RateLimitError(self.name, self._rate_limit_cooldown)
                
                # 200 OK, 203 Non-Authoritative (some CDNs/proxies use this for success)
                if response.status not in (200, 203):
                    text = await response.text()
                    raise DataProviderError(f"MarketData error {response.status}: {text}")
                
                # MarketData returns JSON or CSV depending on endpoint
                content_type = response.headers.get('Content-Type', '')
                if 'json' in content_type:
                    return await response.json()
                else:
                    text = await response.text()
                    # Try to parse as JSON
                    try:
                        return json.loads(text)
                    except:
                        return {'raw': text}
    
    def _norm_symbol(self, symbol: str) -> str:
        """Strip ^ $ prefix for API path"""
        s = symbol.strip().upper()
        return s.lstrip("^$") if (s.startswith("^") or s.startswith("$")) else s

    async def get_stock_info(self, symbol: str) -> Optional[StockInfo]:
        """Get stock information. 指数 ^VIX 用 stocks/quotes/VIX 尝试（indices 免费版可能不可用）"""
        self._request_count += 1
        
        try:
            norm_sym = self._norm_symbol(symbol)
            # 统一使用 stocks 接口（indices 免费版返回 404）
            data = await self._make_request(f"/stocks/quotes/{norm_sym}/")
            
            # MarketData returns array format (list of dicts)
            if isinstance(data, list) and len(data) > 0:
                quote = data[0]
                return StockInfo(
                    symbol=symbol.upper(),
                    current_price=float(quote.get('last', 0) or quote.get('mid', 0) or 0),
                    previous_close=float(quote.get('previousClose', 0) or quote.get('prev_close', 0) or 0),
                    volume=int(quote.get('volume', 0) or 0),
                    timestamp=datetime.now()
                )
            
            # MarketData dict with array values: {"s":"ok","last":[255.78],"bid":[255.3],...}
            if isinstance(data, dict):
                def _first(val, default=0):
                    if isinstance(val, (list, tuple)) and len(val) > 0:
                        return val[0]
                    return val if val is not None else default
                if 'last' in data or 'price' in data or 'mid' in data:
                    return StockInfo(
                        symbol=symbol.upper(),
                        current_price=float(_first(data.get('last')) or _first(data.get('mid')) or _first(data.get('price')) or 0),
                        previous_close=0,
                        volume=int(_first(data.get('volume'), 0) or 0),
                        timestamp=datetime.now()
                    )
            
            raise DataProviderError(f"Could not parse stock data for {symbol}")
            
        except RateLimitError:
            raise
        except Exception as e:
            self._error_count += 1
            raise DataProviderError(f"MarketData error: {e}")
    
    async def get_expiration_dates(self, symbol: str) -> Optional[List[str]]:
        """Get available expiration dates"""
        self._request_count += 1
        
        try:
            norm_sym = self._norm_symbol(symbol)
            data = await self._make_request(f"/options/expirations/{norm_sym}")
            
            if isinstance(data, list):
                # Convert to date strings
                dates = []
                for item in data:
                    if isinstance(item, str):
                        dates.append(item)
                    elif isinstance(item, dict):
                        exp = item.get('expiration') or item.get('date')
                        if exp:
                            dates.append(exp)
                return sorted(dates)
            
            if isinstance(data, dict) and 'expirations' in data:
                return sorted(data['expirations'])
            
            raise DataProviderError(f"Could not parse expiration dates for {symbol}")
            
        except RateLimitError:
            raise
        except Exception as e:
            self._error_count += 1
            raise DataProviderError(f"MarketData error: {e}")
    
    async def get_option_chain(
        self, 
        symbol: str, 
        expiration_date: str
    ) -> Optional[OptionChain]:
        """Get option chain data - supports MarketData.app array response format"""
        self._request_count += 1
        
        try:
            norm_sym = self._norm_symbol(symbol)
            data = await self._make_request(
                f"/options/chain/{norm_sym}/?expiration={expiration_date}"
            )
            
            if not data or data.get('s') != 'ok':
                raise DataProviderError(f"No option chain for {symbol}")
            
            # Get underlying price from response or stock info
            underlying_prices = data.get('underlyingPrice', [])
            current_price = float(underlying_prices[0]) if underlying_prices and underlying_prices[0] else 0
            if not current_price:
                stock_info = await self.get_stock_info(symbol)
                current_price = stock_info.current_price if stock_info else 0
            
            expiry = datetime.strptime(expiration_date, '%Y-%m-%d')
            dte = (expiry - datetime.now()).days
            
            calls = []
            puts = []
            
            # MarketData returns arrays: optionSymbol, strike, bid, ask, last, openInterest, volume, iv, side...
            strikes = data.get('strike', [])
            sides = data.get('side', [])
            bids = data.get('bid', [])
            asks = data.get('ask', [])
            lasts = data.get('last', [])
            ois = data.get('openInterest', [])
            vols = data.get('volume', [])
            ivs = data.get('iv', [])
            symbols = data.get('optionSymbol', [])
            itms = data.get('inTheMoney', [])
            
            n = len(strikes) if strikes else 0
            for i in range(n):
                side = str(sides[i] if i < len(sides) else 'call').lower()
                iv_val = ivs[i] if i < len(ivs) else 0
                if iv_val is None:
                    iv_val = 0
                contract = OptionContract(
                    strike=float(strikes[i]),
                    last_price=float(lasts[i] if i < len(lasts) and lasts[i] is not None else 0),
                    bid=float(bids[i] if i < len(bids) and bids[i] is not None else 0),
                    ask=float(asks[i] if i < len(asks) and asks[i] is not None else 0),
                    volume=int(vols[i] if i < len(vols) else 0),
                    open_interest=int(ois[i] if i < len(ois) else 0),
                    implied_volatility=float(iv_val),
                    option_type=side,
                    contract_symbol=str(symbols[i] if i < len(symbols) else ''),
                    in_the_money=bool(itms[i] if i < len(itms) else False),
                    expiration_date=expiration_date
                )
                if side == 'call':
                    calls.append(contract)
                else:
                    puts.append(contract)
            
            return OptionChain(
                symbol=symbol.upper(),
                expiration_date=expiration_date,
                underlying_price=current_price,
                days_to_expiration=dte,
                calls=calls,
                puts=puts,
                timestamp=datetime.now()
            )
            
        except RateLimitError:
            raise
        except Exception as e:
            self._error_count += 1
            raise DataProviderError(f"MarketData error: {e}")
    
    async def get_risk_free_rate(self) -> float:
        """Return default rate (MarketData doesn't provide this on free tier)"""
        return 0.05
