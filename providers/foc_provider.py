"""
FOC (freeoptionschain) data provider - Options from NASDAQ, no API key
pip install freeoptionschain
"""

import asyncio
import logging
from typing import Optional, List
from datetime import datetime

from .base import (
    DataProvider, StockInfo, OptionChain, OptionContract,
    DataProviderError
)

logger = logging.getLogger("options-analytics")


def _run_sync(func, *args, **kwargs):
    """Run sync FOC in executor"""
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(None, lambda: func(*args, **kwargs))


class FOCProvider(DataProvider):
    """
    freeoptionschain - Options data from NASDAQ, no API key required.
    Install: pip install freeoptionschain
    """

    def __init__(self):
        super().__init__("FOC (NASDAQ)", priority=98)  # High priority, no key needed
        self._foc = None
        self._available = True

    def _get_foc(self):
        """Lazy init FOC"""
        if self._foc is None:
            try:
                from FOC import FOC
                self._foc = FOC()
            except ImportError:
                self._available = False
                raise DataProviderError("freeoptionschain not installed: pip install freeoptionschain")
        return self._foc

    def is_available(self) -> bool:
        if not self._available:
            return False
        try:
            self._get_foc()
            return super().is_available()
        except DataProviderError:
            return False

    async def get_stock_info(self, symbol: str) -> Optional[StockInfo]:
        """Fallback: derive from option chain underlying price when other providers fail"""
        try:
            dates = await self.get_expiration_dates(symbol)
            if not dates:
                return None
            chain = await self.get_option_chain(symbol, dates[0])
            if chain and chain.underlying_price > 0:
                return StockInfo(
                    symbol=symbol.upper(),
                    current_price=chain.underlying_price,
                    previous_close=None,
                    day_open=None,
                    day_high=None,
                    day_low=None,
                    volume=None,
                    market_cap=None,
                    company_name=None,
                    timestamp=datetime.now(),
                )
        except Exception as e:
            logger.debug(f"FOC stock info fallback failed for {symbol}: {e}")
        return None

    def _normalize_exp_date(self, d) -> str:
        """Convert FOC date to YYYY-MM-DD"""
        s = str(d)
        if "-" in s and len(s) >= 10:
            return s[:10]  # YYYY-MM-DD
        try:
            from datetime import date
            if hasattr(d, "strftime"):
                return d.strftime("%Y-%m-%d")
            if hasattr(d, "year"):
                return f"{d.year:04d}-{d.month:02d}-{d.day:02d}"
        except Exception:
            pass
        return s

    async def get_expiration_dates(self, symbol: str) -> Optional[List[str]]:
        """Get expiration dates from NASDAQ via FOC"""
        self._request_count += 1
        try:
            foc = self._get_foc()
            dates = await _run_sync(foc.get_expiration_dates, symbol.upper())
            if dates:
                lst = list(dates) if isinstance(dates, (list, tuple)) else [dates]
                return [self._normalize_exp_date(d) for d in lst if d is not None]
            raise DataProviderError(f"No expirations for {symbol}")
        except DataProviderError:
            raise
        except Exception as e:
            self._error_count += 1
            raise DataProviderError(f"FOC error: {e}")

    async def get_option_chain(
        self, symbol: str, expiration_date: str
    ) -> Optional[OptionChain]:
        """Get option chain from NASDAQ via FOC"""
        self._request_count += 1
        try:
            foc = self._get_foc()
            # FOC API: get_options_chain(symbol[, expiration])
            try:
                chain = await _run_sync(foc.get_options_chain, symbol.upper(), expiration_date)
            except TypeError:
                chain = await _run_sync(foc.get_options_chain, symbol.upper())
            if chain is None:
                raise DataProviderError(f"No chain for {symbol} {expiration_date}")

            # Convert FOC format to our OptionChain
            # FOC structure may vary - adapt based on actual API
            if hasattr(chain, "calls") and hasattr(chain, "puts"):
                calls_df = chain.calls
                puts_df = chain.puts
                underlying = float(getattr(chain, "underlying_price", 0) or 0)
            elif isinstance(chain, dict):
                calls_df = chain.get("calls", chain.get("call", []))
                puts_df = chain.get("puts", chain.get("put", []))
                underlying = float(chain.get("underlying_price", chain.get("underlyingPrice", 0)) or 0)
            else:
                raise DataProviderError(f"Unknown FOC chain format")

            def to_contracts(df, opt_type: str) -> List[OptionContract]:
                if df is None:
                    return []
                contracts = []
                iter_df = df.iterrows() if hasattr(df, "iterrows") else enumerate(df)
                for _, row in iter_df:
                    if hasattr(row, "get"):
                        r = row
                    elif isinstance(row, dict):
                        r = row
                    else:
                        continue
                    strike = float(r.get("strike", r.get("Strike", 0)))
                    last = float(r.get("lastPrice", r.get("last", r.get("Last", 0))) or 0)
                    bid = float(r.get("bid", r.get("Bid", 0))) or last
                    ask = float(r.get("ask", r.get("Ask", 0))) or last
                    vol = int(r.get("volume", r.get("Volume", 0))) or 0
                    oi = int(r.get("openInterest", r.get("Open Interest", 0))) or 0
                    iv = float(r.get("impliedVolatility", r.get("IV", 0))) or 0
                    contracts.append(OptionContract(
                        strike=strike,
                        last_price=last,
                        bid=bid,
                        ask=ask,
                        volume=vol,
                        open_interest=oi,
                        implied_volatility=iv,
                        option_type=opt_type,
                        contract_symbol=str(r.get("contractSymbol", r.get("Contract", ""))),
                        in_the_money=bool(r.get("inTheMoney", r.get("ITM", False))),
                        expiration_date=expiration_date,
                    ))
                return contracts

            calls = to_contracts(calls_df, "call") if hasattr(calls_df, "iterrows") or isinstance(calls_df, list) else []
            puts = to_contracts(puts_df, "put") if hasattr(puts_df, "iterrows") or isinstance(puts_df, list) else []

            if not calls and not puts:
                raise DataProviderError(f"Empty chain for {symbol} {expiration_date}")

            expiry = datetime.strptime(expiration_date, "%Y-%m-%d")
            dte = max(0, (expiry - datetime.now()).days)

            return OptionChain(
                symbol=symbol.upper(),
                expiration_date=expiration_date,
                underlying_price=underlying,
                days_to_expiration=dte,
                calls=calls,
                puts=puts,
                timestamp=datetime.now(),
            )
        except DataProviderError:
            raise
        except Exception as e:
            self._error_count += 1
            raise DataProviderError(f"FOC error: {e}")

    async def get_risk_free_rate(self) -> float:
        """FOC doesn't provide rate - use default"""
        return 0.05
