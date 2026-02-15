"""
Strategy analysis service - Integrates with existing optionsflow.py
"""
import sys
import os
import pandas as pd
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)

# Import existing optionsflow modules
from optionsflow import GreeksCalculator, OptionsStrategyAnalyzer
from backend.services.options_service import OptionsService
from backend.database import SessionLocal, Analysis


class StrategyService:
    """Service for analyzing options strategies"""
    
    def __init__(self):
        self.greeks_calculator = GreeksCalculator()
        self.strategy_analyzer = OptionsStrategyAnalyzer()
    
    def analyze_strategy(
        self,
        symbol: str,
        strategy_type: str,
        expiration_date: Optional[str] = None,
        delta_target: Optional[float] = None,
        width_pct: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a single options strategy
        
        Args:
            symbol: Stock symbol
            strategy_type: Strategy type (ccs, pcs, csp, cc)
            expiration_date: Expiration date (YYYY-MM-DD)
            delta_target: Target delta for option selection
            width_pct: Width percentage for spreads
        
        Returns:
            Analysis result dict
        """
        try:
            exp_dates = OptionsService.get_expiration_dates(symbol)
            if not exp_dates:
                raise ValueError("No expiration dates available for this symbol")
            to_try = [expiration_date] if (expiration_date and expiration_date in exp_dates) else []
            to_try += [d for d in exp_dates if d not in to_try]
            chain_data = None
            for exp in to_try:
                chain_data = OptionsService.get_option_chain(symbol, exp)
                if not chain_data:
                    continue
                exp_dt = pd.to_datetime(exp)
                dte = (exp_dt - pd.Timestamp.now()).total_seconds() / (24 * 60 * 60)
                if dte >= 1:
                    expiration_date = exp
                    break
            if not chain_data:
                raise ValueError("Could not fetch option chain for this symbol")
            
            # Get current price and risk-free rate
            current_price = chain_data.get('underlying_price')
            risk_free_rate = OptionsService.get_risk_free_rate()
            
            # Get dividend yield
            stock_info = OptionsService.get_stock_info(symbol)
            div_yield = stock_info.get('dividendYield', 0) if stock_info else 0
            
            # Prepare option chain DataFrame
            chain_list = chain_data.get('calls', []) + chain_data.get('puts', [])
            
            if not chain_list:
                raise ValueError(
                    f"No option chain data for expiration {expiration_date}. "
                    "This date may have no listed options or the data source returned empty."
                )
            
            # Convert to DataFrame
            chain_df = pd.DataFrame(chain_list)
            
            # Add expiration date column
            chain_df['expiry'] = expiration_date or chain_data.get('expiration_date')
            
            # Calculate DTE
            chain_df['expiry'] = pd.to_datetime(chain_df['expiry'])
            now = datetime.now()
            chain_df['dte'] = (chain_df['expiry'] - now).dt.total_seconds() / (24 * 60 * 60)
            
            # Normalize column names for yfinance compatibility (impliedVolatility, openInterest)
            if 'impliedVolatility' not in chain_df.columns and 'implied_volatility' in chain_df.columns:
                chain_df['impliedVolatility'] = chain_df['implied_volatility']
            if 'openInterest' not in chain_df.columns:
                chain_df['openInterest'] = chain_df['open_interest'] if 'open_interest' in chain_df.columns else 0
            if 'volume' not in chain_df.columns:
                chain_df['volume'] = 0
            
            # Calculate Greeks for each option
            for idx, row in chain_df.iterrows():
                try:
                    iv = row.get('impliedVolatility') or row.get('implied_volatility')
                    if pd.isna(iv) or iv <= 0:
                        continue
                    
                    greeks = self.greeks_calculator.calculate_greeks(
                        float(current_price),
                        float(row['strike']),
                        float(row['dte']) / 365,
                        float(risk_free_rate),
                        float(iv),
                        float(div_yield or 0),
                        'CALL' if row.get('option_type') == 'call' else 'PUT'
                    )
                    
                    # Add Greeks to DataFrame
                    for greek, value in greeks.items():
                        chain_df.loc[idx, greek] = value
                        
                except Exception as e:
                    logger.warning("Error calculating Greeks for row %s: %s", idx, e)
                    continue
            
            # Ensure Greeks columns exist (fill missing with 0 for analyzer)
            for g in ['delta', 'gamma', 'theta']:
                if g not in chain_df.columns:
                    chain_df[g] = 0.0

            # Ensure underlying_price is in chain (required by OptionsStrategyAnalyzer)
            if 'underlying_price' not in chain_df.columns and current_price is not None:
                chain_df['underlying_price'] = float(current_price)

            # Calculate probability ITM (required by OptionsStrategyAnalyzer)
            chain_df['prob_itm'] = chain_df.apply(
                lambda row: abs(row['delta']) if 'delta' in row and not pd.isna(row.get('delta')) else 0,
                axis=1
            )
            
            # Filter chain by option type (CCS/CC need calls, PCS/CSP need puts)
            strategy_type_lower = strategy_type.lower()
            opt_type_name = "call" if strategy_type_lower in ('ccs', 'cc') else "put"
            if strategy_type_lower in ('ccs', 'cc'):
                chain_df = chain_df[chain_df['option_type'] == 'call'].copy()
            elif strategy_type_lower in ('pcs', 'csp'):
                chain_df = chain_df[chain_df['option_type'] == 'put'].copy()
            if chain_df.empty:
                raise ValueError(
                    f"No {opt_type_name} options found for expiration {expiration_date}. "
                    f"Strategy {strategy_type_lower.upper()} requires {opt_type_name}s - this expiration may have insufficient data or no listed {opt_type_name}s."
                )

            if strategy_type_lower == 'ccs':
                result = self.strategy_analyzer.analyze_credit_call_spread(chain_df, width_pct or 0.05)
            elif strategy_type_lower == 'pcs':
                result = self.strategy_analyzer.analyze_put_credit_spread(chain_df, width_pct or 0.05)
            elif strategy_type_lower == 'csp':
                result = self.strategy_analyzer.analyze_cash_secured_put(chain_df)
            elif strategy_type_lower == 'cc':
                result = self.strategy_analyzer.analyze_covered_call(chain_df)
            else:
                raise ValueError(f"Unknown strategy type: {strategy_type}")

            analysis_result, error_msg = result
            if analysis_result is None:
                raise ValueError(error_msg or "Strategy analysis returned no result")
            
            analysis_result = result[0]
            
            # Add metadata
            analysis_result['symbol'] = symbol.upper()
            analysis_result['strategy_type'] = strategy_type_lower
            analysis_result['expiration_date'] = expiration_date or chain_data.get('expiration_date')
            analysis_result['current_price'] = current_price
            analysis_result['timestamp'] = datetime.utcnow().isoformat()
            
            return analysis_result
            
        except ValueError:
            raise
        except Exception as e:
            logger.exception("Error analyzing strategy: %s", e)
            raise ValueError(str(e)) from e
    
    def analyze_multiple_strategies(
        self,
        symbol: str,
        strategies: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple strategies in parallel
        
        Args:
            symbol: Stock symbol
            strategies: List of strategy configs
        
        Returns:
            List of analysis results
        """
        results = []
        
        for strategy_config in strategies:
            strategy_type = strategy_config.get('strategy_type')
            expiration_date = strategy_config.get('expiration_date')
            delta_target = strategy_config.get('delta_target')
            width_pct = strategy_config.get('width_pct')
            
            result = self.analyze_strategy(
                symbol=symbol,
                strategy_type=strategy_type,
                expiration_date=expiration_date,
                delta_target=delta_target,
                width_pct=width_pct
            )
            
            if result:
                results.append(result)
        
        return results

    def analyze_pnl_scenarios(
        self,
        symbol: str,
        strategy_type: str,
        expiration_date: str,
        price_range_pct: float = 0.20,
        steps: int = 20
    ) -> Optional[Dict[str, Any]]:
        """Analyze P&L at different stock prices at expiration."""
        import numpy as np

        analysis = self.analyze_strategy(symbol, strategy_type, expiration_date)
        if not analysis:
            raise ValueError("Strategy analysis failed for P&L calculation")

        current_price = analysis.get('current_price')
        if not current_price:
            raise ValueError("Strategy analysis missing current price - cannot compute P&L scenarios")

        strategy_type_lower = strategy_type.lower()
        price_low = float(current_price) * (1 - price_range_pct)
        price_high = float(current_price) * (1 + price_range_pct)
        price_points = np.linspace(price_low, price_high, steps)

        pnl_scenarios = []
        for price in price_points:
            pnl = 0.0
            if strategy_type_lower == 'ccs':
                strikes = analysis.get('strikes', {})
                short_s = strikes.get('short_strike')
                long_s = strikes.get('long_strike')
                credit = analysis.get('metrics', {}).get('credit', 0)
                if short_s is None or long_s is None:
                    continue
                if price <= short_s:
                    pnl = credit
                elif price >= long_s:
                    pnl = credit - (long_s - short_s)
                else:
                    pnl = credit - (price - short_s)
            elif strategy_type_lower == 'pcs':
                strikes = analysis.get('strikes', {})
                short_s = strikes.get('short_strike')
                long_s = strikes.get('long_strike')
                credit = analysis.get('metrics', {}).get('credit', 0)
                if short_s is None or long_s is None:
                    continue
                if price >= short_s:
                    pnl = credit
                elif price <= long_s:
                    pnl = credit - (short_s - long_s)
                else:
                    pnl = credit - (short_s - price)
            elif strategy_type_lower == 'csp':
                strike = analysis.get('strike')
                premium = analysis.get('metrics', {}).get('premium', 0)
                if strike is None:
                    continue
                if price >= strike:
                    pnl = premium
                else:
                    pnl = premium - (strike - price)
            elif strategy_type_lower == 'cc':
                strike = analysis.get('strike')
                premium = analysis.get('metrics', {}).get('premium', 0)
                if strike is None:
                    continue
                if price <= strike:
                    pnl = premium + (price - current_price)
                else:
                    pnl = premium + (strike - current_price)
            else:
                continue

            pnl_scenarios.append({
                "stock_price": round(float(price), 2),
                "pnl": round(float(pnl), 2),
                "pnl_percent": round(float(pnl / current_price * 100), 2),
                "status": "profit" if pnl > 0 else ("breakeven" if pnl == 0 else "loss")
            })

        breakeven_points = [s for s in pnl_scenarios if s['pnl'] == 0]
        max_profit_scenario = max(pnl_scenarios, key=lambda x: x['pnl'])
        max_loss_scenario = min(pnl_scenarios, key=lambda x: x['pnl'])

        exp_dt = pd.to_datetime(expiration_date)
        dte = int((exp_dt - datetime.now()).total_seconds() / (24 * 60 * 60))

        return {
            "symbol": symbol.upper(),
            "current_price": float(current_price),
            "strategy": strategy_type_lower.upper(),
            "expiration_date": expiration_date,
            "days_to_expiration": dte,
            "strategy_details": analysis,
            "price_range": {
                "low": round(float(price_low), 2),
                "high": round(float(price_high), 2),
                "range_percent": f"{price_range_pct * 100:.0f}%"
            },
            "scenarios": pnl_scenarios,
            "key_levels": {
                "breakeven": breakeven_points[0] if breakeven_points else None,
                "max_profit": max_profit_scenario,
                "max_loss": max_loss_scenario
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    def find_best_strategies(
        self,
        symbol: str,
        expiration_date: Optional[str] = None,
        min_probability_profit: float = 0.60,
        max_risk_reward_ratio: float = 3.0,
        strategy_preference: str = "any"
    ) -> Optional[Dict[str, Any]]:
        """Find best strategies by risk/reward criteria."""
        exp_dates = OptionsService.get_expiration_dates(symbol)
        if not exp_dates:
            return None

        if expiration_date:
            if expiration_date not in exp_dates:
                expiration_date = exp_dates[0]
        else:
            now = datetime.now()
            target_dte_range = range(30, 46)
            for d_str in exp_dates:
                exp_dt = pd.to_datetime(d_str).replace(tzinfo=None)
                dte = (exp_dt - now).days
                if dte in target_dte_range:
                    expiration_date = d_str
                    break
            if not expiration_date:
                for d_str in exp_dates:
                    exp_dt = pd.to_datetime(d_str).replace(tzinfo=None)
                    dte = (exp_dt - now).days
                    if dte >= 30:
                        expiration_date = d_str
                        break
            if not expiration_date:
                expiration_date = exp_dates[0]

        pref = strategy_preference.lower()
        if pref == 'bullish':
            strategies_to_check = [('pcs', 'pcs'), ('cc', 'cc'), ('csp', 'csp')]
        elif pref == 'bearish':
            strategies_to_check = [('ccs', 'ccs')]
        elif pref == 'neutral':
            strategies_to_check = [('pcs', 'pcs'), ('ccs', 'ccs')]
        else:
            strategies_to_check = [('ccs', 'ccs'), ('pcs', 'pcs'), ('csp', 'csp'), ('cc', 'cc')]

        valid_strategies = []
        for name, stype in strategies_to_check:
            analysis = self.analyze_strategy(symbol, stype, expiration_date)
            if not analysis:
                continue
            metrics = analysis.get('metrics', {})
            pop = metrics.get('probability_of_profit', 0)
            rr = metrics.get('risk_reward_ratio', float('inf'))
            if rr == 0:
                rr = float('inf')
            if pop >= min_probability_profit and rr <= max_risk_reward_ratio:
                score = pop / rr if rr > 0 and rr != float('inf') else 0
                valid_strategies.append({
                    "strategy": name.upper(),
                    "analysis": analysis,
                    "score": score,
                    "probability_of_profit": pop,
                    "risk_reward_ratio": rr
                })

        valid_strategies.sort(key=lambda x: x['score'], reverse=True)
        chain_data = OptionsService.get_option_chain(symbol, expiration_date)
        current_price = chain_data.get('underlying_price') if chain_data else 0
        exp_dt = pd.to_datetime(expiration_date)
        dte = int((exp_dt - datetime.now()).total_seconds() / (24 * 60 * 60))

        return {
            "symbol": symbol.upper(),
            "current_price": float(current_price),
            "expiration_date": expiration_date,
            "days_to_expiration": dte,
            "search_criteria": {
                "min_probability_profit": min_probability_profit,
                "max_risk_reward_ratio": max_risk_reward_ratio,
                "preference": strategy_preference
            },
            "strategies_found": len(valid_strategies),
            "best_strategies": valid_strategies[:3],
            "recommendation": valid_strategies[0] if valid_strategies else None,
            "timestamp": datetime.utcnow().isoformat()
        }

    @staticmethod
    def save_analysis(user_id: int, analysis_data: Dict[str, Any]) -> Optional[int]:
        """Save analysis to database. Skips save when user_id is 0 (anonymous)."""
        if user_id <= 0:
            return None
        db = SessionLocal()
        try:
            analysis = Analysis(
                user_id=user_id,
                symbol=analysis_data['symbol'],
                strategy_type=analysis_data['strategy_type'],
                expiration_date=analysis_data['expiration_date'],
                current_price=analysis_data['current_price'],
                analysis_result=json.dumps(analysis_data)
            )
            
            db.add(analysis)
            db.commit()
            db.refresh(analysis)
            
            return analysis.id
        except Exception as e:
            logger.error("Error saving analysis: %s", e)
            db.rollback()
            return None
        finally:
            db.close()
    
    @staticmethod
    def get_user_analyses(
        user_id: int,
        limit: int = 50,
        symbol: Optional[str] = None,
        strategy_type: Optional[str] = None,
        expiration_date: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get user's analysis history with optional filters"""
        from datetime import datetime
        db = SessionLocal()
        try:
            q = db.query(Analysis).filter(Analysis.user_id == user_id)
            if symbol:
                q = q.filter(Analysis.symbol == symbol.upper())
            if strategy_type:
                q = q.filter(Analysis.strategy_type == strategy_type.lower())
            if expiration_date:
                q = q.filter(Analysis.expiration_date == expiration_date)
            if date_from:
                try:
                    dt_from = datetime.fromisoformat(date_from[:10])
                    q = q.filter(Analysis.created_at >= dt_from)
                except (ValueError, IndexError):
                    pass
            if date_to:
                try:
                    dt_to = datetime.fromisoformat(date_to[:10])
                    dt_to = dt_to.replace(hour=23, minute=59, second=59, microsecond=999999)
                    q = q.filter(Analysis.created_at <= dt_to)
                except (ValueError, IndexError):
                    pass
            analyses = q.order_by(Analysis.created_at.desc()).limit(limit).all()
            
            results = []
            for analysis in analyses:
                result = {
                    "id": analysis.id,
                    "symbol": analysis.symbol,
                    "strategy_type": analysis.strategy_type,
                    "expiration_date": analysis.expiration_date,
                    "current_price": analysis.current_price,
                    "created_at": analysis.created_at.isoformat(),
                    "analysis_result": json.loads(analysis.analysis_result)
                }
                results.append(result)
            
            return results
        except Exception as e:
            logger.error("Error getting user analyses: %s", e)
            return []
        finally:
            db.close()

    @staticmethod
    def get_history_filter_options(user_id: int) -> Dict[str, List[str]]:
        """Get distinct symbol, strategy_type, expiration_date for filter dropdowns"""
        db = SessionLocal()
        try:
            symbols = [r[0] for r in db.query(Analysis.symbol).filter(Analysis.user_id == user_id).distinct().all()]
            strategies = [r[0] for r in db.query(Analysis.strategy_type).filter(Analysis.user_id == user_id).distinct().all()]
            expirations = [r[0] for r in db.query(Analysis.expiration_date).filter(Analysis.user_id == user_id).distinct().all()]
            return {
                "symbols": sorted(symbols or []),
                "strategy_types": sorted(strategies or []),
                "expiration_dates": sorted(expirations or []),
            }
        except Exception as e:
            logger.error("Error getting filter options: %s", e)
            return {"symbols": [], "strategy_types": [], "expiration_dates": []}
        finally:
            db.close()
