"""
Options data routes
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Annotated, Optional, List
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.services.options_service import OptionsService
from backend.models.option import (
    StockInfoResponse,
    OptionChainResponse,
    ExpirationDatesResponse,
    FilteredOptionsRequest
)
from backend.routers.auth import get_current_user_id

router = APIRouter(prefix="/options", tags=["options"])
security = HTTPBearer(auto_error=False)


@router.get("/stock/{symbol}", response_model=StockInfoResponse)
async def get_stock_info(
    symbol: str,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)] = None
):
    """Get stock information"""
    # Optional: Add authentication
    # user_id = await get_current_user_id(credentials)
    
    stock_info = OptionsService.get_stock_info(symbol)
    
    if not stock_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock information not found for symbol: {symbol}"
        )
    
    return stock_info


@router.get("/expirations/{symbol}", response_model=ExpirationDatesResponse)
async def get_expiration_dates(
    symbol: str,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)] = None
):
    """Get available expiration dates for options"""
    exp_dates = OptionsService.get_expiration_dates(symbol)
    
    if not exp_dates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No expiration dates found for symbol: {symbol}"
        )
    
    return {
        "symbol": symbol.upper(),
        "expiration_dates": exp_dates
    }


@router.get("/chain/{symbol}", response_model=OptionChainResponse)
async def get_option_chain(
    symbol: str,
    expiration_date: Optional[str] = Query(None, description="Expiration date (YYYY-MM-DD)"),
    option_type: Optional[str] = Query(None, description="Option type: 'call' or 'put'"),
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)] = None
):
    """Get option chain data"""
    chain_data = OptionsService.get_option_chain(symbol, expiration_date, option_type)
    
    if not chain_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Option chain not found for symbol: {symbol}"
        )
    
    return chain_data


@router.post("/filtered", response_model=List[dict])
async def get_filtered_options(
    request: FilteredOptionsRequest,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)] = None
):
    """Get filtered option chain data"""
    
    # Get expiration date if not provided
    exp_date = request.expiration_date
    if not exp_date:
        exp_dates = OptionsService.get_expiration_dates(request.symbol)
        if not exp_dates:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No expiration dates found for symbol: {request.symbol}"
            )
        exp_date = exp_dates[0]
    
    filtered_options = OptionsService.get_filtered_options(
        symbol=request.symbol,
        expiration_date=exp_date,
        option_type=request.option_type,
        min_volume=request.min_volume,
        min_open_interest=request.min_open_interest,
        min_delta=request.min_delta,
        max_delta=request.max_delta,
        strike_range=request.get_strike_range()
    )
    
    if not filtered_options:
        return []
    
    return filtered_options


@router.get("/chain/{symbol}/greeks")
async def get_option_chain_with_greeks(
    symbol: str,
    expiration_date: Optional[str] = Query(None, description="Expiration date (YYYY-MM-DD)"),
    option_type: Optional[str] = Query(None, description="Option type: 'call' or 'put'"),
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)] = None
):
    """Get option chain with calculated Greeks for visualization"""
    chain_data = OptionsService.get_option_chain_with_greeks(symbol, expiration_date, option_type)
    if not chain_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Option chain not found for symbol: {symbol}"
        )
    return chain_data


@router.get("/sources-status")
async def get_sources_status(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)] = None
):
    """Get status of all data sources and which are available"""
    try:
        from backend.utils.data_source import get_sources_status as _get_status
        return _get_status()
    except ImportError as e:
        return {
            "multi_source_enabled": False,
            "message": f"Data providers not loaded: {e}",
            "total_providers": 3,
            "available_providers": 1,
            "providers": [
                {"name": "Yahoo Finance", "priority": 100, "is_available": True, "note": "Direct"},
                {"name": "MarketData.app", "priority": 90, "is_available": False, "note": "Import failed"},
                {"name": "Alpha Vantage", "priority": 80, "is_available": False, "note": "Import failed"},
            ],
        }


@router.get("/cache-status")
async def get_cache_status(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)] = None
):
    """Get cache TTL settings and stats (for debugging)"""
    from backend.services import options_service as svc
    s, o, e, r = svc._stock_cache, svc._option_chain_cache, svc._exp_cache, svc._rate_cache
    return {
        "cache_ttl_seconds": {
            "stock": s.ttl_seconds,
            "option_chain": o.ttl_seconds,
            "expirations": e.ttl_seconds,
            "rate": r.ttl_seconds,
        },
        "stats": {
            "stock": s.get_stats(),
            "option_chain": o.get_stats(),
            "expirations": e.get_stats(),
            "rate": r.get_stats(),
        },
    }


@router.get("/rate")
async def get_risk_free_rate(
    market: Optional[str] = Query(None, description="Market: 'us' or 'cn'"),
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)] = None
):
    """Get current risk-free rate. market=cn for China (~2.5%), else US (13-Week T-Bill)."""
    is_china = (market or "").lower() == "cn"
    rate = OptionsService.get_risk_free_rate("cn" if is_china else None)
    return {
        "risk_free_rate": rate,
        "percentage": f"{rate * 100:.2f}%",
        "source": "AKShare / 参考利率" if is_china else "13-Week T-Bill (Yahoo Finance)",
    }
