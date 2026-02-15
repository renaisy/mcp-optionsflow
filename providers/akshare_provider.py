"""
AKShare 数据源 - 中国 A 股/ETF 期权 (与美股期权源并存)
支持: 华夏上证50ETF(510050)、华泰柏瑞沪深300ETF(510300)、南方中证500ETF(510500)、
     华夏科创50ETF(588000)、易方达科创50ETF(588080) 等上交所金融期权
"""

import asyncio
import re
import logging
from typing import Optional, List
from datetime import datetime
from calendar import monthrange

from .base import (
    DataProvider, StockInfo, OptionChain, OptionContract,
    DataProviderError
)

try:
    from optionsflow import GreeksCalculator
except ImportError:
    GreeksCalculator = None

logger = logging.getLogger("options-analytics")

# 标的代码 -> AKShare 金融期权名称 (上交所，option_finance_board 有 当前价)
SYMBOL_TO_AKSHARE: dict[str, str] = {
    "510050": "华夏上证50ETF期权",
    "510300": "华泰柏瑞沪深300ETF期权",
    "510500": "南方中证500ETF期权",
    "588000": "华夏科创50ETF期权",
    "588080": "易方达科创50ETF期权",
}


def _is_china_symbol(symbol: str) -> bool:
    """判断是否为中国市场标的 (ETF 代码或中文名)"""
    s = str(symbol).strip()
    if s in SYMBOL_TO_AKSHARE:
        return True
    if s in SYMBOL_TO_AKSHARE.values():
        return True
    # 6 位数字 (ETF 代码)
    if re.match(r"^\d{6}$", s):
        return True
    # 含中文
    if re.search(r"[\u4e00-\u9fff]", s):
        return True
    return False


def _resolve_akshare_symbol(symbol: str) -> Optional[str]:
    """解析为 AKShare option_finance_board 使用的 symbol"""
    s = str(symbol).strip()
    if s in SYMBOL_TO_AKSHARE:
        return SYMBOL_TO_AKSHARE[s]
    if s in SYMBOL_TO_AKSHARE.values():
        return s
    return None


def _exp_to_yymm(expiration_date: str) -> str:
    """将 YYYY-MM-DD 转为 YYMM"""
    try:
        dt = datetime.strptime(expiration_date, "%Y-%m-%d")
        return dt.strftime("%y%m")
    except ValueError:
        # 兼容 2502 形式
        m = re.match(r"(\d{2})(\d{2})", str(expiration_date))
        if m:
            return m.group(1) + m.group(2)
        return str(expiration_date).replace("-", "")[-4:]


def _yymm_to_expiration(yymm: str) -> str:
    """将 YYMM 转为近似到期日 YYYY-MM-DD (当月第四个周三)"""
    yy, mm = int("20" + yymm[:2]), int(yymm[2:4])
    _, last = monthrange(yy, mm)
    # 第四个周三
    count = 0
    for d in range(1, last + 1):
        wd = datetime(yy, mm, d).weekday()  # 0=Mon
        if wd == 2:
            count += 1
            if count == 4:
                return f"{yy:04d}-{mm:02d}-{d:02d}"
    return f"{yy:04d}-{mm:02d}-28"


def _run_sync(func, *args, **kwargs):
    """在线程池中运行同步 akshare 调用"""
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(None, lambda: func(*args, **kwargs))


class AKShareProvider(DataProvider):
    """
    AKShare 数据源 - 仅支持中国 A 股 ETF 期权
    对美股标的 (AAPL/SPY 等) 直接抛出 DataProviderError，由 DataSourceManager 切换其他源
    """

    def __init__(self):
        super().__init__("AKShare", priority=50)  # 低于 Yahoo/MarketData，高于 Alpha Vantage

    def _ensure_akshare(self):
        try:
            import akshare as ak  # noqa: F401
        except ImportError:
            raise DataProviderError("akshare 未安装，请执行: pip install akshare")

    async def get_stock_info(self, symbol: str) -> Optional[StockInfo]:
        self._request_count += 1

        if not _is_china_symbol(symbol):
            raise DataProviderError(
                f"AKShare 仅支持中国市场期权，不支持 {symbol}（请使用 Yahoo/MarketData 等美股源）"
            )

        akshare_symbol = _resolve_akshare_symbol(symbol)
        if not akshare_symbol:
            raise DataProviderError(f"AKShare 暂不支持标的 {symbol}，支持: {list(SYMBOL_TO_AKSHARE.keys())}")

        self._ensure_akshare()
        import akshare as ak

        try:
            df = await _run_sync(ak.option_finance_sse_underlying, symbol=akshare_symbol)
        except Exception as e:
            self._error_count += 1
            raise DataProviderError(f"AKShare 标的行情获取失败: {e}")

        if df is None or df.empty:
            raise DataProviderError(f"AKShare 未返回 {symbol} 标的行情")

        # 取第一行，字段名可能是中文
        row = df.iloc[0]
        price = float(row.get("收盘价", row.get("当前价", 0)))
        if price <= 0:
            for c in ["收盘价", "当前价", "最新价"]:
                if c in row and row[c] is not None:
                    try:
                        price = float(row[c])
                        break
                    except (TypeError, ValueError):
                        pass

        return StockInfo(
            symbol=symbol,
            current_price=price,
            company_name=akshare_symbol,
            timestamp=datetime.now(),
        )

    async def get_expiration_dates(self, symbol: str) -> Optional[List[str]]:
        self._request_count += 1

        if not _is_china_symbol(symbol):
            raise DataProviderError(f"AKShare 仅支持中国市场期权，不支持 {symbol}")

        akshare_symbol = _resolve_akshare_symbol(symbol)
        if not akshare_symbol:
            raise DataProviderError(f"AKShare 暂不支持标的 {symbol}")

        self._ensure_akshare()
        import akshare as ak

        # 遍历未来 8 个月，检查哪些月份有数据
        now = datetime.now()
        result: List[str] = []
        for i in range(8):
            m = now.month + i
            if m > 12:
                y = now.year + (m - 1) // 12
                m = ((m - 1) % 12) + 1
            else:
                y = now.year
            yymm = f"{y % 100:02d}{m:02d}"

            try:
                df = await _run_sync(ak.option_finance_board, symbol=akshare_symbol, end_month=yymm)
                if df is not None and not df.empty:
                    exp_str = _yymm_to_expiration(yymm)
                    if exp_str not in result:
                        result.append(exp_str)
            except Exception:
                continue

        if not result:
            raise DataProviderError(f"AKShare 未获取到 {symbol} 的到期月份")

        return sorted(result)

    async def get_option_chain(
        self,
        symbol: str,
        expiration_date: str,
    ) -> Optional[OptionChain]:
        self._request_count += 1

        if not _is_china_symbol(symbol):
            raise DataProviderError(f"AKShare 仅支持中国市场期权，不支持 {symbol}")

        akshare_symbol = _resolve_akshare_symbol(symbol)
        if not akshare_symbol:
            raise DataProviderError(f"AKShare 暂不支持标的 {symbol}")

        self._ensure_akshare()
        import akshare as ak

        end_month = _exp_to_yymm(expiration_date)

        try:
            df = await _run_sync(ak.option_finance_board, symbol=akshare_symbol, end_month=end_month)
        except Exception as e:
            self._error_count += 1
            raise DataProviderError(f"AKShare 期权链获取失败: {e}")

        if df is None or df.empty:
            raise DataProviderError(f"AKShare 未返回 {symbol} {expiration_date} 期权链")

        # 兼容不同列名：合约交易代码/合约编码, 当前价/lastprice, 行权价, 数量/volume
        code_col = "合约交易代码" if "合约交易代码" in df.columns else "instrument"
        price_col = "当前价" if "当前价" in df.columns else "lastprice"
        strike_col = "行权价" if "行权价" in df.columns else None
        qty_col = "数量" if "数量" in df.columns else ("volume" if "volume" in df.columns else "position")

        # 深交所嘉实沪深300返回格式不同(无当前价)，跳过
        if price_col not in df.columns and "lastprice" not in df.columns:
            raise DataProviderError(f"AKShare 该品种返回格式不支持（深交所部分品种无行情）")

        if strike_col and strike_col not in df.columns:
            strike_col = None

        # 获取标的价
        try:
            und_df = await _run_sync(ak.option_finance_sse_underlying, symbol=akshare_symbol)
            underlying_price = float(und_df.iloc[0].get("收盘价", und_df.iloc[0].get("当前价", 0)))
        except Exception:
            underlying_price = 0.0

        expiry_dt = datetime.strptime(expiration_date, "%Y-%m-%d")
        dte = max(0, (expiry_dt - datetime.now()).days)
        T_years = dte / 365.0 if dte > 0 else 1.0 / 365.0
        r = 0.025
        q = 0.0

        calls: List[OptionContract] = []
        puts: List[OptionContract] = []

        for _, row in df.iterrows():
            code = str(row.get(code_col, ""))
            if not code:
                continue

            is_call = "C" in code.upper() or "购" in str(row.get("类型", ""))
            price_val = row.get(price_col, row.get("lastprice", 0))
            try:
                last_price = float(price_val) if price_val is not None else 0.0
            except (TypeError, ValueError):
                last_price = 0.0

            if strike_col:
                strike = float(row.get(strike_col, 0))
            else:
                # 从 instrument 解析，如 IO2306-C-3100
                m = re.search(r"[-](\d+(?:\.\d+)?)$", code)
                strike = float(m.group(1)) if m else 0.0

            try:
                oi = int(row.get(qty_col, 0) or 0)
            except (TypeError, ValueError):
                oi = 0

            iv = 0.0
            if GreeksCalculator and last_price > 0 and underlying_price > 0 and strike > 0 and T_years > 0:
                opt_type = "call" if is_call else "put"
                iv_computed = GreeksCalculator.implied_volatility_from_price(
                    underlying_price, strike, T_years, r, q, last_price, opt_type
                )
                if iv_computed is not None and iv_computed > 0:
                    iv = iv_computed

            oc = OptionContract(
                strike=strike,
                last_price=last_price,
                bid=last_price,
                ask=last_price,
                volume=0,
                open_interest=oi,
                implied_volatility=iv,
                option_type="call" if is_call else "put",
                contract_symbol=code,
                in_the_money=False,
                expiration_date=expiration_date,
            )
            if is_call:
                calls.append(oc)
            else:
                puts.append(oc)

        expiry_dt = datetime.strptime(expiration_date, "%Y-%m-%d")
        dte = max(0, (expiry_dt - datetime.now()).days)

        return OptionChain(
            symbol=symbol,
            expiration_date=expiration_date,
            underlying_price=underlying_price if underlying_price > 0 else 0.0,
            days_to_expiration=dte,
            calls=calls,
            puts=puts,
            timestamp=datetime.now(),
        )

    async def get_risk_free_rate(self) -> float:
        """中国无风险利率近似 (如未单独接口则用默认)"""
        return 0.025  # 约 2.5% 近似
