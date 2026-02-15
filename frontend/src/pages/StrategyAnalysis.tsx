/**
 * Strategy Analysis page - Analyze, P&L Scenarios, Find Best, Compare
 */
import React, { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Calculator, Loader2, TrendingUp, BarChart3, GitCompare, History, Star, X, HelpCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { optionsAPI, strategiesAPI } from '../services/api';
import type { StrategyAnalysisResult } from '../types/strategy';
import { StrategyResultCard, PnlScenarioCard, FindBestCard, CompareResultsCard } from '../components/strategy/StrategyCards';

const STRATEGY_KEYS: Record<string, string> = {
  ccs: 'strategyAnalysis.strategyCcs',
  pcs: 'strategyAnalysis.strategyPcs',
  csp: 'strategyAnalysis.strategyCsp',
  cc: 'strategyAnalysis.strategyCc',
};
const STRATEGY_BRIEF_KEYS: Record<string, string> = {
  ccs: 'strategyAnalysis.strategyBriefCcs',
  pcs: 'strategyAnalysis.strategyBriefPcs',
  csp: 'strategyAnalysis.strategyBriefCsp',
  cc: 'strategyAnalysis.strategyBriefCc',
};

const STORAGE_KEY_HISTORY = 'strategy-analysis-query-history';
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

type TabId = 'analyze' | 'pnl' | 'find-best' | 'compare';

export const StrategyAnalysis: React.FC = () => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<TabId>('analyze');
  const [symbol, setSymbol] = useState('');
  const [strategyType, setStrategyType] = useState<'ccs' | 'pcs' | 'csp' | 'cc'>('pcs');
  const [expirations, setExpirations] = useState<string[]>([]);
  const [selectedExpiration, setSelectedExpiration] = useState('');
  const [saveResult, setSaveResult] = useState(true);
  const [queryHistory, setQueryHistory] = useState<string[]>(loadHistory);
  const [watchlist, setWatchlist] = useState<string[]>(loadWatchlist);
  const [result, setResult] = useState<StrategyAnalysisResult | null>(null);
  const [pnlData, setPnlData] = useState<Record<string, unknown> | null>(null);
  const [findBestData, setFindBestData] = useState<Record<string, unknown> | null>(null);
  const [compareResults, setCompareResults] = useState<StrategyAnalysisResult[] | null>(null);
  const [compareStrategies, setCompareStrategies] = useState<Array<'ccs' | 'pcs' | 'csp' | 'cc'>>(['pcs', 'ccs']);
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

  const loadExpirations = useCallback(async (sym: string) => {
    try {
      const res = await optionsAPI.getExpirationDates(sym.trim().toUpperCase());
      const dates = (res.data as { expiration_dates?: string[] })?.expiration_dates || [];
      setExpirations(dates);
      setSelectedExpiration(dates[0] || '');
    } catch {
      setExpirations([]);
      setSelectedExpiration('');
    }
  }, []);

  const quickSearch = useCallback((s: string) => {
    const sym = s.trim().toUpperCase();
    if (!sym) return;
    setSymbol(sym);
    setError('');
    loadExpirations(sym);
  }, [loadExpirations]);

  const handleSymbolBlur = useCallback(() => {
    if (symbol.trim()) loadExpirations(symbol);
  }, [symbol, loadExpirations]);

  const clearError = useCallback(() => setError(''), []);

  const handleAnalyze = useCallback(async () => {
    if (!symbol.trim()) {
      setError(t('strategyAnalysis.errEnterSymbol'));
      return;
    }
    setError('');
    setLoading(true);
    setResult(null);
    try {
      const res = await strategiesAPI.analyzeStrategy({
        symbol: symbol.trim().toUpperCase(),
        strategy_type: strategyType,
        expiration_date: selectedExpiration || undefined,
        save_result: saveResult,
      });
      setResult(res.data as StrategyAnalysisResult);
      addToHistory(symbol.trim().toUpperCase());
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Analysis failed';
      setError(String(msg));
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [symbol, strategyType, selectedExpiration, saveResult, addToHistory]);

  const handlePnlScenarios = useCallback(async () => {
    if (!symbol.trim() || !selectedExpiration) {
      setError(t('strategyAnalysis.errEnterSymbolExpiration'));
      return;
    }
    setError('');
    setLoading(true);
    setPnlData(null);
    try {
      const res = await strategiesAPI.analyzePnlScenarios({
        symbol: symbol.trim().toUpperCase(),
        strategy: strategyType,
        expiration_date: selectedExpiration,
        price_range_pct: 0.20,
        steps: 25,
      });
      setPnlData(res.data as Record<string, unknown>);
      addToHistory(symbol.trim().toUpperCase());
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'P&L analysis failed';
      setError(String(msg));
      setPnlData(null);
    } finally {
      setLoading(false);
    }
  }, [symbol, strategyType, selectedExpiration, addToHistory]);

  const handleFindBest = useCallback(async () => {
    if (!symbol.trim()) {
      setError(t('strategyAnalysis.errEnterSymbol'));
      return;
    }
    setError('');
    setLoading(true);
    setFindBestData(null);
    try {
      const res = await strategiesAPI.findBestStrategies({
        symbol: symbol.trim().toUpperCase(),
        expiration_date: selectedExpiration || undefined,
        min_probability_profit: 0.55,
        max_risk_reward_ratio: 3.5,
        strategy_preference: 'any',
      });
      setFindBestData(res.data as Record<string, unknown>);
      addToHistory(symbol.trim().toUpperCase());
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Find best failed';
      setError(String(msg));
      setFindBestData(null);
    } finally {
      setLoading(false);
    }
  }, [symbol, selectedExpiration, addToHistory]);

  const handleCompare = useCallback(async () => {
    if (!symbol.trim()) {
      setError(t('strategyAnalysis.errEnterSymbol'));
      return;
    }
    setError('');
    setLoading(true);
    setCompareResults(null);
    try {
      const res = await strategiesAPI.compareStrategies({
        symbol: symbol.trim().toUpperCase(),
        strategies: compareStrategies.map((s) => ({
          strategy_type: s,
          expiration_date: selectedExpiration || undefined,
        })),
        save_results: false,
      });
      const data = res.data as { strategies?: StrategyAnalysisResult[] };
      setCompareResults(data.strategies || []);
      addToHistory(symbol.trim().toUpperCase());
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Compare failed';
      setError(String(msg));
      setCompareResults(null);
    } finally {
      setLoading(false);
    }
  }, [symbol, selectedExpiration, compareStrategies, addToHistory]);

  const tabs: { id: TabId; labelKey: string; icon: React.ReactNode }[] = [
    { id: 'analyze', labelKey: 'strategyAnalysis.analyze', icon: <Calculator className="w-4 h-4" /> },
    { id: 'pnl', labelKey: 'strategyAnalysis.pnlScenarios', icon: <BarChart3 className="w-4 h-4" /> },
    { id: 'find-best', labelKey: 'strategyAnalysis.findBest', icon: <TrendingUp className="w-4 h-4" /> },
    { id: 'compare', labelKey: 'strategyAnalysis.compare', icon: <GitCompare className="w-4 h-4" /> },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="glass-card overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-4 border-b border-white/10">
          <h1 className="text-2xl font-bold text-text">{t('strategyAnalysis.title')}</h1>
          <Link
            to="/history"
            className="flex items-center gap-2 text-text-secondary hover:text-primary text-sm transition-colors"
          >
            <History className="w-4 h-4" />
            {t('strategyAnalysis.viewHistory')}
          </Link>
        </div>

        <div className="flex border-b border-white/10 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => { setActiveTab(tab.id); clearError(); }}
              className={`flex items-center gap-2 px-6 py-3 text-sm font-medium transition-colors
                ${activeTab === tab.id ? 'text-primary border-b-2 border-primary bg-primary/5' : 'text-text-muted hover:text-text'}`}
            >
              {tab.icon}
              {t(tab.labelKey)}
            </button>
          ))}
        </div>

        <div className="p-6">
          {/* Shared form */}
          <div className="flex flex-wrap items-end gap-x-4 gap-y-3 mb-6">
            <div className="flex flex-col gap-1 min-w-[140px]">
              <label className="text-sm text-text-secondary leading-5">{t('strategyAnalysis.symbol')}</label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                  onBlur={handleSymbolBlur}
                  onKeyDown={(e) => {
                    if (e.key !== 'Enter') return;
                    if (activeTab === 'analyze') handleAnalyze();
                    else if (activeTab === 'pnl') handlePnlScenarios();
                    else if (activeTab === 'find-best') handleFindBest();
                    else if (activeTab === 'compare') handleCompare();
                  }}
                  placeholder={t('strategyAnalysis.symbolPlaceholder')}
                  className="input-field h-10 min-w-[120px]"
                />
                {symbol.trim() && !watchlist.includes(symbol.trim().toUpperCase()) && (
                  <button
                    type="button"
                    onClick={() => addToWatchlist(symbol.trim().toUpperCase())}
                    className="btn-secondary flex items-center gap-2 shrink-0 h-10 px-4"
                    title={t('strategyAnalysis.addToWatchlist')}
                  >
                    <Star className="w-5 h-5" />
                    {t('strategyAnalysis.addToWatchlist')}
                  </button>
                )}
              </div>
            </div>
            {activeTab !== 'find-best' && (
              <div className="flex flex-col gap-1 min-w-[140px]">
                <label className="text-sm text-text-secondary leading-5 flex items-center gap-1.5 cursor-help group relative">
                  {t('strategyAnalysis.strategy')}
                  <HelpCircle className="w-3.5 h-3.5 text-text-muted shrink-0" />
                  <span className="absolute left-0 bottom-full mb-1.5 z-50 px-3 py-2 w-72 text-xs text-text bg-background-light border border-white/20 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-opacity duration-200 pointer-events-none">
                    {t(STRATEGY_BRIEF_KEYS[strategyType])}
                  </span>
                </label>
                <select
                  value={strategyType}
                  onChange={(e) => setStrategyType(e.target.value as 'ccs' | 'pcs' | 'csp' | 'cc')}
                  className="input-field h-10"
                >
                  {(['ccs', 'pcs', 'csp', 'cc'] as const).map((s) => (
                    <option key={s} value={s}>{t(STRATEGY_KEYS[s])}</option>
                  ))}
                </select>
              </div>
            )}
            <div className="flex flex-col gap-1 min-w-[120px]">
              <label className="text-sm text-text-secondary leading-5">{t('strategyAnalysis.expiration')}</label>
              <select
                value={selectedExpiration}
                onChange={(e) => setSelectedExpiration(e.target.value)}
                className="input-field h-10"
              >
                {expirations.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>
            {activeTab === 'compare' && (
              <div className="flex flex-col gap-1 min-w-[100px]">
                <label className="text-sm text-text-secondary leading-5">{t('strategyAnalysis.compareLabel')}</label>
                <select
                  value={compareStrategies.join(',')}
                  onChange={(e) => setCompareStrategies(e.target.value.split(',') as Array<'ccs' | 'pcs' | 'csp' | 'cc'>)}
                  className="input-field h-10"
                >
                  <option value="pcs,ccs">{t('strategyAnalysis.comparePcsCcs')}</option>
                  <option value="pcs,csp">{t('strategyAnalysis.comparePcsCsp')}</option>
                  <option value="cc,csp">{t('strategyAnalysis.compareCcCsp')}</option>
                </select>
              </div>
            )}
            {activeTab === 'analyze' && (
              <div className="flex flex-col gap-1 min-w-0">
                <label className="text-sm text-text-secondary leading-5 invisible">Save</label>
                <label className="flex items-center gap-2 cursor-pointer h-10">
                  <input
                    type="checkbox"
                    checked={saveResult}
                    onChange={(e) => setSaveResult(e.target.checked)}
                    className="rounded border-white/20"
                  />
                  <span className="text-sm text-text-secondary">{t('strategyAnalysis.saveToHistory')}</span>
                </label>
              </div>
            )}
            <div className="shrink-0 flex flex-col gap-1">
              <label className="text-sm text-text-secondary leading-5 invisible">Action</label>
              <div className="h-10 flex items-center">
                {activeTab === 'analyze' && (
                  <button
                    onClick={handleAnalyze}
                    disabled={loading || !symbol.trim()}
                    className="btn-primary flex items-center gap-2 h-10 disabled:opacity-50"
                  >
                    {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Calculator className="w-5 h-5" />}
                    {t('strategyAnalysis.btnAnalyze')}
                  </button>
                )}
              {activeTab === 'pnl' && (
                <button
                  onClick={handlePnlScenarios}
                  disabled={loading || !symbol.trim()}
                  className="btn-primary flex items-center gap-2 h-10 disabled:opacity-50"
                >
                  {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <BarChart3 className="w-5 h-5" />}
                  {t('strategyAnalysis.btnShowPnl')}
                </button>
              )}
              {activeTab === 'find-best' && (
                <button
                  onClick={handleFindBest}
                  disabled={loading || !symbol.trim()}
                  className="btn-primary flex items-center gap-2 h-10 disabled:opacity-50"
                >
                  {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <TrendingUp className="w-5 h-5" />}
                  {t('strategyAnalysis.btnFindBest')}
                </button>
              )}
              {activeTab === 'compare' && (
                <button
                  onClick={handleCompare}
                  disabled={loading || !symbol.trim()}
                  className="btn-primary flex items-center gap-2 h-10 disabled:opacity-50"
                >
                  {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <GitCompare className="w-5 h-5" />}
                  {t('strategyAnalysis.btnCompare')}
                </button>
              )}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 mt-4 border-t border-white/10">
            <div>
              <div className="flex items-center gap-2 text-text-secondary text-sm mb-2">
                <History className="w-4 h-4" />
                <span>{t('strategyAnalysis.queryHistory')}</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {queryHistory.length === 0 ? (
                  <span className="text-text-muted text-sm">{t('strategyAnalysis.noHistoryRecords')}</span>
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
                <span>{t('strategyAnalysis.watchlist')}</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {watchlist.length === 0 ? (
                  <span className="text-text-muted text-sm">{t('strategyAnalysis.clickToAddWatchlist')}</span>
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
                        title={t('strategyAnalysis.remove')}
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
      </div>

      {error && (
        <div className="glass-card p-4 border-functional-danger/30">
          <p className="text-functional-danger">{error}</p>
        </div>
      )}

      {activeTab === 'analyze' && result && (
        <StrategyResultCard result={result} />
      )}

      {activeTab === 'pnl' && pnlData && (
        <PnlScenarioCard data={pnlData} />
      )}

      {activeTab === 'find-best' && findBestData && (
        <FindBestCard data={findBestData} />
      )}

      {activeTab === 'compare' && compareResults && compareResults.length > 0 && (
        <CompareResultsCard results={compareResults} />
      )}
    </div>
  );
};
