"""
Data Source Manager - Automatic failover between multiple data sources
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from .base import (
    DataProvider, StockInfo, OptionChain,
    RateLimitError, DataProviderError
)
from .yahoo_finance import YahooFinanceProvider
from .alpha_vantage import AlphaVantageProvider
from .market_data import MarketDataProvider
from .akshare_provider import AKShareProvider

logger = logging.getLogger("options-analytics")


class DataSourceManager:
    """
    Manages multiple data sources with automatic failover.
    Automatically switches to backup source when primary is rate limited.
    """
    
    def __init__(self, alpha_vantage_key: Optional[str] = None, market_data_key: Optional[str] = None):
        self.providers: List[DataProvider] = []
        self._setup_providers(alpha_vantage_key, market_data_key)
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 60  # seconds
    
    def _setup_providers(self, alpha_vantage_key: Optional[str], market_data_key: Optional[str]):
        """Initialize data providers in priority order"""
        # Primary: Yahoo Finance (free, most comprehensive)
        self.providers.append(YahooFinanceProvider())
        
        # Secondary: MarketData.app (good options support, needs API key for production)
        market_provider = MarketDataProvider(api_token=market_data_key)
        self.providers.append(market_provider)
        
        # Tertiary: Alpha Vantage (stock only, needs API key, 25 req/day free)
        alpha_provider = AlphaVantageProvider(api_key=alpha_vantage_key)
        self.providers.append(alpha_provider)
        
        # China market: AKShare (510050/510300/510500/588000/588080 等 A 股 ETF 期权)
        try:
            self.providers.append(AKShareProvider())
        except Exception as e:
            logger.warning(f"AKShare provider not loaded: {e}")
        
        logger.info(f"Initialized {len(self.providers)} data providers: {[p.name for p in self.providers]}")
    
    def _get_available_providers(self) -> List[DataProvider]:
        """Get list of available (non-rate-limited) providers"""
        available = [p for p in self.providers if p.is_available()]
        return sorted(available, key=lambda x: x.priority, reverse=True)
    
    async def get_stock_info(self, symbol: str) -> Optional[StockInfo]:
        """Get stock info with automatic failover"""
        errors = []
        
        for provider in self._get_available_providers():
            try:
                logger.debug(f"Trying {provider.name} for stock info: {symbol}")
                result = await provider.get_stock_info(symbol)
                if result:
                    logger.info(f"Got stock info from {provider.name} for {symbol}")
                    return result
            except RateLimitError as e:
                logger.warning(f"{provider.name} rate limited: {e.retry_after}s")
                errors.append(str(e))
                continue
            except DataProviderError as e:
                logger.warning(f"{provider.name} error: {e}")
                errors.append(str(e))
                continue
            except Exception as e:
                logger.error(f"{provider.name} unexpected error: {e}")
                errors.append(str(e))
                continue
        
        logger.error(f"All providers failed for stock info {symbol}: {errors}")
        return None
    
    async def get_expiration_dates(self, symbol: str) -> Optional[List[str]]:
        """Get expiration dates with automatic failover"""
        errors = []
        
        for provider in self._get_available_providers():
            try:
                logger.debug(f"Trying {provider.name} for expiration dates: {symbol}")
                result = await provider.get_expiration_dates(symbol)
                if result:
                    logger.info(f"Got {len(result)} expiration dates from {provider.name} for {symbol}")
                    return result
            except RateLimitError as e:
                logger.warning(f"{provider.name} rate limited: {e.retry_after}s")
                errors.append(str(e))
                continue
            except DataProviderError as e:
                logger.warning(f"{provider.name} error: {e}")
                errors.append(str(e))
                continue
            except Exception as e:
                logger.error(f"{provider.name} unexpected error: {e}")
                errors.append(str(e))
                continue
        
        logger.error(f"All providers failed for expiration dates {symbol}: {errors}")
        return None
    
    async def get_option_chain(
        self, 
        symbol: str, 
        expiration_date: str
    ) -> Optional[OptionChain]:
        """Get option chain with automatic failover"""
        errors = []
        
        for provider in self._get_available_providers():
            try:
                logger.debug(f"Trying {provider.name} for option chain: {symbol} {expiration_date}")
                result = await provider.get_option_chain(symbol, expiration_date)
                if result:
                    logger.info(f"Got option chain from {provider.name} for {symbol}")
                    return result
            except RateLimitError as e:
                logger.warning(f"{provider.name} rate limited: {e.retry_after}s")
                errors.append(str(e))
                continue
            except DataProviderError as e:
                logger.warning(f"{provider.name} error: {e}")
                errors.append(str(e))
                continue
            except Exception as e:
                logger.error(f"{provider.name} unexpected error: {e}")
                errors.append(str(e))
                continue
        
        logger.error(f"All providers failed for option chain {symbol}: {errors}")
        return None
    
    async def get_risk_free_rate(self) -> float:
        """Get risk-free rate with automatic failover"""
        for provider in self._get_available_providers():
            try:
                rate = await provider.get_risk_free_rate()
                if rate > 0:
                    return rate
            except Exception as e:
                logger.warning(f"{provider.name} error getting risk-free rate: {e}")
                continue
        
        return 0.05  # Default fallback
    
    def get_provider_stats(self) -> List[Dict[str, Any]]:
        """Get statistics for all providers"""
        return [p.get_stats() for p in self.providers]
    
    def get_status(self) -> Dict[str, Any]:
        """Get overall status of data sources"""
        available = self._get_available_providers()
        return {
            "total_providers": len(self.providers),
            "available_providers": len(available),
            "providers": self.get_provider_stats(),
            "timestamp": datetime.utcnow().isoformat()
        }
