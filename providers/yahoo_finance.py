"""
Yahoo Finance data provider
"""

import yfinance as yf
import pandas as pd
from typing import Optional, List
from datetime import datetime
import time
import logging

from .base import (
    DataProvider, StockInfo, OptionChain, OptionContract,
    RateLimitError, DataProviderError
)

logger = logging.getLogger("options-analytics")


class YahooFinanceProvider(DataProvider):
    """Yahoo Finance data provider (free, but rate limited)"""
    
    def __init__(self):
        super().__init__("Yahoo Finance", priority=100)
        self._rate_limit_cooldown = 300  # 5 minutes
    
    async def get_stock_info(self, symbol: str) -> Optional[StockInfo]:
        """Get stock information from Yahoo Finance"""
        self._request_count += 1
        
        try:
            ticker = yf.Ticker(symbol.upper())
            
            # Try history first (less rate limited)
            hist = ticker.history(period='1d')
            if hist.empty:
                raise DataProviderError(f"No price data for {symbol}")
            
            current_price = hist['Close'].iloc[-1]
            
            # Try to get additional info
            info = {}
            try:
                info = ticker.info
            except Exception as e:
                logger.warning(f"Could not get full info for {symbol}: {e}")
            
            return StockInfo(
                symbol=symbol.upper(),
                current_price=float(current_price),
                previous_close=info.get('previousClose'),
                day_open=info.get('regularMarketOpen'),
                day_high=info.get('dayHigh'),
                day_low=info.get('dayLow'),
                volume=info.get('volume'),
                market_cap=info.get('marketCap'),
                pe_ratio=info.get('trailingPE'),
                dividend_yield=info.get('dividendYield', 0) or 0,
                beta=info.get('beta'),
                fifty_two_week_high=info.get('fiftyTwoWeekHigh'),
                fifty_two_week_low=info.get('fiftyTwoWeekLow'),
                company_name=info.get('longName') or info.get('shortName'),
                sector=info.get('sector'),
                industry=info.get('industry'),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            error_str = str(e).lower()
            if 'rate limit' in error_str or 'too many requests' in error_str:
                self.mark_rate_limited(self._rate_limit_cooldown)
                raise RateLimitError(self.name, self._rate_limit_cooldown)
            self._error_count += 1
            raise DataProviderError(f"Yahoo Finance error: {e}")
    
    async def get_expiration_dates(self, symbol: str) -> Optional[List[str]]:
        """Get available expiration dates"""
        self._request_count += 1
        
        try:
            ticker = yf.Ticker(symbol.upper())
            exp_dates = ticker.options
            
            if not exp_dates:
                raise DataProviderError(f"No options available for {symbol}")
            
            return list(exp_dates)
            
        except Exception as e:
            error_str = str(e).lower()
            if 'rate limit' in error_str or 'too many requests' in error_str:
                self.mark_rate_limited(self._rate_limit_cooldown)
                raise RateLimitError(self.name, self._rate_limit_cooldown)
            self._error_count += 1
            raise DataProviderError(f"Yahoo Finance error: {e}")
    
    async def get_option_chain(
        self, 
        symbol: str, 
        expiration_date: str
    ) -> Optional[OptionChain]:
        """Get option chain data"""
        self._request_count += 1
        
        try:
            ticker = yf.Ticker(symbol.upper())
            
            # Get stock price
            hist = ticker.history(period='1d')
            if hist.empty:
                raise DataProviderError(f"No price data for {symbol}")
            current_price = float(hist['Close'].iloc[-1])
            
            # Get option chain
            chain = ticker.option_chain(expiration_date)
            
            if chain is None:
                raise DataProviderError(f"No chain data for {symbol} {expiration_date}")
            
            # Calculate DTE
            expiry = datetime.strptime(expiration_date, '%Y-%m-%d')
            dte = (expiry - datetime.now()).days
            
            # Process calls
            calls = []
            if chain.calls is not None and not chain.calls.empty:
                for _, row in chain.calls.iterrows():
                    calls.append(OptionContract(
                        strike=float(row['strike']),
                        last_price=float(row.get('lastPrice', 0)),
                        bid=float(row.get('bid', 0)),
                        ask=float(row.get('ask', 0)),
                        volume=int(row.get('volume', 0)),
                        open_interest=int(row.get('openInterest', 0)),
                        implied_volatility=float(row.get('impliedVolatility', 0)),
                        option_type='call',
                        contract_symbol=str(row.get('contractSymbol', '')),
                        in_the_money=bool(row.get('inTheMoney', False)),
                        expiration_date=expiration_date
                    ))
            
            # Process puts
            puts = []
            if chain.puts is not None and not chain.puts.empty:
                for _, row in chain.puts.iterrows():
                    puts.append(OptionContract(
                        strike=float(row['strike']),
                        last_price=float(row.get('lastPrice', 0)),
                        bid=float(row.get('bid', 0)),
                        ask=float(row.get('ask', 0)),
                        volume=int(row.get('volume', 0)),
                        open_interest=int(row.get('openInterest', 0)),
                        implied_volatility=float(row.get('impliedVolatility', 0)),
                        option_type='put',
                        contract_symbol=str(row.get('contractSymbol', '')),
                        in_the_money=bool(row.get('inTheMoney', False)),
                        expiration_date=expiration_date
                    ))
            
            # Get dividend yield
            div_yield = 0.0
            try:
                info = ticker.info
                div_yield = info.get('dividendYield', 0) or 0
            except:
                pass
            
            return OptionChain(
                symbol=symbol.upper(),
                expiration_date=expiration_date,
                underlying_price=current_price,
                days_to_expiration=dte,
                calls=calls,
                puts=puts,
                dividend_yield=div_yield,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            error_str = str(e).lower()
            if 'rate limit' in error_str or 'too many requests' in error_str:
                self.mark_rate_limited(self._rate_limit_cooldown)
                raise RateLimitError(self.name, self._rate_limit_cooldown)
            self._error_count += 1
            raise DataProviderError(f"Yahoo Finance error: {e}")
    
    async def get_risk_free_rate(self) -> float:
        """Get risk-free rate from 13-week Treasury"""
        self._request_count += 1
        
        try:
            ticker = yf.Ticker("^IRX")
            hist = ticker.history(period='5d')
            
            if not hist.empty:
                rate = float(hist['Close'].iloc[-1]) / 100.0
                return rate
            
            return 0.05  # Default 5%
            
        except Exception as e:
            logger.warning(f"Could not fetch risk-free rate: {e}")
            return 0.05  # Default fallback
