#!/usr/bin/env python3

import logging
import asyncio
import yfinance as yf
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server
import json
import traceback
import re
import pandas as pd
import numpy as np
from scipy.stats import norm
from scipy.interpolate import griddata
from scipy.optimize import brentq
import datetime
from functools import wraps
import time
import os
from typing import List, Dict, Optional, Any, Tuple

# Import multi-source data manager
try:
    from providers import DataSourceManager
    MULTI_SOURCE_ENABLED = True
except ImportError:
    MULTI_SOURCE_ENABLED = False

def retry_on_error(max_retries: int = 3, delay: float = 1.0):
    """Decorator to retry failing functions with exponential backoff"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)
                        logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {str(e)}")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"All {max_retries} attempts failed: {str(e)}\n{traceback.format_exc()}")
            raise last_error
        return wrapper
    return decorator


def get_risk_free_rate() -> float:
    """Simple way to get a recent risk-free rate (using 1-year treasury yield).
       Consider more robust methods for production."""
    try:
        tbill = yf.Ticker("^IRX")  # Ticker for 13-week T-Bill
        hist = tbill.history(period="5d")
        if not hist.empty:
            return hist['Close'].iloc[-1] / 100.0  # Convert percentage to decimal
        logger.warning("Could not fetch T-Bill rate, using default")
        return 0.04  # Default if data fetch fails
    except Exception as e:
        logger.warning(f"Error fetching risk-free rate: {e}")
        return 0.04  # Default rate if there's an error

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("options_analytics.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("options-analytics")

class OptionsError(Exception):
    pass

class ValidationError(OptionsError):
    pass

class APIError(OptionsError):
    pass

class GreeksCalculator:
    def __init__(self):
        self.MIN_SIGMA = 0.0001  # Minimum volatility to prevent division by zero
        self.MIN_TIME = 1/365    # Minimum time (1 day) to prevent time issues
        
    @staticmethod
    def calculate_d1(S: float, K: float, T: float, r: float, sigma: float, q: float) -> float:
        """Calculate d1 component of Black-Scholes with dividend yield"""
        try:
            if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
                return float('nan')
            return (np.log(S/K) + (r - q + (sigma**2)/2)*T) / (sigma*np.sqrt(T))
        except Exception as e:
            logger.error(f"Error in d1 calculation: {e}")
            return float('nan')

    @staticmethod
    def calculate_d2(S: float, K: float, T: float, r: float, sigma: float, q: float) -> float:
        """Calculate d2 component of Black-Scholes"""
        try:
            if T <= 0 or sigma <= 0:
                return float('nan')
            d1 = GreeksCalculator.calculate_d1(S, K, T, r, sigma, q)
            return d1 - sigma*np.sqrt(T)
        except Exception as e:
            logger.error(f"Error in d2 calculation: {e}")
            return float('nan')

    def calculate_greeks(self, S: float, K: float, T: float, r: float,
                        sigma: float, q: float, option_type: str) -> Dict[str, float]:
        """
        Calculate option Greeks using Black-Scholes model
        
        Parameters:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free rate (as decimal)
        sigma: Implied volatility (as decimal)
        q: Dividend yield (as decimal)
        option_type: 'CALL' or 'PUT'
        """
        try:
            # Input validation with detailed logging
            logger.debug(f"Inputs: S={S}, K={K}, T={T}, r={r}, sigma={sigma}, q={q}, type={option_type}")
            
            if pd.isna(sigma) or sigma <= 0:
                logger.warning(f"Invalid volatility: {sigma}")
                return {greek: float('nan') for greek in 
                    ['delta', 'gamma', 'theta', 'vega', 'rho']}

            # Ensure minimum values to prevent numerical issues
            T = max(T, self.MIN_TIME)
            sigma = max(sigma, self.MIN_SIGMA)

            if S <= 0 or K <= 0:
                logger.warning(f"Invalid price or strike: S={S}, K={K}")
                return {greek: float('nan') for greek in 
                    ['delta', 'gamma', 'theta', 'vega', 'rho']}

            # Base calculations with logging
            d1 = self.calculate_d1(S, K, T, r, sigma, q)
            d2 = self.calculate_d2(S, K, T, r, sigma, q)
            
            logger.debug(f"d1={d1}, d2={d2}")

            if np.isnan(d1) or np.isnan(d2):
                logger.warning("d1 or d2 calculation failed")
                return {greek: float('nan') for greek in 
                    ['delta', 'gamma', 'theta', 'vega', 'rho']}

            is_call = option_type.upper() == 'CALL'

            # Standard normal calculations
            N_d1 = norm.cdf(d1)
            N_d2 = norm.cdf(d2)
            n_d1 = norm.pdf(d1)
            
            logger.debug(f"N_d1={N_d1}, N_d2={N_d2}, n_d1={n_d1}")

            # Delta calculation
            if is_call:
                delta = np.exp(-q*T) * N_d1
            else:
                delta = np.exp(-q*T) * (N_d1 - 1)  # Simplified put delta formula

            # Gamma calculation (same for calls and puts)
            gamma = np.exp(-q*T) * n_d1 / (S * sigma * np.sqrt(T))

            # Theta calculation
            theta_term1 = -(S * sigma * np.exp(-q*T) * n_d1) / (2 * np.sqrt(T))
            if is_call:
                theta = theta_term1 - r*K*np.exp(-r*T)*N_d2 + q*S*np.exp(-q*T)*N_d1
            else:
                theta = theta_term1 + r*K*np.exp(-r*T)*norm.cdf(-d2) - q*S*np.exp(-q*T)*norm.cdf(-d1)

            # Vega calculation (same for calls and puts)
            vega = S * np.exp(-q*T) * np.sqrt(T) * n_d1

            # Rho calculation
            if is_call:
                rho = K * T * np.exp(-r*T) * N_d2
            else:
                rho = -K * T * np.exp(-r*T) * norm.cdf(-d2)

            # Log calculated values before adjustments
            logger.debug(f"Raw values: delta={delta}, gamma={gamma}, theta={theta}, vega={vega}, rho={rho}")

            # Return adjusted values
            return {
                'delta': float(delta),
                'gamma': float(gamma),
                'theta': float(theta/365),  # Convert to daily theta
                'vega': float(vega/100),    # Per 1% change in vol
                'rho': float(rho/100)       # Per 1% change in rates
            }

        except Exception as e:
            logger.error(f"Error calculating Greeks: {str(e)}")
            return {greek: float('nan') for greek in 
                ['delta', 'gamma', 'theta', 'vega', 'rho']}

    @staticmethod
    def implied_volatility_from_price(
        S: float, K: float, T: float, r: float, q: float,
        option_price: float, option_type: str
    ) -> Optional[float]:
        """
        Compute implied volatility from option price (inverse Black-Scholes).
        Returns sigma (as decimal, e.g. 0.25 for 25%) or None if cannot solve.
        """
        if option_price <= 0 or S <= 0 or K <= 0 or T <= 0:
            return None
        is_call = option_type.upper() in ('CALL', 'C')

        def bs_price(sigma: float) -> float:
            if sigma <= 0:
                return float('nan')
            d1 = GreeksCalculator.calculate_d1(S, K, T, r, sigma, q)
            d2 = GreeksCalculator.calculate_d2(S, K, T, r, sigma, q)
            if np.isnan(d1) or np.isnan(d2):
                return float('nan')
            if is_call:
                return S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
            return K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)

        def objective(sigma: float) -> float:
            return bs_price(sigma) - option_price

        try:
            # IV typically 0.01% to 300%; use wider bracket for edge cases
            sigma_lo, sigma_hi = 1e-6, 5.0
            f_lo, f_hi = objective(sigma_lo), objective(sigma_hi)
            if np.isnan(f_lo) or np.isnan(f_hi):
                return None
            if f_lo * f_hi <= 0:
                sigma = brentq(objective, sigma_lo, sigma_hi, maxiter=100)
                return float(sigma)
            # No root in bracket: market price outside BS range (e.g. below intrinsic)
            # Use heuristic fallback so Greeks can still be calculated
            if f_lo > 0 and f_hi > 0:
                return 0.20  # price below min, use 20% as fallback
            if f_lo < 0 and f_hi < 0:
                return 0.50  # price above max, use 50% as fallback
            return None
        except (ValueError, RuntimeError, ZeroDivisionError):
            return None

class OptionsStrategyAnalyzer:
    """Analyzes basic options strategies"""
    
    def __init__(self):
        self.greeks_calculator = GreeksCalculator()
        self.MIN_DTE = 1  # Move to class initialization
        self.last_error = None
        self.MIN_VOLUME = 5
        self.MIN_OPEN_INTEREST = 5
        self.MAX_SPREAD_PCT = 0.20

    def _validate_option_liquidity(self, option: pd.Series) -> Tuple[bool, Optional[str]]:
        if option['bid'] <= 0 or option['ask'] <= 0:
            return False, "Invalid bid/ask prices"
        if option['ask'] < option['bid']:
            return False, "Ask price lower than bid price"
            
        spread_pct = (option['ask'] - option['bid']) / option['ask']
        min_price = min(option['bid'], option['ask'])
        
        # First check overall maximum spread threshold
        if spread_pct > self.MAX_SPREAD_PCT:
            return False, f"Spread ({spread_pct:.1%}) exceeds maximum threshold ({self.MAX_SPREAD_PCT:.1%})"
        
        # Additional tiered checks for different price ranges
        if min_price < 1.0 and spread_pct > 0.25:
            return False, f"Spread ({spread_pct:.1%}) too wide for sub-$1 option"
        elif min_price < 5.0 and spread_pct > 0.15:
            return False, f"Spread ({spread_pct:.1%}) too wide for $1-$5 option"
        elif min_price > 10.0 and spread_pct > 0.10:
            return False, f"Spread ({spread_pct:.1%}) too wide for $10+ option"
            
        return True, None

    def _validate_option_activity(self, option: pd.Series) -> bool:
        """Validate option has sufficient trading activity (volume or open interest)"""
        vol = option.get('volume', 0) or 0
        oi = option.get('openInterest', 0) or 0
        return vol >= self.MIN_VOLUME or oi >= self.MIN_OPEN_INTEREST

    def analyze_credit_call_spread(self, chain: pd.DataFrame, width_pct: float = 0.05) -> Tuple[Optional[Dict], Optional[str]]:
        try:
            if 'underlying_price' not in chain.columns:
                return None, "Missing price data in options chain"
                
            if 'dte' not in chain.columns:
                return None, "Missing DTE calculation in options chain"
                
            dte = chain['dte'].iloc[0]
            if dte < self.MIN_DTE:
                return None, f"Expiration too close. Minimum DTE: {self.MIN_DTE}"

            current_price = chain['underlying_price'].iloc[0]
            # Find closest OTM strikes
            otm_calls = chain[chain['strike'] > current_price].copy()
            if otm_calls.empty:
                return None, "No valid OTM strikes found"
                
            # Target first and second OTM strikes with sufficient volume
            valid_strikes = otm_calls[
                (otm_calls['volume'] >= self.MIN_VOLUME) & 
                (otm_calls['openInterest'] >= self.MIN_OPEN_INTEREST)
            ]['strike'].sort_values()
            
            if len(valid_strikes) < 2:
                return None, "Not enough liquid strikes for spread"
                
            target_short_strike = valid_strikes.iloc[0]
            target_long_strike = valid_strikes.iloc[1]
            
            # Find closest strikes
            short_options = chain[chain['strike'] >= target_short_strike]
            if short_options.empty:
                return None, f"No valid strikes found above {target_short_strike}"
                
            short_strike = short_options['strike'].iloc[0]
            long_options = chain[chain['strike'] >= target_long_strike]
            if long_options.empty:
                return None, f"No valid strikes found above {target_long_strike}"
                
            long_strike = long_options['strike'].iloc[0]
            
            short_option = chain[chain['strike'] == short_strike].iloc[0]
            long_option = chain[chain['strike'] == long_strike].iloc[0]

            # Validate liquidity
            if not self._validate_option_liquidity(short_option):
                return None, f"Short strike {short_strike} has insufficient liquidity (wide bid-ask spread)"
            if not self._validate_option_liquidity(long_option):
                return None, f"Long strike {long_strike} has insufficient liquidity (wide bid-ask spread)"
            
            # Validate activity
            if not self._validate_option_activity(short_option):
                return None, f"Short strike {short_strike} has insufficient volume (min: {self.MIN_VOLUME}) or open interest (min: {self.MIN_OPEN_INTEREST})"
            if not self._validate_option_activity(long_option):
                return None, f"Long strike {long_strike} has insufficient volume (min: {self.MIN_VOLUME}) or open interest (min: {self.MIN_OPEN_INTEREST})"
            
            credit = float(short_option['bid'] - long_option['ask'])
            if credit <= 0:
                return None, f"No valid credit found for strike combination {short_strike}/{long_strike}"
                
            max_loss = float(long_strike - short_strike - credit)
            probability_otm = 1 - float(short_option['prob_itm'])
            
            try:
                net_delta = float(short_option['delta'] - long_option['delta'])
                net_theta = float(short_option['theta'] - long_option['theta'])
                net_gamma = float(short_option['gamma'] - long_option['gamma'])
                
                # Validate Greeks are not zero or NaN
                if all(abs(greek) < 1e-10 for greek in [net_delta, net_theta, net_gamma]):
                    return None, "Invalid Greeks calculation for spread"
                    
            except (ValueError, TypeError) as e:
                return None, f"Error calculating spread Greeks: {str(e)}"

            return {
                'strikes': {
                    'short_strike': float(short_strike),
                    'long_strike': float(long_strike)
                },
                'metrics': {
                    'credit': credit,
                    'max_loss': max_loss,
                    'max_profit': credit,
                    'probability_of_profit': probability_otm,
                    'risk_reward_ratio': abs(max_loss/credit) if credit != 0 else float('inf')
                },
                'greeks': {
                    'net_delta': net_delta,
                    'net_theta': net_theta,
                    'net_gamma': net_gamma
                }
            }, None
            
        except Exception as e:
            error_msg = f"Error analyzing CCS: {str(e)}"
            logger.error(error_msg)
            return None, error_msg

    def analyze_put_credit_spread(self, chain: pd.DataFrame, width_pct: float = 0.05) -> Tuple[Optional[Dict], Optional[str]]:
        try:
            if 'underlying_price' not in chain.columns:
                return None, "Missing price data in options chain"
                
            if 'dte' not in chain.columns:
                return None, "Missing DTE calculation in options chain"
                
            dte = chain['dte'].iloc[0]
            if dte < self.MIN_DTE:
                return None, f"Expiration too close. Minimum DTE: {self.MIN_DTE}"

            current_price = chain['underlying_price'].iloc[0]
            
            below_current = chain[chain['strike'] < current_price]
            if below_current.empty:
                return None, f"No valid strikes found below current price {current_price}"
                
            short_strike = below_current['strike'].iloc[-1]
            below_short = chain[chain['strike'] < short_strike]
            if below_short.empty:
                return None, f"No valid strikes found below {short_strike}"
                
            long_strike = below_short['strike'].iloc[-1]
            
            short_option = chain[chain['strike'] == short_strike].iloc[0]
            long_option = chain[chain['strike'] == long_strike].iloc[0]

            # Validate liquidity
            if not self._validate_option_liquidity(short_option):
                return None, f"Short strike {short_strike} has insufficient liquidity (wide bid-ask spread)"
            if not self._validate_option_liquidity(long_option):
                return None, f"Long strike {long_strike} has insufficient liquidity (wide bid-ask spread)"
            
            # Validate activity
            if not self._validate_option_activity(short_option):
                return None, f"Short strike {short_strike} has insufficient volume (min: {self.MIN_VOLUME}) or open interest (min: {self.MIN_OPEN_INTEREST})"
            if not self._validate_option_activity(long_option):
                return None, f"Long strike {long_strike} has insufficient volume (min: {self.MIN_VOLUME}) or open interest (min: {self.MIN_OPEN_INTEREST})"
            
            credit = float(short_option['bid'] - long_option['ask'])
            if credit <= 0:
                return None, f"No valid credit found for strike combination {short_strike}/{long_strike}"
                
            max_loss = float(short_strike - long_strike - credit)
            probability_otm = 1 - float(short_option['prob_itm'])
            
            return {
                'strikes': {
                    'short_strike': float(short_strike),
                    'long_strike': float(long_strike)
                },
                'metrics': {
                    'credit': credit,
                    'max_loss': max_loss,
                    'max_profit': credit,
                    'probability_of_profit': probability_otm,
                    'risk_reward_ratio': abs(max_loss/credit) if credit != 0 else float('inf')
                },
                'greeks': {
                    'net_delta': float(short_option['delta'] - long_option['delta']),
                    'net_theta': float(short_option['theta'] - long_option['theta']),
                    'net_gamma': float(short_option['gamma'] - long_option['gamma'])
                }
            }, None
            
        except Exception as e:
            error_msg = f"Error analyzing PCS: {str(e)}"
            logger.error(error_msg)
            return None, error_msg

    def analyze_cash_secured_put(self, chain: pd.DataFrame, delta_target: float = 0.3) -> Tuple[Optional[Dict], Optional[str]]:
        try:
            if 'underlying_price' not in chain.columns:
                return None, "Missing price data in options chain"
                
            if 'dte' not in chain.columns:
                return None, "Missing DTE calculation in options chain"
                
            dte = chain['dte'].iloc[0]
            if dte < self.MIN_DTE:
                return None, f"Expiration too close. Minimum DTE: {self.MIN_DTE}"

            current_price = chain['underlying_price'].iloc[0]
            put_options = chain[chain['option_type'] == 'put']
            
            if put_options.empty:
                return None, "No valid put options found for this expiration"
                
            # For puts, find closest to -delta_target since put deltas are negative
            target_put = put_options.iloc[(put_options['delta'] + delta_target).abs().argsort()[:1]].iloc[0]
            
            # Validate liquidity
            if not self._validate_option_liquidity(target_put):
                return None, f"Strike {target_put['strike']} has insufficient liquidity (wide bid-ask spread)"
            
            # Validate activity
            if not self._validate_option_activity(target_put):
                return None, f"Strike {target_put['strike']} has insufficient volume (min: {self.MIN_VOLUME}) or open interest (min: {self.MIN_OPEN_INTEREST})"
            
            premium = float(target_put['bid'])
            max_loss = float(target_put['strike'] - premium)
            assigned_cost_basis = float(target_put['strike'] - premium)
            
            return {
                'strike': float(target_put['strike']),
                'metrics': {
                    'premium': premium,
                    'max_loss': max_loss,
                    'assigned_cost_basis': assigned_cost_basis,
                    'return_if_otm': float(premium / target_put['strike'] * 100),
                    'downside_protection': float((1 - assigned_cost_basis/current_price) * 100)
                },
                'greeks': {
                    'delta': float(target_put['delta']),
                    'theta': float(target_put['theta']),
                    'gamma': float(target_put['gamma'])
                }
            }, None
            
        except Exception as e:
            error_msg = f"Error analyzing CSP: {str(e)}"
            logger.error(error_msg)
            return None, error_msg

    def analyze_covered_call(self, chain: pd.DataFrame, delta_target: float = 0.3) -> Tuple[Optional[Dict], Optional[str]]:
        try:
            if 'underlying_price' not in chain.columns:
                return None, "Missing price data in options chain"
                
            if 'dte' not in chain.columns:
                return None, "Missing DTE calculation in options chain"
                
            dte = chain['dte'].iloc[0]
            if dte < self.MIN_DTE:
                return None, f"Expiration too close. Minimum DTE: {self.MIN_DTE}"

            current_price = chain['underlying_price'].iloc[0]
            call_options = chain[chain['option_type'] == 'call']
            if call_options.empty:
                return None, "No valid call options found for this expiration"

            # Debug info
            logger.info(f"Current price: {current_price}")
            logger.info(f"Available strikes: {call_options['strike'].tolist()}")
            logger.info(f"Deltas: {call_options['delta'].tolist()}")

            otm_calls = call_options[call_options['strike'] >= current_price]
            if otm_calls.empty:
                return None, "No valid OTM strikes found"

            logger.info(f"OTM strikes: {otm_calls['strike'].tolist()}")
            logger.info(f"OTM deltas: {otm_calls['delta'].tolist()}")

            # Find the strike with delta closest to our target
            target_delta = 1 - delta_target  # For 0.3 target, we want 0.7 delta
            target_call = otm_calls.iloc[(otm_calls['delta'] - target_delta).abs().argsort()[:1]].iloc[0]
            
            logger.info(f"Selected strike: {target_call['strike']}")
            logger.info(f"Selected delta: {target_call['delta']}")
            
            # Validate liquidity
            is_liquid, liquidity_error = self._validate_option_liquidity(target_call)
            if not is_liquid:
                return None, f"Strike {target_call['strike']} {liquidity_error}"
            
            # Validate activity
            if not self._validate_option_activity(target_call):
                return None, f"Strike {target_call['strike']} has insufficient volume (min: {self.MIN_VOLUME}) or open interest (min: {self.MIN_OPEN_INTEREST})"
            
            premium = float(target_call['bid'])
            max_profit = float(target_call['strike'] - current_price + premium)
            called_away_return = float((max_profit / current_price) * 100)
            
            return {
                'strike': float(target_call['strike']),
                'metrics': {
                    'premium': premium,
                    'max_profit': max_profit,
                    'max_profit_percent': called_away_return,
                    'upside_cap': float(target_call['strike']),
                    'premium_yield': float(premium / current_price * 100)
                },
                'greeks': {
                    'position_delta': float(target_call['delta']),  # Delta is already correct from BS calc
                    'theta': float(target_call['theta']),
                    'gamma': float(target_call['gamma'])
                }
            }, None
            
        except Exception as e:
            error_msg = f"Error analyzing CC: {str(e)}"
            logger.error(error_msg)
            return None, error_msg

def format_response(data: Any, error: Optional[str] = None) -> List[TextContent]:
    """Format API response"""
    response = {
        "success": error is None,
        "timestamp": time.time(),
        "data": data if error is None else None,
        "error": error
    }
    
    return [TextContent(
        type="text",
        text=json.dumps(response, indent=2)
    )]

# Initialize server and analyzers
app = Server("options-analytics")
greeks_calculator = GreeksCalculator()
strategy_analyzer = OptionsStrategyAnalyzer()

# Initialize data source manager
data_manager = None
if MULTI_SOURCE_ENABLED:
    try:
        data_manager = DataSourceManager(
            alpha_vantage_key=os.getenv("ALPHA_VANTAGE_API_KEY"),
            market_data_key=os.getenv("MARKET_DATA_API_KEY")
        )
        logger.info("Multi-source data manager initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize data manager: {e}")
        data_manager = None


def process_option_chain(chain: pd.DataFrame, current_price: float, risk_free_rate: Optional[float] = None) -> pd.DataFrame:
    """Process option chain and calculate Greeks"""
    
    # Get risk-free rate if not provided
    if risk_free_rate is None:
        risk_free_rate = get_risk_free_rate()
        logger.info(f"Using risk-free rate: {risk_free_rate:.4f}")
        
    # Extract symbol from contract
    contract_symbol = chain['contractSymbol'].iloc[0]
    symbol_match = re.match(r'^[A-Za-z]+', contract_symbol)
    if not symbol_match:
        raise ValueError(f"Could not extract symbol from contract: {contract_symbol}")
    symbol = symbol_match.group()
    
    # Get dividend yield
    try:
        ticker = yf.Ticker(symbol)
        div_yield = ticker.info.get('dividendYield', 0)
        if div_yield is None:
            div_yield = 0
    except Exception as e:
        logger.warning(f"Could not get dividend yield for {symbol}: {e}")
        div_yield = 0
        
    logger.info(f"Processing chain for {symbol} with div_yield={div_yield}")
        
    # Ensure we have the required columns
    if 'underlying_price' not in chain.columns:
        chain['underlying_price'] = current_price
    
    # Convert expiry to datetime and handle timezone
    chain['expiry'] = pd.to_datetime(chain['expiry'])
    
    # Calculate time to expiration
    now = datetime.datetime.now()
    chain['expiry'] = pd.to_datetime(chain['expiry'])
    chain['dte'] = (chain['expiry'] - now).dt.total_seconds() / (24 * 60 * 60)  # Exact DTE in days
    
     # Initialize Greeks calculator
    calculator = GreeksCalculator()
    
    # Calculate Greeks for each option
    for idx, row in chain.iterrows():
        try:
            # Skip if invalid IV
            if pd.isna(row['impliedVolatility']) or row['impliedVolatility'] <= 0:
                logger.warning(f"Skipping row {idx} due to invalid IV: {row['impliedVolatility']}")
                continue
                
            # Log key inputs
            logger.debug(f"Processing option: Strike={row['strike']}, IV={row['impliedVolatility']}, DTE={row['dte']}")
            
            # Calculate Greeks
            greeks = calculator.calculate_greeks(
                float(current_price),
                float(row['strike']),
                float(row['dte']) / 365,  # Convert DTE to years
                float(risk_free_rate),
                float(row['impliedVolatility']),
                float(div_yield),
                'CALL' if row['option_type'] == 'call' else 'PUT'
            )
            
            # Update DataFrame with Greeks
            for greek, value in greeks.items():
                chain.loc[idx, greek] = value
                
            # Log results
            logger.debug(f"Calculated Greeks for row {idx}: {greeks}")
            
        except Exception as e:
            logger.error(f"Error processing row {idx}: {e}")
            # Set Greeks to NaN on error
            for greek in ['delta', 'gamma', 'theta', 'vega', 'rho']:
                chain.loc[idx, greek] = np.nan
    
    # Calculate probability ITM based on delta
    chain['prob_itm'] = chain.apply(
        lambda row: abs(row['delta']) if not pd.isna(row['delta']) else 0,
        axis=1
    )
    
    return chain

@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="get_stock_info",
            description="Get comprehensive stock information including price, volume, market cap, and key metrics",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol (e.g., AAPL, TSLA)"}
                },
                "required": ["symbol"]
            }
        ),
        Tool(
            name="get_expiration_dates",
            description="Get all available options expiration dates for a stock",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol"}
                },
                "required": ["symbol"]
            }
        ),
        Tool(
            name="get_option_chain",
            description="Get options chain data with Greeks for a specific expiration date. Returns calls and puts with strike, bid, ask, volume, IV, and calculated Greeks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol"},
                    "expiration_date": {"type": "string", "description": "Expiration date (YYYY-MM-DD). If not provided, uses nearest expiration."},
                    "option_type": {
                        "type": "string",
                        "enum": ["call", "put", "all"],
                        "description": "Filter by option type (default: all)",
                        "default": "all"
                    }
                },
                "required": ["symbol"]
            }
        ),
        Tool(
            name="calculate_greeks",
            description="Calculate option Greeks (delta, gamma, theta, vega, rho) for a specific option using Black-Scholes model",
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_price": {"type": "number", "description": "Current stock price"},
                    "strike_price": {"type": "number", "description": "Option strike price"},
                    "days_to_expiration": {"type": "number", "description": "Days until expiration"},
                    "implied_volatility": {"type": "number", "description": "Implied volatility as decimal (e.g., 0.25 for 25%)"},
                    "option_type": {
                        "type": "string",
                        "enum": ["call", "put"],
                        "description": "Option type"
                    },
                    "risk_free_rate": {
                        "type": "number",
                        "description": "Risk-free rate as decimal (default: current Treasury rate)",
                        "default": 0.05
                    },
                    "dividend_yield": {
                        "type": "number",
                        "description": "Annual dividend yield as decimal (default: 0)",
                        "default": 0
                    }
                },
                "required": ["stock_price", "strike_price", "days_to_expiration", "implied_volatility", "option_type"]
            }
        ),
        Tool(
            name="analyze_basic_strategies",
            description="Analyze basic options strategies: CCS (Credit Call Spread), PCS (Put Credit Spread), CSP (Cash Secured Put), CC (Covered Call)",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol"},
                    "strategy": {
                        "type": "string",
                        "enum": ["ccs", "pcs", "csp", "cc"],
                        "description": "Options strategy to analyze"
                    },
                    "delta_target": {
                        "type": "number",
                        "description": "Target delta for CSP/CC (default: 0.3)",
                        "default": 0.3
                    },
                    "width_pct": {
                        "type": "number",
                        "description": "Width for spreads as decimal (default: 0.05)",
                        "default": 0.05
                    },
                    "expiration_date": {
                        "type": "string",
                        "description": "Options expiration date (YYYY-MM-DD)"
                    }
                },
                "required": ["symbol", "strategy", "expiration_date"]
            }
        ),
        Tool(
            name="compare_strategies",
            description="Compare multiple options strategies for the same symbol and expiration. Returns side-by-side comparison with risk metrics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol"},
                    "expiration_date": {"type": "string", "description": "Expiration date (YYYY-MM-DD)"},
                    "strategies": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["ccs", "pcs", "csp", "cc"]
                        },
                        "description": "List of strategies to compare (e.g., ['ccs', 'pcs', 'csp'])"
                    },
                    "delta_target": {
                        "type": "number",
                        "description": "Target delta for CSP/CC (default: 0.3)",
                        "default": 0.3
                    }
                },
                "required": ["symbol", "expiration_date", "strategies"]
            }
        ),
        Tool(
            name="analyze_pnl_scenarios",
            description="Analyze profit/loss scenarios for an options strategy at different stock prices at expiration",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol"},
                    "strategy": {
                        "type": "string",
                        "enum": ["ccs", "pcs", "csp", "cc"],
                        "description": "Options strategy type"
                    },
                    "expiration_date": {"type": "string", "description": "Expiration date (YYYY-MM-DD)"},
                    "price_range_pct": {
                        "type": "number",
                        "description": "Percentage range around current price to analyze (default: 0.20 for +/- 20%)",
                        "default": 0.20
                    },
                    "steps": {
                        "type": "integer",
                        "description": "Number of price points to calculate (default: 20)",
                        "default": 20
                    }
                },
                "required": ["symbol", "strategy", "expiration_date"]
            }
        ),
        Tool(
            name="find_best_strategies",
            description="Find the best options strategies based on risk/reward criteria for a given symbol and expiration",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol"},
                    "expiration_date": {"type": "string", "description": "Expiration date (YYYY-MM-DD). If not provided, uses nearest 30-45 DTE."},
                    "min_probability_profit": {
                        "type": "number",
                        "description": "Minimum probability of profit (default: 0.60)",
                        "default": 0.60
                    },
                    "max_risk_reward_ratio": {
                        "type": "number",
                        "description": "Maximum risk/reward ratio (default: 3.0)",
                        "default": 3.0
                    },
                    "strategy_preference": {
                        "type": "string",
                        "enum": ["bullish", "bearish", "neutral", "any"],
                        "description": "Market outlook preference (default: any)",
                        "default": "any"
                    }
                },
                "required": ["symbol"]
            }
        ),
        Tool(
            name="get_data_sources_status",
            description="Get status of all available data sources. Shows which providers are available and their rate limit status.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]

@app.call_tool()
@retry_on_error(max_retries=3, delay=1.0)
async def call_tool(name: str, arguments: dict):
    try:
        # ==================== get_stock_info ====================
        if name == "get_stock_info":
            symbol = arguments['symbol'].strip().upper()
            ticker = yf.Ticker(symbol)
            
            try:
                info = ticker.info
                hist = ticker.history(period='1d')
                current_price = hist['Close'].iloc[-1] if not hist.empty else (
                    info.get('regularMarketPrice') or info.get('currentPrice')
                )
            except Exception as e:
                raise APIError(f"Could not fetch data for {symbol}: {str(e)}")
            
            if not current_price:
                raise APIError(f"Could not get current price for {symbol}")
            
            # Get dividend yield
            div_yield = info.get('dividendYield', 0) or 0
            
            response = {
                "symbol": symbol,
                "company_name": info.get('longName') or info.get('shortName'),
                "current_price": float(current_price),
                "previous_close": info.get('previousClose'),
                "day_open": info.get('regularMarketOpen'),
                "day_high": info.get('dayHigh'),
                "day_low": info.get('dayLow'),
                "volume": info.get('volume'),
                "avg_volume": info.get('averageVolume'),
                "market_cap": info.get('marketCap'),
                "pe_ratio": info.get('trailingPE'),
                "forward_pe": info.get('forwardPE'),
                "dividend_yield": div_yield,
                "beta": info.get('beta'),
                "52_week_high": info.get('fiftyTwoWeekHigh'),
                "52_week_low": info.get('fiftyTwoWeekLow'),
                "50_day_ma": info.get('fiftyDayAverage'),
                "200_day_ma": info.get('twoHundredDayAverage'),
                "shares_outstanding": info.get('sharesOutstanding'),
                "float_shares": info.get('floatShares'),
                "sector": info.get('sector'),
                "industry": info.get('industry'),
                "website": info.get('website'),
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            return format_response(response)
        
        # ==================== get_expiration_dates ====================
        elif name == "get_expiration_dates":
            symbol = arguments['symbol'].strip().upper()
            ticker = yf.Ticker(symbol)
            
            exp_dates = ticker.options
            if not exp_dates:
                raise APIError(f"No options available for {symbol}")
            
            today = datetime.datetime.now()
            
            # Enrich with DTE information
            dates_info = []
            for date_str in exp_dates:
                exp_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                dte = (exp_date - today).days
                if dte > 0:
                    dates_info.append({
                        "date": date_str,
                        "days_to_expiration": dte,
                        "expiration_type": "weekly" if dte <= 7 else ("monthly" if dte <= 45 else "quarterly")
                    })
            
            response = {
                "symbol": symbol,
                "total_expirations": len(dates_info),
                "expiration_dates": dates_info,
                "nearest_expiration": dates_info[0] if dates_info else None,
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            return format_response(response)
        
        # ==================== get_option_chain ====================
        elif name == "get_option_chain":
            symbol = arguments['symbol'].strip().upper()
            option_type = arguments.get('option_type', 'all').lower()
            
            ticker = yf.Ticker(symbol)
            
            # Get current price
            try:
                current_price = ticker.history(period='1d')['Close'].iloc[-1]
            except:
                info = ticker.info
                current_price = info.get('regularMarketPrice') or info.get('currentPrice')
            
            if not current_price:
                raise APIError(f"Could not get current price for {symbol}")
            
            # Get expiration dates
            exp_dates = ticker.options
            if not exp_dates:
                raise APIError(f"No options available for {symbol}")
            
            # Use provided or nearest expiration
            requested_expiry = arguments.get('expiration_date')
            if requested_expiry:
                if requested_expiry not in exp_dates:
                    raise ValidationError(f"Expiration {requested_expiry} not available. Available: {', '.join(exp_dates[:5])}")
            else:
                requested_expiry = exp_dates[0]
            
            # Get the chain
            chain = ticker.option_chain(requested_expiry)
            if not hasattr(chain, 'calls') or not hasattr(chain, 'puts'):
                raise APIError("Invalid options chain data")
            
            # Get risk-free rate and dividend yield
            risk_free_rate = get_risk_free_rate()
            try:
                div_yield = ticker.info.get('dividendYield', 0) or 0
            except:
                div_yield = 0
            
            expiry_date = pd.to_datetime(requested_expiry)
            now = datetime.datetime.now()
            dte = (expiry_date - now).total_seconds() / (24 * 60 * 60)
            
            # Process calls
            calls_data = []
            if option_type in ['all', 'call'] and not chain.calls.empty:
                calls_df = chain.calls.copy()
                calls_df['option_type'] = 'call'
                calls_df['underlying_price'] = current_price
                calls_df['expiry'] = expiry_date
                calls_df['dte'] = dte
                calls_processed = process_option_chain(calls_df, current_price, risk_free_rate)
                
                for _, row in calls_processed.iterrows():
                    calls_data.append({
                        "strike": float(row['strike']),
                        "last_price": float(row.get('lastPrice', 0)),
                        "bid": float(row.get('bid', 0)),
                        "ask": float(row.get('ask', 0)),
                        "volume": int(row.get('volume', 0)),
                        "open_interest": int(row.get('openInterest', 0)),
                        "implied_volatility": float(row.get('impliedVolatility', 0)),
                        "delta": float(row.get('delta', 0)) if not pd.isna(row.get('delta')) else None,
                        "gamma": float(row.get('gamma', 0)) if not pd.isna(row.get('gamma')) else None,
                        "theta": float(row.get('theta', 0)) if not pd.isna(row.get('theta')) else None,
                        "vega": float(row.get('vega', 0)) if not pd.isna(row.get('vega')) else None,
                        "rho": float(row.get('rho', 0)) if not pd.isna(row.get('rho')) else None,
                        "itm": bool(row.get('inTheMoney', False)),
                        "contract_symbol": row.get('contractSymbol', '')
                    })
            
            # Process puts
            puts_data = []
            if option_type in ['all', 'put'] and not chain.puts.empty:
                puts_df = chain.puts.copy()
                puts_df['option_type'] = 'put'
                puts_df['underlying_price'] = current_price
                puts_df['expiry'] = expiry_date
                puts_df['dte'] = dte
                puts_processed = process_option_chain(puts_df, current_price, risk_free_rate)
                
                for _, row in puts_processed.iterrows():
                    puts_data.append({
                        "strike": float(row['strike']),
                        "last_price": float(row.get('lastPrice', 0)),
                        "bid": float(row.get('bid', 0)),
                        "ask": float(row.get('ask', 0)),
                        "volume": int(row.get('volume', 0)),
                        "open_interest": int(row.get('openInterest', 0)),
                        "implied_volatility": float(row.get('impliedVolatility', 0)),
                        "delta": float(row.get('delta', 0)) if not pd.isna(row.get('delta')) else None,
                        "gamma": float(row.get('gamma', 0)) if not pd.isna(row.get('gamma')) else None,
                        "theta": float(row.get('theta', 0)) if not pd.isna(row.get('theta')) else None,
                        "vega": float(row.get('vega', 0)) if not pd.isna(row.get('vega')) else None,
                        "rho": float(row.get('rho', 0)) if not pd.isna(row.get('rho')) else None,
                        "itm": bool(row.get('inTheMoney', False)),
                        "contract_symbol": row.get('contractSymbol', '')
                    })
            
            response = {
                "symbol": symbol,
                "current_price": float(current_price),
                "expiration_date": requested_expiry,
                "days_to_expiration": int(dte),
                "risk_free_rate": risk_free_rate,
                "dividend_yield": div_yield,
                "calls_count": len(calls_data),
                "puts_count": len(puts_data),
                "calls": calls_data if option_type in ['all', 'call'] else [],
                "puts": puts_data if option_type in ['all', 'put'] else [],
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            return format_response(response)
        
        # ==================== calculate_greeks ====================
        elif name == "calculate_greeks":
            stock_price = float(arguments['stock_price'])
            strike_price = float(arguments['strike_price'])
            dte = float(arguments['days_to_expiration'])
            iv = float(arguments['implied_volatility'])
            option_type = arguments['option_type'].upper()
            r = float(arguments.get('risk_free_rate', 0.05))
            q = float(arguments.get('dividend_yield', 0))
            
            if option_type not in ['CALL', 'PUT']:
                raise ValidationError("option_type must be 'call' or 'put'")
            
            if dte <= 0:
                raise ValidationError("days_to_expiration must be positive")
            
            if iv <= 0:
                raise ValidationError("implied_volatility must be positive")
            
            T = dte / 365.0  # Convert to years
            
            greeks = greeks_calculator.calculate_greeks(
                S=stock_price,
                K=strike_price,
                T=T,
                r=r,
                sigma=iv,
                q=q,
                option_type=option_type
            )
            
            # Calculate theoretical price using Black-Scholes
            d1 = GreeksCalculator.calculate_d1(stock_price, strike_price, T, r, iv, q)
            d2 = GreeksCalculator.calculate_d2(stock_price, strike_price, T, r, iv, q)
            
            if option_type == 'CALL':
                price = stock_price * np.exp(-q*T) * norm.cdf(d1) - strike_price * np.exp(-r*T) * norm.cdf(d2)
            else:
                price = strike_price * np.exp(-r*T) * norm.cdf(-d2) - stock_price * np.exp(-q*T) * norm.cdf(-d1)
            
            response = {
                "inputs": {
                    "stock_price": stock_price,
                    "strike_price": strike_price,
                    "days_to_expiration": dte,
                    "time_to_expiration_years": round(T, 4),
                    "implied_volatility": iv,
                    "implied_volatility_pct": f"{iv*100:.1f}%",
                    "option_type": option_type,
                    "risk_free_rate": r,
                    "dividend_yield": q
                },
                "theoretical_price": float(price),
                "greeks": {
                    "delta": greeks['delta'],
                    "gamma": greeks['gamma'],
                    "theta": greeks['theta'],
                    "theta_daily": greeks['theta'],
                    "vega": greeks['vega'],
                    "rho": greeks['rho']
                },
                "interpretation": {
                    "delta_meaning": f"Option price changes by ${abs(greeks['delta']):.4f} per $1 stock move",
                    "gamma_meaning": f"Delta changes by {greeks['gamma']:.4f} per $1 stock move",
                    "theta_meaning": f"Option loses ${abs(greeks['theta']):.4f} per day from time decay",
                    "vega_meaning": f"Option price changes by ${greeks['vega']:.4f} per 1% IV change",
                    "rho_meaning": f"Option price changes by ${greeks['rho']:.4f} per 1% rate change"
                },
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            return format_response(response)
        
        # ==================== analyze_basic_strategies ====================
        elif name == "analyze_basic_strategies":
            symbol = arguments['symbol'].strip().upper()
            strategy = arguments['strategy'].lower()
            delta_target = arguments.get('delta_target', 0.3)
            width_pct = arguments.get('width_pct', 0.05)
            requested_expiry = arguments['expiration_date']
            
            ticker = yf.Ticker(symbol)
            
            # Get current price
            try:
                current_price = ticker.history(period='1d')['Close'].iloc[-1]
            except:
                info = ticker.info
                current_price = info.get('regularMarketPrice') or info.get('currentPrice')
            
            if not current_price:
                raise APIError(f"Could not get current price for {symbol}")
            
            # Get expiration dates and validate
            exp_dates = ticker.options
            if not exp_dates:
                raise APIError(f"No options available for {symbol}")
            
            if requested_expiry not in exp_dates:
                raise ValidationError(f"Expiration {requested_expiry} not available. Available dates: {', '.join(exp_dates[:5])}")
            
            # Calculate DTE
            today = pd.Timestamp.now().normalize()
            expiry_date = pd.to_datetime(requested_expiry).normalize()
            dte = (expiry_date - today).days
            
            # Initialize response
            response = {
                "symbol": symbol,
                "strategy": strategy.upper(),
                "current_price": float(current_price),
                "expiration": requested_expiry,
                "days_to_expiration": dte
            }
            
            if dte < 30:
                valid_dates = [date for date in exp_dates 
                            if (pd.to_datetime(date) - pd.Timestamp.now()).days >= 30]
                if valid_dates:
                    response["warning"] = f"Short-dated option. Consider {valid_dates[0]} for better premium."
            
            if dte < 1:
                raise ValidationError(f"Expiration too soon. DTE must be at least 1, got {dte}")
            
            # Get and process the chain
            chain = ticker.option_chain(requested_expiry)
            
            calls = chain.calls.copy()
            puts = chain.puts.copy()
            calls['option_type'] = 'call'
            puts['option_type'] = 'put'
            calls['underlying_price'] = current_price
            puts['underlying_price'] = current_price
            calls['expiry'] = expiry_date
            puts['expiry'] = expiry_date
            
            risk_free_rate = get_risk_free_rate()
            calls_processed = process_option_chain(calls, current_price, risk_free_rate)
            puts_processed = process_option_chain(puts, current_price, risk_free_rate)
            
            # Analyze strategy
            if strategy == "ccs":
                analysis, error = strategy_analyzer.analyze_credit_call_spread(calls_processed, width_pct=width_pct)
            elif strategy == "pcs":
                analysis, error = strategy_analyzer.analyze_put_credit_spread(puts_processed, width_pct=width_pct)
            elif strategy == "csp":
                analysis, error = strategy_analyzer.analyze_cash_secured_put(puts_processed, delta_target=delta_target)
            elif strategy == "cc":
                analysis, error = strategy_analyzer.analyze_covered_call(calls_processed, delta_target=delta_target)
            else:
                raise ValidationError(f"Invalid strategy: {strategy}")
            
            if error:
                raise APIError(error)
            
            if not analysis:
                raise APIError(f"Could not analyze {strategy.upper()} strategy - no valid options found")
            
            response["analysis"] = analysis
            
            return format_response(response)
        
        # ==================== compare_strategies ====================
        elif name == "compare_strategies":
            symbol = arguments['symbol'].strip().upper()
            expiration_date = arguments['expiration_date']
            strategies = arguments['strategies']
            delta_target = arguments.get('delta_target', 0.3)
            
            ticker = yf.Ticker(symbol)
            
            # Get current price
            try:
                current_price = ticker.history(period='1d')['Close'].iloc[-1]
            except:
                info = ticker.info
                current_price = info.get('regularMarketPrice') or info.get('currentPrice')
            
            if not current_price:
                raise APIError(f"Could not get current price for {symbol}")
            
            # Validate expiration
            exp_dates = ticker.options
            if not exp_dates:
                raise APIError(f"No options available for {symbol}")
            
            if expiration_date not in exp_dates:
                raise ValidationError(f"Expiration {expiration_date} not available")
            
            # Get and process chains
            chain = ticker.option_chain(expiration_date)
            expiry_date = pd.to_datetime(expiration_date)
            now = datetime.datetime.now()
            dte = int((expiry_date - now).total_seconds() / (24 * 60 * 60))
            
            calls = chain.calls.copy()
            puts = chain.puts.copy()
            calls['option_type'] = 'call'
            puts['option_type'] = 'put'
            calls['underlying_price'] = current_price
            puts['underlying_price'] = current_price
            calls['expiry'] = expiry_date
            puts['expiry'] = expiry_date
            
            risk_free_rate = get_risk_free_rate()
            calls_processed = process_option_chain(calls, current_price, risk_free_rate)
            puts_processed = process_option_chain(puts, current_price, risk_free_rate)
            
            # Analyze each strategy
            results = []
            for strategy in strategies:
                strategy = strategy.lower()
                
                if strategy == "ccs":
                    analysis, error = strategy_analyzer.analyze_credit_call_spread(calls_processed, width_pct=0.05)
                elif strategy == "pcs":
                    analysis, error = strategy_analyzer.analyze_put_credit_spread(puts_processed, width_pct=0.05)
                elif strategy == "csp":
                    analysis, error = strategy_analyzer.analyze_cash_secured_put(puts_processed, delta_target=delta_target)
                elif strategy == "cc":
                    analysis, error = strategy_analyzer.analyze_covered_call(calls_processed, delta_target=delta_target)
                else:
                    continue
                
                if analysis and not error:
                    results.append({
                        "strategy": strategy.upper(),
                        "analysis": analysis
                    })
            
            # Sort by probability of profit
            def get_pop(result):
                metrics = result['analysis'].get('metrics', {})
                return metrics.get('probability_of_profit', 0)
            
            results.sort(key=get_pop, reverse=True)
            
            response = {
                "symbol": symbol,
                "current_price": float(current_price),
                "expiration_date": expiration_date,
                "days_to_expiration": dte,
                "risk_free_rate": risk_free_rate,
                "strategies_compared": len(results),
                "comparison": results,
                "recommendation": results[0] if results else None,
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            return format_response(response)
        
        # ==================== analyze_pnl_scenarios ====================
        elif name == "analyze_pnl_scenarios":
            symbol = arguments['symbol'].strip().upper()
            strategy_type = arguments['strategy'].lower()
            expiration_date = arguments['expiration_date']
            price_range_pct = arguments.get('price_range_pct', 0.20)
            steps = arguments.get('steps', 20)
            
            ticker = yf.Ticker(symbol)
            
            # Get current price
            try:
                current_price = ticker.history(period='1d')['Close'].iloc[-1]
            except:
                info = ticker.info
                current_price = info.get('regularMarketPrice') or info.get('currentPrice')
            
            if not current_price:
                raise APIError(f"Could not get current price for {symbol}")
            
            # Validate expiration
            exp_dates = ticker.options
            if expiration_date not in exp_dates:
                raise ValidationError(f"Expiration {expiration_date} not available")
            
            # Get and process chains
            chain = ticker.option_chain(expiration_date)
            expiry_date = pd.to_datetime(expiration_date)
            now = datetime.datetime.now()
            dte = int((expiry_date - now).total_seconds() / (24 * 60 * 60))
            
            calls = chain.calls.copy()
            puts = chain.puts.copy()
            calls['option_type'] = 'call'
            puts['option_type'] = 'put'
            calls['underlying_price'] = current_price
            puts['underlying_price'] = current_price
            calls['expiry'] = expiry_date
            puts['expiry'] = expiry_date
            
            risk_free_rate = get_risk_free_rate()
            calls_processed = process_option_chain(calls, current_price, risk_free_rate)
            puts_processed = process_option_chain(puts, current_price, risk_free_rate)
            
            # Analyze strategy to get strikes
            if strategy_type == "ccs":
                analysis, error = strategy_analyzer.analyze_credit_call_spread(calls_processed)
            elif strategy_type == "pcs":
                analysis, error = strategy_analyzer.analyze_put_credit_spread(puts_processed)
            elif strategy_type == "csp":
                analysis, error = strategy_analyzer.analyze_cash_secured_put(puts_processed)
            elif strategy_type == "cc":
                analysis, error = strategy_analyzer.analyze_covered_call(calls_processed)
            else:
                raise ValidationError(f"Invalid strategy: {strategy_type}")
            
            if error or not analysis:
                raise APIError(f"Could not analyze strategy: {error}")
            
            # Generate price scenarios
            price_low = current_price * (1 - price_range_pct)
            price_high = current_price * (1 + price_range_pct)
            price_points = np.linspace(price_low, price_high, steps)
            
            pnl_scenarios = []
            
            # Calculate P&L at each price point
            for price in price_points:
                if strategy_type == "ccs":
                    # Credit Call Spread: Max profit if below short strike, max loss if above long strike
                    short_strike = analysis['strikes']['short_strike']
                    long_strike = analysis['strikes']['long_strike']
                    credit = analysis['metrics']['credit']
                    
                    if price <= short_strike:
                        pnl = credit
                    elif price >= long_strike:
                        pnl = credit - (long_strike - short_strike)
                    else:
                        pnl = credit - (price - short_strike)
                    
                elif strategy_type == "pcs":
                    # Put Credit Spread
                    short_strike = analysis['strikes']['short_strike']
                    long_strike = analysis['strikes']['long_strike']
                    credit = analysis['metrics']['credit']
                    
                    if price >= short_strike:
                        pnl = credit
                    elif price <= long_strike:
                        pnl = credit - (short_strike - long_strike)
                    else:
                        pnl = credit - (short_strike - price)
                    
                elif strategy_type == "csp":
                    # Cash Secured Put
                    strike = analysis['strike']
                    premium = analysis['metrics']['premium']
                    
                    if price >= strike:
                        pnl = premium
                    else:
                        pnl = premium - (strike - price)
                    
                elif strategy_type == "cc":
                    # Covered Call
                    strike = analysis['strike']
                    premium = analysis['metrics']['premium']
                    
                    if price <= strike:
                        pnl = premium + (price - current_price)
                    else:
                        pnl = premium + (strike - current_price)
                
                pnl_scenarios.append({
                    "stock_price": round(float(price), 2),
                    "pnl": round(float(pnl), 2),
                    "pnl_percent": round(float(pnl / current_price * 100), 2),
                    "status": "profit" if pnl > 0 else ("breakeven" if pnl == 0 else "loss")
                })
            
            # Find key levels
            breakeven_points = [s for s in pnl_scenarios if s['pnl'] == 0]
            max_profit_scenario = max(pnl_scenarios, key=lambda x: x['pnl'])
            max_loss_scenario = min(pnl_scenarios, key=lambda x: x['pnl'])
            
            response = {
                "symbol": symbol,
                "current_price": float(current_price),
                "strategy": strategy_type.upper(),
                "expiration_date": expiration_date,
                "days_to_expiration": dte,
                "strategy_details": analysis,
                "price_range": {
                    "low": round(float(price_low), 2),
                    "high": round(float(price_high), 2),
                    "range_percent": f"{price_range_pct*100:.0f}%"
                },
                "scenarios": pnl_scenarios,
                "key_levels": {
                    "breakeven": breakeven_points[0] if breakeven_points else None,
                    "max_profit": max_profit_scenario,
                    "max_loss": max_loss_scenario
                },
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            return format_response(response)
        
        # ==================== find_best_strategies ====================
        elif name == "find_best_strategies":
            symbol = arguments['symbol'].strip().upper()
            min_pop = arguments.get('min_probability_profit', 0.60)
            max_rr = arguments.get('max_risk_reward_ratio', 3.0)
            preference = arguments.get('strategy_preference', 'any')
            
            ticker = yf.Ticker(symbol)
            
            # Get current price
            try:
                current_price = ticker.history(period='1d')['Close'].iloc[-1]
            except:
                info = ticker.info
                current_price = info.get('regularMarketPrice') or info.get('currentPrice')
            
            if not current_price:
                raise APIError(f"Could not get current price for {symbol}")
            
            # Get expiration dates
            exp_dates = ticker.options
            if not exp_dates:
                raise APIError(f"No options available for {symbol}")
            
            # Find optimal expiration (30-45 DTE preferred)
            requested_expiry = arguments.get('expiration_date')
            if not requested_expiry:
                now = datetime.datetime.now()
                target_dte_range = range(30, 46)
                for date_str in exp_dates:
                    exp_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                    dte = (exp_date - now).days
                    if dte in target_dte_range:
                        requested_expiry = date_str
                        break
                if not requested_expiry:
                    # Use first available after 30 days
                    for date_str in exp_dates:
                        exp_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                        dte = (exp_date - now).days
                        if dte >= 30:
                            requested_expiry = date_str
                            break
                if not requested_expiry:
                    requested_expiry = exp_dates[0]
            
            # Get and process chains
            chain = ticker.option_chain(requested_expiry)
            expiry_date = pd.to_datetime(requested_expiry)
            now = datetime.datetime.now()
            dte = int((expiry_date - now).total_seconds() / (24 * 60 * 60))
            
            calls = chain.calls.copy()
            puts = chain.puts.copy()
            calls['option_type'] = 'call'
            puts['option_type'] = 'put'
            calls['underlying_price'] = current_price
            puts['underlying_price'] = current_price
            calls['expiry'] = expiry_date
            puts['expiry'] = expiry_date
            
            risk_free_rate = get_risk_free_rate()
            calls_processed = process_option_chain(calls, current_price, risk_free_rate)
            puts_processed = process_option_chain(puts, current_price, risk_free_rate)
            
            # Define strategies to analyze based on preference
            if preference == 'bullish':
                strategies_to_check = [('pcs', puts_processed), ('cc', calls_processed), ('csp', puts_processed)]
            elif preference == 'bearish':
                strategies_to_check = [('ccs', calls_processed)]
            elif preference == 'neutral':
                strategies_to_check = [('pcs', puts_processed), ('ccs', calls_processed)]
            else:  # any
                strategies_to_check = [
                    ('ccs', calls_processed),
                    ('pcs', puts_processed),
                    ('csp', puts_processed),
                    ('cc', calls_processed)
                ]
            
            valid_strategies = []
            
            for strategy_name, chain_df in strategies_to_check:
                if strategy_name == "ccs":
                    analysis, error = strategy_analyzer.analyze_credit_call_spread(chain_df)
                elif strategy_name == "pcs":
                    analysis, error = strategy_analyzer.analyze_put_credit_spread(chain_df)
                elif strategy_name == "csp":
                    analysis, error = strategy_analyzer.analyze_cash_secured_put(chain_df)
                elif strategy_name == "cc":
                    analysis, error = strategy_analyzer.analyze_covered_call(chain_df)
                else:
                    continue
                
                if error or not analysis:
                    continue
                
                metrics = analysis.get('metrics', {})
                pop = metrics.get('probability_of_profit', 0)
                rr = metrics.get('risk_reward_ratio', float('inf'))
                
                # Filter by criteria
                if pop >= min_pop and rr <= max_rr:
                    valid_strategies.append({
                        "strategy": strategy_name.upper(),
                        "analysis": analysis,
                        "score": pop / rr if rr > 0 else 0,  # Higher is better
                        "probability_of_profit": pop,
                        "risk_reward_ratio": rr
                    })
            
            # Sort by score
            valid_strategies.sort(key=lambda x: x['score'], reverse=True)
            
            response = {
                "symbol": symbol,
                "current_price": float(current_price),
                "expiration_date": requested_expiry,
                "days_to_expiration": dte,
                "search_criteria": {
                    "min_probability_profit": min_pop,
                    "max_risk_reward_ratio": max_rr,
                    "preference": preference
                },
                "strategies_found": len(valid_strategies),
                "best_strategies": valid_strategies[:3],  # Top 3
                "recommendation": valid_strategies[0] if valid_strategies else None,
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            return format_response(response)
        
        # ==================== get_data_sources_status ====================
        elif name == "get_data_sources_status":
            if data_manager:
                status = data_manager.get_status()
                status["multi_source_enabled"] = True
            else:
                status = {
                    "multi_source_enabled": False,
                    "fallback_mode": True,
                    "primary_source": "Yahoo Finance (direct)",
                    "note": "Multi-source manager not initialized. Using Yahoo Finance directly."
                }
            
            return format_response(status)
        
        else:
            raise ValidationError(f"Unknown tool: {name}")
            
    except ValidationError as e:
        logger.error(f"Validation error in {name}: {str(e)}")
        return format_response(None, f"Validation error: {str(e)}")
        
    except APIError as e:
        logger.error(f"API error in {name}: {str(e)}\n{traceback.format_exc()}")
        return format_response(None, f"API error: {str(e)}")
        
    except Exception as e:
        logger.error(f"Unexpected error in {name}: {str(e)}\n{traceback.format_exc()}")
        return format_response(None, f"Internal error: {str(e)}")

async def main():    
    logger.info("Starting Options Analytics server...")
    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
    except Exception as e:
        logger.error(f"Server error: {str(e)}\n{traceback.format_exc()}")
        raise

if __name__ == "__main__":
    asyncio.run(main())