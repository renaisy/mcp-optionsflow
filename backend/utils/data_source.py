"""
Multi-source data integration - Converts provider types to backend format
"""
import asyncio
import logging
import os
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

_data_manager = None


def _get_data_manager():
    """Lazy init DataSourceManager"""
    global _data_manager
    if _data_manager is None:
        try:
            from providers import DataSourceManager
            _data_manager = DataSourceManager(
                alpha_vantage_key=os.getenv("ALPHA_VANTAGE_API_KEY"),
                market_data_key=os.getenv("MARKET_DATA_API_KEY"),
                finnhub_api_key=os.getenv("FINNHUB_API_KEY"),
            )
        except ImportError as e:
            logger.warning("Providers not available: %s", e)
    return _data_manager


def _run_async(coro):
    """Run async in sync context (兼容 FastAPI 已有 event loop)"""
    try:
        asyncio.get_running_loop()
        # 已在 async 上下文中，在独立线程中运行避免冲突
        import concurrent.futures
        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(_run)
            return future.result()
    except RuntimeError:
        return asyncio.run(coro)


def _stock_info_to_dict(info) -> Dict[str, Any]:
    """Convert provider StockInfo to backend dict format"""
    return {
        "symbol": info.symbol,
        "currentPrice": info.current_price,
        "previousClose": getattr(info, "previous_close", None),
        "open": getattr(info, "day_open", None),
        "dayHigh": getattr(info, "day_high", None),
        "dayLow": getattr(info, "day_low", None),
        "volume": getattr(info, "volume", None),
        "marketCap": getattr(info, "market_cap", None),
        "dividendYield": getattr(info, "dividend_yield", 0) or 0,
        "fiftyTwoWeekHigh": getattr(info, "fifty_two_week_high", None),
        "fiftyTwoWeekLow": getattr(info, "fifty_two_week_low", None),
        "companyName": getattr(info, "company_name", None),
    }


def _option_contract_to_dict(c, underlying_price: float) -> Dict[str, Any]:
    """Convert OptionContract to backend option row format"""
    return {
        "strike": c.strike,
        "lastPrice": c.last_price,
        "bid": c.bid,
        "ask": c.ask,
        "volume": c.volume,
        "openInterest": c.open_interest,
        "impliedVolatility": c.implied_volatility,
        "option_type": c.option_type,
        "underlying_price": underlying_price,
        "contractSymbol": getattr(c, "contract_symbol", ""),
        "inTheMoney": getattr(c, "in_the_money", False),
    }


def _option_chain_to_dict(chain) -> Dict[str, Any]:
    """Convert provider OptionChain to backend dict format"""
    from datetime import datetime
    calls = [_option_contract_to_dict(c, chain.underlying_price) for c in chain.calls]
    puts = [_option_contract_to_dict(c, chain.underlying_price) for c in chain.puts]
    return {
        "symbol": chain.symbol,
        "expiration_date": chain.expiration_date,
        "underlying_price": chain.underlying_price,
        "calls": calls,
        "puts": puts,
        "timestamp": datetime.utcnow().isoformat(),
    }


def get_stock_info_multi(symbol: str) -> Optional[Dict[str, Any]]:
    """Get stock info via DataSourceManager with failover"""
    manager = _get_data_manager()
    if not manager:
        return None

    async def _fetch():
        info = await manager.get_stock_info(symbol)
        return _stock_info_to_dict(info) if info else None

    try:
        return _run_async(_fetch())
    except Exception as e:
        logger.warning("Multi-source stock info failed for %s: %s", symbol, e)
        return None


def get_expiration_dates_multi(symbol: str) -> Optional[List[str]]:
    """Get expiration dates via DataSourceManager with failover"""
    manager = _get_data_manager()
    if not manager:
        return None

    async def _fetch():
        return await manager.get_expiration_dates(symbol)

    try:
        return _run_async(_fetch())
    except Exception as e:
        logger.warning("Multi-source expiration dates failed for %s: %s", symbol, e)
        return None


def get_option_chain_multi(symbol: str, expiration_date: str) -> Optional[Dict[str, Any]]:
    """Get option chain via DataSourceManager with failover"""
    manager = _get_data_manager()
    if not manager:
        return None

    async def _fetch():
        chain = await manager.get_option_chain(symbol, expiration_date)
        return _option_chain_to_dict(chain) if chain else None

    try:
        return _run_async(_fetch())
    except Exception as e:
        logger.warning("Multi-source option chain failed for %s: %s", symbol, e)
        return None


def get_risk_free_rate_multi(market: Optional[str] = None) -> float:
    """Get risk-free rate via DataSourceManager. market='cn' for China (AKShare), else US."""
    manager = _get_data_manager()
    if not manager:
        return 0.025 if market == "cn" else 0.05

    async def _fetch():
        if market == "cn":
            # China: try AKShare first (returns 2.5%), else use reference
            for p in manager.providers:
                if p.name == "AKShare":
                    try:
                        rate = await p.get_risk_free_rate()
                        if rate > 0:
                            return rate
                    except Exception:
                        pass
                    break
            return 0.025  # China reference (约2.5%)
        return await manager.get_risk_free_rate()

    try:
        return _run_async(_fetch())
    except Exception as e:
        logger.warning("Multi-source risk-free rate failed: %s", e)
        return 0.025 if market == "cn" else 0.05


def get_sources_status() -> Dict[str, Any]:
    """Get status of all data sources - always returns full provider list"""
    # Fallback when providers not loaded
    fallback_providers = [
        {"name": "Yahoo Finance", "priority": 100, "is_available": True, "note": "Direct (primary)"},
        {"name": "Finnhub", "priority": 95, "is_available": False, "note": "Stock quote - set FINNHUB_API_KEY (free at finnhub.io)"},
        {"name": "FOC (NASDAQ)", "priority": 98, "is_available": False, "note": "Options from NASDAQ, no key - pip install freeoptionschain"},
        {"name": "MarketData.app", "priority": 90, "is_available": False, "note": "Not loaded - set MARKET_DATA_API_KEY"},
        {"name": "Alpha Vantage", "priority": 80, "is_available": False, "note": "Not loaded - set ALPHA_VANTAGE_API_KEY"},
        {"name": "AKShare", "priority": 50, "is_available": False, "note": "China ETF options (510050, 510300, etc.)"},
    ]
    try:
        manager = _get_data_manager()
        if not manager:
            return {
                "multi_source_enabled": False,
                "message": "Data providers not loaded (check project path)",
                "total_providers": 3,
                "available_providers": 1,
                "providers": fallback_providers,
            }
        status = manager.get_status()
        status["multi_source_enabled"] = True
        # Add human-readable note for each provider
        for p in status.get("providers", []):
            if "note" not in p:
                p["note"] = "Rate limited" if not p.get("is_available") else "Ready"
        return status
    except Exception as e:
        return {
            "multi_source_enabled": False,
            "message": str(e),
            "total_providers": 3,
            "available_providers": 1,
            "providers": fallback_providers,
        }
