"""
Strategy analysis routes
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Annotated, List, Optional
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.services.strategy_service import StrategyService
from backend.models.strategy import (
    StrategyAnalysisRequest,
    StrategyAnalysisResponse,
    MultiStrategyRequest,
    StrategyComparisonResponse,
    PnlScenariosRequest,
    FindBestStrategiesRequest
)
from backend.routers.auth import get_current_user_id

router = APIRouter(prefix="/strategies", tags=["strategies"])
security = HTTPBearer(auto_error=False)

# Initialize strategy service
strategy_service = StrategyService()


async def _get_optional_user_id(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> int:
    """Get user ID if authenticated, else 0 for anonymous"""
    if not credentials:
        return 0
    try:
        return await get_current_user_id(credentials)
    except HTTPException:
        return 0


@router.post("/analyze", response_model=StrategyAnalysisResponse)
async def analyze_strategy(
    request: StrategyAnalysisRequest,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)]
):
    """Analyze a single options strategy"""
    user_id = await _get_optional_user_id(credentials)
    
    # Analyze strategy
    try:
        result = strategy_service.analyze_strategy(
            symbol=request.symbol,
            strategy_type=request.strategy_type,
            expiration_date=request.expiration_date,
            delta_target=request.delta_target,
            width_pct=request.width_pct
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Analysis returned no result. Try a different expiration date or symbol."
        )
    
    # Save to history if requested
    if request.save_result:
        analysis_id = StrategyService.save_analysis(user_id, result)
        result['analysis_id'] = analysis_id
    
    return result


@router.post("/compare", response_model=StrategyComparisonResponse)
async def compare_strategies(
    request: MultiStrategyRequest,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)]
):
    """Analyze and compare multiple strategies"""
    user_id = await _get_optional_user_id(credentials)
    
    try:
        results = strategy_service.analyze_multiple_strategies(
            symbol=request.symbol,
            strategies=request.strategies
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    if not results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not analyze any strategies. Try a different expiration date or symbol."
        )
    
    # Save results if requested
    if request.save_results:
        for result in results:
            StrategyService.save_analysis(user_id, result)
    
    from datetime import datetime
    return {
        "symbol": request.symbol,
        "strategies": results,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/pnl-scenarios")
async def analyze_pnl_scenarios(
    request: PnlScenariosRequest,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)]
):
    """Analyze P&L scenarios at different stock prices at expiration"""
    await _get_optional_user_id(credentials)

    try:
        result = strategy_service.analyze_pnl_scenarios(
            symbol=request.symbol,
            strategy_type=request.strategy,
            expiration_date=request.expiration_date,
            price_range_pct=request.price_range_pct or 0.20,
            steps=request.steps or 20
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="P&L analysis returned no result. Try a different expiration date or strategy."
        )
    return result


@router.post("/find-best")
async def find_best_strategies(
    request: FindBestStrategiesRequest,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)]
):
    """Find best strategies by risk/reward criteria"""
    await _get_optional_user_id(credentials)

    try:
        result = strategy_service.find_best_strategies(
            symbol=request.symbol,
            expiration_date=request.expiration_date,
            min_probability_profit=request.min_probability_profit or 0.60,
            max_risk_reward_ratio=request.max_risk_reward_ratio or 3.0,
            strategy_preference=request.strategy_preference or "any"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not find strategies. Try a different expiration date or symbol."
        )
    return result


@router.get("/history/filter-options")
async def get_history_filter_options(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
):
    """Get distinct values for history filter dropdowns"""
    user_id = await _get_optional_user_id(credentials)
    if user_id <= 0:
        return {"symbols": [], "strategy_types": [], "expiration_dates": []}
    return StrategyService.get_history_filter_options(user_id)


@router.get("/history", response_model=List[dict])
async def get_analysis_history(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
    limit: int = 50,
    symbol: Optional[str] = None,
    strategy_type: Optional[str] = None,
    expiration_date: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Get user's analysis history with optional filters"""
    user_id = await _get_optional_user_id(credentials)
    
    if user_id <= 0:
        return []
    analyses = StrategyService.get_user_analyses(
        user_id, limit,
        symbol=symbol,
        strategy_type=strategy_type,
        expiration_date=expiration_date,
        date_from=date_from,
        date_to=date_to,
    )
    return analyses


@router.get("/history/{analysis_id}", response_model=dict)
async def get_analysis_detail(
    analysis_id: int,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)]
):
    """Get specific analysis details"""
    user_id = await _get_optional_user_id(credentials)
    
    if user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    from backend.database import SessionLocal, Analysis
    db = SessionLocal()
    
    try:
        analysis = db.query(Analysis).filter(
            Analysis.id == analysis_id,
            Analysis.user_id == user_id
        ).first()
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found"
            )
        
        import json
        result = {
            "id": analysis.id,
            "symbol": analysis.symbol,
            "strategy_type": analysis.strategy_type,
            "expiration_date": analysis.expiration_date,
            "current_price": analysis.current_price,
            "created_at": analysis.created_at.isoformat(),
            "analysis_result": json.loads(analysis.analysis_result)
        }
        
        return result
    finally:
        db.close()


@router.delete("/history/{analysis_id}")
async def delete_analysis(
    analysis_id: int,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)]
):
    """Delete an analysis record"""
    user_id = await _get_optional_user_id(credentials)
    
    if user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    from backend.database import SessionLocal, Analysis
    db = SessionLocal()
    
    try:
        analysis = db.query(Analysis).filter(
            Analysis.id == analysis_id,
            Analysis.user_id == user_id
        ).first()
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found"
            )
        
        db.delete(analysis)
        db.commit()
        
        return {"message": "Analysis deleted successfully"}
    finally:
        db.close()
