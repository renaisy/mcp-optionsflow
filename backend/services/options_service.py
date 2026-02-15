"""
Options data service - Fetch and cache options data with multi-source failover
"""
import logging
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.config import (
    CACHE_TTL_STOCK,
    CACHE_TTL_OPTION_CHAIN,
    CACHE_TTL_EXPIRATIONS,
    CACHE_TTL_RATE,
)
from backend.utils.cache import SimpleCache

logger = logging.getLogger(__name__)

# Try to use multi-source (providers)
try:
    from backend.utils.data_source import (
        get_stock_info_multi,
        get_expiration_dates_multi,
        get_option_chain_multi,
        get_risk_free_rate_multi,
        get_sources_status,
    )
    MULTI_SOURCE_AVAILABLE = True
except ImportError:
    MULTI_SOURCE_AVAILABLE = False

# Lazy import to avoid circular dependency
def _get_greeks_calculator():
    from optionsflow import GreeksCalculator
    return GreeksCalculator()

# Initialize caches with different TTLs to reduce data source API calls
_stock_cache = SimpleCache(ttl_seconds=CACHE_TTL_STOCK)
_option_chain_cache = SimpleCache(ttl_seconds=CACHE_TTL_OPTION_CHAIN)
_exp_cache = SimpleCache(ttl_seconds=CACHE_TTL_EXPIRATIONS)
_rate_cache = SimpleCache(ttl_seconds=CACHE_TTL_RATE)


class OptionsService:
    """Service for fetching options data"""
    
    @staticmethod
    def get_stock_info(symbol: str) -> Optional[Dict[str, Any]]:
        """Get stock information (multi-source with yfinance fallback)"""
        cache_key = f"stock_info_{symbol}"
        cached = _stock_cache.get(cache_key)
        if cached:
            return cached

        if MULTI_SOURCE_AVAILABLE:
            result = get_stock_info_multi(symbol)
            if result:
                _stock_cache.set(cache_key, result)
                return result

        try:
            ticker = yf.Ticker(symbol.upper())
            info = ticker.info
            
            stock_data = {
                "symbol": symbol.upper(),
                "currentPrice": info.get("currentPrice") or info.get("regularMarketPrice"),
                "previousClose": info.get("previousClose"),
                "open": info.get("regularMarketOpen"),
                "dayHigh": info.get("dayHigh"),
                "dayLow": info.get("dayLow"),
                "volume": info.get("volume"),
                "marketCap": info.get("marketCap"),
                "dividendYield": info.get("dividendYield", 0),
                "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
                "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
                "companyName": info.get("longName") or info.get("shortName"),
            }
            
            _stock_cache.set(cache_key, stock_data)
            return stock_data
            
        except Exception as e:
            logger.error("Error fetching stock info for %s: %s", symbol, e)
            return None
    
    @staticmethod
    def get_expiration_dates(symbol: str) -> Optional[List[str]]:
        """Get available expiration dates (multi-source with yfinance fallback)"""
        cache_key = f"exp_dates_{symbol}"
        cached = _exp_cache.get(cache_key)
        if cached:
            return cached

        if MULTI_SOURCE_AVAILABLE:
            result = get_expiration_dates_multi(symbol)
            if result:
                _exp_cache.set(cache_key, result)
                return result

        try:
            ticker = yf.Ticker(symbol.upper())
            exp_dates = ticker.options
            
            if exp_dates:
                _exp_cache.set(cache_key, list(exp_dates))
                return list(exp_dates)
            
            return None
            
        except Exception as e:
            logger.error("Error fetching expiration dates for %s: %s", symbol, e)
            return None
    
    @staticmethod
    def get_option_chain(
        symbol: str,
        expiration_date: Optional[str] = None,
        option_type: Optional[str] = None  # 'call' or 'put'
    ) -> Optional[Dict[str, Any]]:
        """Get option chain data"""
        
        # Get expiration dates if not provided
        if not expiration_date:
            exp_dates = OptionsService.get_expiration_dates(symbol)
            if not exp_dates:
                return None
            expiration_date = exp_dates[0]  # Use nearest expiration
        
        cache_key = f"option_chain_{symbol}_{expiration_date}"
        cached = _option_chain_cache.get(cache_key)
        if cached:
            chain_data = cached
        else:
            chain_data = None
            if MULTI_SOURCE_AVAILABLE:
                chain_data = get_option_chain_multi(symbol, expiration_date)
                if chain_data:
                    _option_chain_cache.set(cache_key, chain_data)

            if not chain_data:
                try:
                    ticker = yf.Ticker(symbol.upper())
                    option_chain = ticker.option_chain(expiration_date)
                    if option_chain is None:
                        return None
                    current_price = OptionsService.get_stock_info(symbol)
                    underlying_price = current_price.get("currentPrice") if current_price else None
                    calls_data = []
                    if not option_chain.calls.empty:
                        calls_df = option_chain.calls.copy()
                        calls_df['option_type'] = 'call'
                        calls_df['underlying_price'] = underlying_price
                        calls_data = calls_df.to_dict('records')
                    puts_data = []
                    if not option_chain.puts.empty:
                        puts_df = option_chain.puts.copy()
                        puts_df['option_type'] = 'put'
                        puts_df['underlying_price'] = underlying_price
                        puts_data = puts_df.to_dict('records')
                    chain_data = {
                        "symbol": symbol.upper(),
                        "expiration_date": expiration_date,
                        "underlying_price": underlying_price,
                        "calls": calls_data,
                        "puts": puts_data,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    _option_chain_cache.set(cache_key, chain_data)
                except Exception as e:
                    logger.error("Error fetching option chain for %s: %s", symbol, e)
                    chain_data = None
        
        # Filter by option type if specified
        if option_type:
            if option_type.lower() == 'call':
                chain_data['puts'] = []
            elif option_type.lower() == 'put':
                chain_data['calls'] = []
        
        return chain_data
    
    @staticmethod
    def get_filtered_options(
        symbol: str,
        expiration_date: str,
        option_type: str,
        min_volume: Optional[int] = None,
        min_open_interest: Optional[int] = None,
        min_delta: Optional[float] = None,
        max_delta: Optional[float] = None,
        strike_range: Optional[tuple] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """Get filtered option chain data"""
        
        chain_data = OptionsService.get_option_chain(symbol, expiration_date, option_type)
        
        if not chain_data:
            return None
        
        options = chain_data.get('calls' if option_type == 'call' else 'puts', [])
        
        # Apply filters
        filtered = []
        for opt in options:
            # Volume filter
            if min_volume and opt.get('volume', 0) < min_volume:
                continue
            
            # Open interest filter
            if min_open_interest and opt.get('openInterest', 0) < min_open_interest:
                continue
            
            # Delta filter (if available)
            delta = abs(opt.get('delta', 0)) if 'delta' in opt else None
            if delta is not None:
                if min_delta is not None and delta < min_delta:
                    continue
                if max_delta is not None and delta > max_delta:
                    continue
            
            # Strike range filter
            if strike_range:
                strike = opt.get('strike', 0)
                if strike < strike_range[0] or strike > strike_range[1]:
                    continue
            
            filtered.append(opt)
        
        return filtered

    @staticmethod
    def get_option_chain_with_greeks(
        symbol: str,
        expiration_date: Optional[str] = None,
        option_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get option chain with calculated Greeks for visualization."""
        chain_data = OptionsService.get_option_chain(symbol, expiration_date, option_type)
        if not chain_data:
            return None

        calculator = _get_greeks_calculator()
        risk_free_rate = OptionsService.get_risk_free_rate()
        stock_info = OptionsService.get_stock_info(symbol)
        div_yield = float(stock_info.get('dividendYield', 0) or 0) if stock_info else 0
        current_price = chain_data.get('underlying_price')
        if not current_price:
            return None

        from datetime import datetime
        exp_date = chain_data.get('expiration_date')
        exp_dt = pd.to_datetime(exp_date)
        now = datetime.now()
        dte_days = (exp_dt.replace(tzinfo=None) - now).total_seconds() / (24 * 60 * 60)

        def add_greeks(rows: list) -> list:
            out = []
            for r in rows:
                iv = r.get('impliedVolatility') or r.get('implied_volatility')
                if iv is None or (isinstance(iv, float) and (iv <= 0 or pd.isna(iv))):
                    out.append({**r, 'delta': None, 'gamma': None, 'theta': None, 'vega': None})
                    continue
                try:
                    greeks = calculator.calculate_greeks(
                        float(current_price), float(r['strike']),
                        float(dte_days) / 365, risk_free_rate, float(iv), div_yield,
                        'CALL' if r.get('option_type') == 'call' else 'PUT'
                    )
                except Exception:
                    greeks = {'delta': None, 'gamma': None, 'theta': None, 'vega': None}
                out.append({**r, **greeks})
            return out

        chain_data = dict(chain_data)
        chain_data['calls'] = add_greeks(chain_data.get('calls', []))
        chain_data['puts'] = add_greeks(chain_data.get('puts', []))
        return chain_data
    
    @staticmethod
    def get_risk_free_rate(market: Optional[str] = None) -> float:
        """Get risk-free rate. market='cn' for China (~2.5%), else US (T-Bill)."""
        cache_key = f"risk_free_rate_{market or 'us'}"
        cached = _rate_cache.get(cache_key)
        if cached is not None:
            return cached

        if market == "cn":
            if MULTI_SOURCE_AVAILABLE:
                rate = get_risk_free_rate_multi("cn")
                _rate_cache.set(cache_key, rate)
                return rate
            _rate_cache.set(cache_key, 0.025)
            return 0.025

        if MULTI_SOURCE_AVAILABLE:
            rate = get_risk_free_rate_multi()
            if rate > 0:
                _rate_cache.set(cache_key, rate)
                return rate

        try:
            ticker = yf.Ticker("^IRX")
            rate = ticker.info.get("regularMarketPrice", 5.0) / 100.0
            _rate_cache.set(cache_key, rate)
            return rate
        except Exception as e:
            logger.warning("Could not fetch risk-free rate, using default: %s", e)
            default_rate = 0.05
            _rate_cache.set(cache_key, default_rate)
            return default_rate
