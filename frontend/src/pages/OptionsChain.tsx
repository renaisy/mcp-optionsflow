/**
 * Options Chain page - T-shaped options display
 * Calls (left) | Strike (center) | Puts (right)
 * 查询历史 + 关注列表
 */
import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Search, Loader2, History, Star, X } from 'lucide-react';
import { optionsAPI } from '../services/api';
import type { OptionChain, OptionData, StockInfo, ExpirationDates } from '../types/option';

/** 按 strike 合并 calls 与 puts，用于 T 形报价 */
function mergeByStrike(calls: OptionData[] = [], puts: OptionData[] = []): Array<{ strike: number; call?: OptionData; put?: OptionData }> {
  const callMap = new Map<number, OptionData>();
  calls.forEach((c) => callMap.set(c.strike, c));
  const putMap = new Map<number, OptionData>();
  puts.forEach((p) => putMap.set(p.strike, p));
  const strikes = new Set([...callMap.keys(), ...putMap.keys()]);
  return Array.from(strikes)
    .sort((a, b) => a - b)
    .map((strike) => ({
      strike,
      call: callMap.get(strike),
      put: putMap.get(strike),
    }));
}

const Cell: React.FC<{ value: string | number; align?: 'left' | 'right'; className?: string }> = ({
  value,
  align = 'right',
  className = '',
}) => (
  <td className={`px-1.5 py-2 text-sm tabular-nums ${align === 'left' ? 'text-left' : 'text-right'} ${className}`}>
    {value}
  </td>
);

const formatPrice = (v: number | undefined): string => (v != null ? v.toFixed(2) : '—');
const formatPct = (v: number | undefined): string => (v != null ? (v * 100).toFixed(1) + '%' : '—');
const formatNum = (v: number | undefined): string => (v != null ? String(v) : '—');

const STORAGE_KEY_HISTORY = 'options-chain-query-history';
const STORAGE_KEY_WATCHLIST = 'optionsflow-watchlist';  // 全站通用
const MAX_HISTORY = 12;

function loadHistory(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_HISTORY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr.slice(0, MAX_HISTORY) : [];
  } catch {
    return [];
  }
}

function loadWatchlist(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_WATCHLIST);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

export const OptionsChain: React.FC = () => {
  const { t } = useTranslation();
  const [symbol, setSymbol] = useState('');
  const [stockInfo, setStockInfo] = useState<StockInfo | null>(null);
  const [queryHistory, setQueryHistory] = useState<string[]>(loadHistory);
  const [watchlist, setWatchlist] = useState<string[]>(loadWatchlist);
  const [expirations, setExpirations] = useState<string[]>([]);
  const [selectedExpiration, setSelectedExpiration] = useState('');
  const [chainData, setChainData] = useState<OptionChain | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const addToHistory = useCallback((s: string) => {
    const normalized = s.trim().toUpperCase();
    if (!normalized) return;
    setQueryHistory((prev) => {
      const next = [normalized, ...prev.filter((x) => x !== normalized)].slice(0, MAX_HISTORY);
      localStorage.setItem(STORAGE_KEY_HISTORY, JSON.stringify(next));
      return next;
    });
  }, []);

  const addToWatchlist = useCallback((s: string) => {
    const normalized = s.trim().toUpperCase();
    if (!normalized || watchlist.includes(normalized)) return;
    const next = [...watchlist, normalized];
    setWatchlist(next);
    localStorage.setItem(STORAGE_KEY_WATCHLIST, JSON.stringify(next));
  }, [watchlist]);

  const removeFromWatchlist = useCallback((s: string) => {
    const next = watchlist.filter((x) => x !== s);
    setWatchlist(next);
    localStorage.setItem(STORAGE_KEY_WATCHLIST, JSON.stringify(next));
  }, [watchlist]);

  const quickSearch = useCallback(async (s: string) => {
    const sym = s.trim().toUpperCase();
    if (!sym) return;
    setSymbol(sym);
    setError('');
    setLoading(true);
    try {
      const [stockRes, expRes] = await Promise.all([
        optionsAPI.getStockInfo(sym),
        optionsAPI.getExpirationDates(sym),
      ]);
      const stock = stockRes.data as StockInfo;
      const expData = expRes.data as ExpirationDates;
      setStockInfo(stock);
      const dates = expData.expiration_dates || [];
      if (dates.length) {
        const firstExp = dates[0];
        const chainRes = await optionsAPI.getOptionChainWithGreeks(sym, firstExp);
        setChainData(chainRes.data as OptionChain);
        setExpirations(dates);
        setSelectedExpiration(firstExp);
        addToHistory(sym);
      } else {
        setExpirations([]);
        setSelectedExpiration('');
        setChainData(null);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to fetch';
      setError(String(msg));
      setStockInfo(null);
      setExpirations([]);
      setChainData(null);
    } finally {
      setLoading(false);
    }
  }, [addToHistory]);

  const handleSearch = useCallback(async () => {
    if (!symbol.trim()) return;
    setError('');
    setLoading(true);
    try {
      const s = symbol.trim().toUpperCase();
      const [stockRes, expRes] = await Promise.all([
        optionsAPI.getStockInfo(s),
        optionsAPI.getExpirationDates(s),
      ]);
      const stock = stockRes.data as StockInfo;
      const expData = expRes.data as ExpirationDates;
      setStockInfo(stock);
      const dates = expData.expiration_dates || [];
      setExpirations(dates);
      if (dates.length) {
        const firstExp = dates[0];
        setSelectedExpiration(firstExp);
        const chainRes = await optionsAPI.getOptionChainWithGreeks(s, firstExp);
        setChainData(chainRes.data as OptionChain);
        addToHistory(s);
      } else {
        setSelectedExpiration('');
        setChainData(null);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to fetch data';
      setError(String(msg));
      setStockInfo(null);
      setExpirations([]);
      setChainData(null);
    } finally {
      setLoading(false);
    }
  }, [symbol, addToHistory]);

  const handleExpirationChange = useCallback(async (exp: string) => {
    setSelectedExpiration(exp);
    if (!symbol.trim()) return;
    setLoading(true);
    setError('');
    try {
      const res = await optionsAPI.getOptionChainWithGreeks(symbol.trim().toUpperCase(), exp);
      setChainData(res.data as OptionChain);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to fetch chain';
      setError(String(msg));
      setChainData(null);
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  const rows = useMemo(() => {
    if (!chainData) return [];
    return mergeByStrike(chainData.calls, chainData.puts);
  }, [chainData]);

  const underlyingPrice = chainData?.underlying_price;
  const atmRowIndex = useMemo(() => {
    if (!underlyingPrice || rows.length === 0) return 0;
    let best = 0;
    let bestDiff = Math.abs(rows[0].strike - underlyingPrice);
    rows.forEach((r, i) => {
      const d = Math.abs(r.strike - underlyingPrice);
      if (d < bestDiff) {
        bestDiff = d;
        best = i;
      }
    });
    return best;
  }, [rows, underlyingPrice]);

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const atmRowRef = useRef<HTMLTableRowElement>(null);
  useEffect(() => {
    if (!chainData || !atmRowRef.current) return;
    const t = setTimeout(() => {
      atmRowRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }, 50);
    return () => clearTimeout(t);
  }, [chainData]);

  const isChinaSymbol = useMemo(() => {
    const s = symbol.trim();
    return /^\d{6}$/.test(s) || /[\u4e00-\u9fff]/.test(s);
  }, [symbol]);
  const pricePrefix = isChinaSymbol ? '' : '$';

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="glass-card p-6">
        <h1 className="text-2xl font-bold text-text mb-4">{t('optionsChain.title')}</h1>
        <div className="flex flex-wrap gap-4 items-end">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm text-text-secondary mb-1">Stock Symbol</label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
              <input
                type="text"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="e.g. AAPL, 510050"
                className="input-field pl-10"
              />
            </div>
          </div>
          <button onClick={handleSearch} disabled={loading} className="btn-primary flex items-center gap-2">
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
            Search
          </button>
          {stockInfo && symbol.trim() && !watchlist.includes(symbol.trim().toUpperCase()) && (
            <button
              type="button"
              onClick={() => addToWatchlist(symbol.trim().toUpperCase())}
              className="btn-secondary flex items-center gap-2"
              title="添加到关注列表"
            >
              <Star className="w-5 h-5" />
              关注
            </button>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4 pt-4 border-t border-white/10">
          <div>
            <div className="flex items-center gap-2 text-text-secondary text-sm mb-2">
              <History className="w-4 h-4" />
              <span>查询历史</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {queryHistory.length === 0 ? (
                <span className="text-text-muted text-sm">暂无记录</span>
              ) : (
                queryHistory.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => quickSearch(s)}
                    disabled={loading}
                    className="px-3 py-1.5 rounded-lg bg-background-light border border-white/10 text-sm
                      hover:bg-primary/10 hover:border-primary/30 transition-colors disabled:opacity-50"
                  >
                    {s}
                  </button>
                ))
              )}
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2 text-text-secondary text-sm mb-2">
              <Star className="w-4 h-4" />
              <span>关注列表</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {watchlist.length === 0 ? (
                <span className="text-text-muted text-sm">点击「关注」添加</span>
              ) : (
                watchlist.map((s) => (
                  <span
                    key={s}
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-primary/10 border border-primary/20 text-sm"
                  >
                    <button
                      type="button"
                      onClick={() => quickSearch(s)}
                      disabled={loading}
                      className="hover:text-primary font-medium disabled:opacity-50"
                    >
                      {s}
                    </button>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); removeFromWatchlist(s); }}
                      className="p-0.5 rounded hover:bg-functional-danger/20 text-text-muted hover:text-functional-danger"
                      title="移除"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </span>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="glass-card p-4 border-functional-danger/30">
          <p className="text-functional-danger">{error}</p>
        </div>
      )}

      {stockInfo && expirations.length > 0 && (
        <div className="glass-card p-6">
          <div className="flex flex-wrap gap-8 items-end">
            <div className="flex flex-col gap-1.5">
              <span className="text-text-muted text-sm">Current Price</span>
              <span className="text-2xl font-bold text-primary tabular-nums h-10 flex items-center">
                {pricePrefix}{stockInfo.currentPrice?.toFixed(2) ?? '—'}
              </span>
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="text-text-muted text-sm">Expiration</span>
              <select
                value={selectedExpiration}
                onChange={(e) => handleExpirationChange(e.target.value)}
                className="input-field w-44 h-10 py-2"
              >
                {expirations.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}

      {chainData && (
        <div className="glass-card overflow-hidden">
          <h2 className="text-lg font-semibold text-text p-4 border-b border-white/10">
            T-Shaped Options Chain — {chainData.expiration_date}
          </h2>
          <div ref={scrollContainerRef} className="overflow-x-auto max-h-[600px] overflow-y-auto">
            <table className="w-full border-collapse text-sm">
              <colgroup>
                <col className="w-[8.5%]" /><col className="w-[8.5%]" /><col className="w-[8.5%]" />
                <col className="w-[7%]" /><col className="w-[7%]" /><col className="w-[7%]" />
                <col className="w-[7%]" />
                <col className="w-[7%]" /><col className="w-[7%]" /><col className="w-[7%]" />
                <col className="w-[8.5%]" /><col className="w-[8.5%]" /><col className="w-[8.5%]" />
              </colgroup>
              <thead className="sticky top-0 z-10 bg-background-light/95 backdrop-blur border-b border-white/10">
                <tr>
                  <th colSpan={6} className="px-1 py-3 text-center text-functional-success font-medium border-r border-white/10">
                    CALLS
                  </th>
                  <th className="px-1 py-3 text-center font-semibold text-primary bg-primary/10 min-w-0">
                    STRIKE
                  </th>
                  <th colSpan={6} className="px-1 py-3 text-center text-functional-danger font-medium border-l border-white/10">
                    PUTS
                  </th>
                </tr>
                <tr className="text-text-muted text-xs">
                  <th className="px-1 py-2 text-right font-medium">Bid</th>
                  <th className="px-1 py-2 text-right font-medium">Ask</th>
                  <th className="px-1 py-2 text-right font-medium">Last</th>
                  <th className="px-1 py-2 text-right font-medium">Vol</th>
                  <th className="px-1 py-2 text-right font-medium">OI</th>
                  <th className="px-1 py-2 text-right font-medium">IV</th>
                  <th></th>
                  <th className="px-1 py-2 text-left font-medium">IV</th>
                  <th className="px-1 py-2 text-left font-medium">OI</th>
                  <th className="px-1 py-2 text-left font-medium">Vol</th>
                  <th className="px-1 py-2 text-left font-medium">Last</th>
                  <th className="px-1 py-2 text-left font-medium">Ask</th>
                  <th className="px-1 py-2 text-left font-medium">Bid</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(({ strike, call, put }, idx) => (
                  <tr
                    key={strike}
                    ref={idx === atmRowIndex ? atmRowRef : undefined}
                    className={`border-b border-white/5 hover:bg-white/5 transition-colors ${idx === atmRowIndex ? 'bg-primary/15' : ''}`}
                  >
                    {/* Call cells - right align */}
                    <Cell value={formatPrice(call?.bid)} />
                    <Cell value={formatPrice(call?.ask)} />
                    <Cell value={formatPrice(call?.lastPrice ?? call?.bid)} className={call?.inTheMoney ? 'text-functional-success/90' : ''} />
                    <Cell value={formatNum(call?.volume)} />
                    <Cell value={formatNum(call?.openInterest)} />
                    <Cell value={formatPct(call?.impliedVolatility)} />
                    {/* Strike - center, compact */}
                    <td className="px-1 py-2 text-center text-xs font-semibold text-primary bg-primary/5 border-x border-white/10">
                      {pricePrefix}{strike}
                    </td>
                    {/* Put cells - left align (mirror layout) */}
                    <Cell value={formatPct(put?.impliedVolatility)} align="left" />
                    <Cell value={formatNum(put?.openInterest)} align="left" />
                    <Cell value={formatNum(put?.volume)} align="left" />
                    <Cell value={formatPrice(put?.lastPrice ?? put?.ask)} align="left" className={put?.inTheMoney ? 'text-functional-danger/90' : ''} />
                    <Cell value={formatPrice(put?.ask)} align="left" />
                    <Cell value={formatPrice(put?.bid)} align="left" />
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-4 py-2 text-xs text-text-muted border-t border-white/10">
            Last = Last traded price; OI = Open Interest; IV = Implied Volatility. ITM rows highlighted.
          </div>
        </div>
      )}

      {!chainData && !loading && stockInfo && expirations.length > 0 && (
        <div className="glass-card p-8 text-center text-text-muted">
          Select an expiration date to load the option chain.
        </div>
      )}
    </div>
  );
};
