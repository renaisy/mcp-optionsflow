/**
 * Greeks Visualizer - Visualize Delta, IV vs Strike
 */
import React, { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Search, Loader2, History, Star, X } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { optionsAPI } from '../services/api';
import type { OptionChain, OptionData } from '../types/option';

const STORAGE_KEY_HISTORY = 'greeks-visualizer-query-history';
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

export const GreeksVisualizer: React.FC = () => {
  const { t } = useTranslation();
  const [symbol, setSymbol] = useState('');
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
      const expRes = await optionsAPI.getExpirationDates(sym);
      const dates = (expRes.data as { expiration_dates?: string[] })?.expiration_dates || [];
      if (dates.length) {
        setExpirations(dates);
        setSelectedExpiration(dates[0]);
        const chainRes = await optionsAPI.getOptionChainWithGreeks(sym, dates[0]);
        setChainData(chainRes.data as OptionChain);
        addToHistory(sym);
      } else {
        setExpirations([]);
        setSelectedExpiration('');
        setChainData(null);
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to fetch';
      setError(String(msg));
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
      const expRes = await optionsAPI.getExpirationDates(s);
      const dates = (expRes.data as { expiration_dates?: string[] })?.expiration_dates || [];
      setExpirations(dates);
      if (dates.length) {
        setSelectedExpiration(dates[0]);
        const chainRes = await optionsAPI.getOptionChainWithGreeks(s, dates[0]);
        setChainData(chainRes.data as OptionChain);
        addToHistory(s);
      } else {
        setSelectedExpiration('');
        setChainData(null);
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to fetch';
      setError(String(msg));
      setChainData(null);
    } finally {
      setLoading(false);
    }
  }, [symbol, addToHistory]);

  const handleExpirationChange = useCallback(async (exp: string) => {
    setSelectedExpiration(exp);
    if (!symbol.trim()) return;
    setLoading(true);
    try {
      const res = await optionsAPI.getOptionChainWithGreeks(symbol.trim().toUpperCase(), exp);
      setChainData(res.data as OptionChain);
    } catch {
      setChainData(null);
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  const chartDataCalls = React.useMemo(() => {
    if (!chainData?.calls?.length) return [];
    return chainData.calls
      .filter((o: OptionData) => o.delta != null && o.impliedVolatility != null)
      .map((o: OptionData) => ({
        strike: o.strike,
        delta: o.delta,
        iv: (o.impliedVolatility ?? 0) * 100,
      }));
  }, [chainData]);

  const chartDataPuts = React.useMemo(() => {
    if (!chainData?.puts?.length) return [];
    return chainData.puts
      .filter((o: OptionData) => o.delta != null && o.impliedVolatility != null)
      .map((o: OptionData) => ({
        strike: o.strike,
        delta: o.delta,
        iv: (o.impliedVolatility ?? 0) * 100,
      }));
  }, [chainData]);

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="glass-card p-6">
        <h1 className="text-2xl font-bold text-text mb-4">{t('greeksVisualizer.title')}</h1>
        <div className="flex flex-wrap gap-4 items-end">
          <div className="flex-1 min-w-[180px]">
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
          <div>
            <label className="block text-sm text-text-secondary mb-1">Expiration</label>
            <select
              value={selectedExpiration}
              onChange={(e) => handleExpirationChange(e.target.value)}
              className="input-field w-40"
              disabled={!expirations.length}
            >
              {expirations.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>
          <button onClick={handleSearch} disabled={loading} className="btn-primary flex items-center gap-2">
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
            Load
          </button>
          {symbol.trim() && !watchlist.includes(symbol.trim().toUpperCase()) && (
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

      {chainData && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold text-text mb-4">Calls - Delta vs Strike</h2>
            <div className="h-64">
              {chartDataCalls.length ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartDataCalls}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                    <XAxis dataKey="strike" stroke="#94A3B8" />
                    <YAxis stroke="#94A3B8" />
                    <Tooltip contentStyle={{ background: '#1E293B', border: '1px solid rgba(255,255,255,0.1)' }} />
                    <Legend />
                    <Line type="monotone" dataKey="delta" stroke="#00D4FF" name="Delta" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-text-muted text-center py-12">No data with Greeks</p>
              )}
            </div>
          </div>

          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold text-text mb-4">Calls - IV vs Strike</h2>
            <div className="h-64">
              {chartDataCalls.length ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartDataCalls}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                    <XAxis dataKey="strike" stroke="#94A3B8" />
                    <YAxis stroke="#94A3B8" />
                    <Tooltip contentStyle={{ background: '#1E293B', border: '1px solid rgba(255,255,255,0.1)' }} />
                    <Legend />
                    <Line type="monotone" dataKey="iv" stroke="#10B981" name="IV (%)" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-text-muted text-center py-12">No data with Greeks</p>
              )}
            </div>
          </div>

          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold text-text mb-4">Puts - Delta vs Strike</h2>
            <div className="h-64">
              {chartDataPuts.length ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartDataPuts}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                    <XAxis dataKey="strike" stroke="#94A3B8" />
                    <YAxis stroke="#94A3B8" />
                    <Tooltip contentStyle={{ background: '#1E293B', border: '1px solid rgba(255,255,255,0.1)' }} />
                    <Legend />
                    <Line type="monotone" dataKey="delta" stroke="#F59E0B" name="Delta" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-text-muted text-center py-12">No data with Greeks</p>
              )}
            </div>
          </div>

          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold text-text mb-4">Puts - IV vs Strike</h2>
            <div className="h-64">
              {chartDataPuts.length ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartDataPuts}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                    <XAxis dataKey="strike" stroke="#94A3B8" />
                    <YAxis stroke="#94A3B8" />
                    <Tooltip contentStyle={{ background: '#1E293B', border: '1px solid rgba(255,255,255,0.1)' }} />
                    <Legend />
                    <Line type="monotone" dataKey="iv" stroke="#8B5CF6" name="IV (%)" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-text-muted text-center py-12">No data with Greeks</p>
              )}
            </div>
          </div>
        </div>
      )}

      {!chainData && !loading && (
        <div className="glass-card p-8 text-center text-text-muted">
          Enter a symbol and click Load to visualize Greeks.
        </div>
      )}
    </div>
  );
};
