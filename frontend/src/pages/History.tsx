/**
 * History page - View past strategy analyses with multi-dimension filters
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { History as HistoryIcon, Trash2, ChevronRight, Loader2, Filter, X } from 'lucide-react';
import { strategiesAPI } from '../services/api';
import type { AnalysisHistory } from '../types/strategy';

const STRATEGY_LABELS: Record<string, string> = {
  ccs: 'CCS',
  pcs: 'PCS',
  csp: 'CSP',
  cc: 'CC',
};

interface FilterOptions {
  symbols: string[];
  strategy_types: string[];
  expiration_dates: string[];
}

export const History: React.FC = () => {
  const { t } = useTranslation();
  const [items, setItems] = useState<AnalysisHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<AnalysisHistory | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({
    symbols: [],
    strategy_types: [],
    expiration_dates: [],
  });
  const [filters, setFilters] = useState({
    symbol: '',
    strategy_type: '',
    expiration_date: '',
    date_from: '',
    date_to: '',
  });

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params: Record<string, string | number | undefined> = { limit: 100 };
      if (filters.symbol) params.symbol = filters.symbol;
      if (filters.strategy_type) params.strategy_type = filters.strategy_type;
      if (filters.expiration_date) params.expiration_date = filters.expiration_date;
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;
      const res = await strategiesAPI.getHistory(params);
      setItems((res.data as AnalysisHistory[]) || []);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to load history';
      setError(String(msg));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [filters.symbol, filters.strategy_type, filters.expiration_date, filters.date_from, filters.date_to]);

  const loadFilterOptions = useCallback(async () => {
    try {
      const res = await strategiesAPI.getHistoryFilterOptions();
      setFilterOptions((res.data as FilterOptions) || { symbols: [], strategy_types: [], expiration_dates: [] });
    } catch {
      setFilterOptions({ symbols: [], strategy_types: [], expiration_dates: [] });
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    loadFilterOptions();
  }, [loadFilterOptions]);

  const handleSelect = async (id: number) => {
    setSelectedId(id);
    try {
      const res = await strategiesAPI.getAnalysisDetail(id);
      setDetail(res.data as AnalysisHistory);
    } catch {
      setDetail(null);
    }
  };

  const handleDelete = async (id: number) => {
    setDeleting(id);
    try {
      await strategiesAPI.deleteAnalysis(id);
      setItems((prev) => prev.filter((i) => i.id !== id));
      if (selectedId === id) {
        setSelectedId(null);
        setDetail(null);
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Delete failed';
      setError(String(msg));
    } finally {
      setDeleting(null);
    }
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleString();
  };

  const hasActiveFilters =
    !!filters.symbol || !!filters.strategy_type || !!filters.expiration_date || !!filters.date_from || !!filters.date_to;

  const clearFilters = () => {
    setFilters({ symbol: '', strategy_type: '', expiration_date: '', date_from: '', date_to: '' });
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="glass-card p-6">
        <h1 className="text-2xl font-bold text-text mb-4 flex items-center gap-2">
          <HistoryIcon className="w-8 h-8 text-primary" />
          {t('history.title')}
        </h1>

        <div className="mb-6 p-4 rounded-xl bg-background-light/50 border border-white/10">
          <div className="flex items-center gap-2 mb-4">
            <Filter className="w-4 h-4 text-primary shrink-0" />
            <span className="text-sm font-medium text-text-secondary">{t('history.filterLabel')}</span>
            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="ml-auto flex items-center gap-1.5 text-sm text-functional-warning hover:text-primary transition-colors px-2 py-1 rounded hover:bg-white/5"
              >
                <X className="w-3.5 h-3.5" />
                {t('history.clearFilters')}
              </button>
            )}
          </div>
          <div className="flex flex-wrap items-end gap-4">
            <div className="flex flex-col gap-1 min-w-[100px]">
              <label className="text-sm text-text-secondary leading-5">{t('history.symbol')}</label>
              <select
                value={filters.symbol}
                onChange={(e) => setFilters((f) => ({ ...f, symbol: e.target.value }))}
                className="input-field h-10"
              >
                <option value="">{t('common.all')}</option>
                {filterOptions.symbols.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1 min-w-[100px]">
              <label className="text-sm text-text-secondary leading-5">{t('history.strategy')}</label>
              <select
                value={filters.strategy_type}
                onChange={(e) => setFilters((f) => ({ ...f, strategy_type: e.target.value }))}
                className="input-field h-10"
              >
                <option value="">{t('common.all')}</option>
                {filterOptions.strategy_types.map((s) => (
                  <option key={s} value={s}>{STRATEGY_LABELS[s] ?? s}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1 min-w-[120px]">
              <label className="text-sm text-text-secondary leading-5">{t('history.expirationDate')}</label>
              <select
                value={filters.expiration_date}
                onChange={(e) => setFilters((f) => ({ ...f, expiration_date: e.target.value }))}
                className="input-field h-10"
              >
                <option value="">{t('common.all')}</option>
                {filterOptions.expiration_dates.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1 min-w-[140px]">
              <label className="text-sm text-text-secondary leading-5">{t('history.dateFrom')}</label>
              <input
                type="date"
                value={filters.date_from}
                onChange={(e) => setFilters((f) => ({ ...f, date_from: e.target.value }))}
                className="input-field h-10 [color-scheme:dark]"
              />
            </div>
            <div className="flex flex-col gap-1 min-w-[140px]">
              <label className="text-sm text-text-secondary leading-5">{t('history.dateTo')}</label>
              <input
                type="date"
                value={filters.date_to}
                onChange={(e) => setFilters((f) => ({ ...f, date_to: e.target.value }))}
                className="input-field h-10 [color-scheme:dark]"
              />
            </div>
          </div>
        </div>

        {loading && (
          <div className="flex justify-center py-12">
            <Loader2 className="w-10 h-10 animate-spin text-primary" />
          </div>
        )}

        {error && (
          <div className="p-4 mb-4 rounded-lg bg-functional-danger/10 border border-functional-danger/30">
            <p className="text-functional-danger">{error}</p>
          </div>
        )}

        {!loading && items.length === 0 && (
          <div className="text-center py-12 text-text-muted">
            {hasActiveFilters ? t('history.noResults') : t('history.noHistory')}
          </div>
        )}

        {!loading && items.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="space-y-2 max-h-[500px] overflow-y-auto">
              {items.map((item) => (
                <div
                  key={item.id}
                  className={`glass-card p-4 flex items-center justify-between cursor-pointer transition-all ${
                    selectedId === item.id ? 'border-primary ring-1 ring-primary/30' : ''
                  }`}
                  onClick={() => handleSelect(item.id)}
                >
                  <div>
                    <p className="font-semibold text-text">{item.symbol}</p>
                    <p className="text-sm text-text-muted">
                      {STRATEGY_LABELS[item.strategy_type] ?? item.strategy_type} · {item.expiration_date}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(item.id);
                      }}
                      disabled={deleting === item.id}
                      className="p-2 text-functional-danger hover:bg-functional-danger/10 rounded-lg"
                    >
                      {deleting === item.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                    </button>
                    <ChevronRight className="w-5 h-5 text-text-muted" />
                  </div>
                </div>
              ))}
            </div>

            <div>
              {detail ? (
                <DetailPanel item={detail} />
              ) : (
                <div className="glass-card p-8 text-center text-text-muted">
                  {t('history.selectToView')}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

function DetailPanel({ item }: { item: AnalysisHistory }) {
  const ar = item.analysis_result as unknown as Record<string, unknown>;
  const metrics = ar?.metrics as Record<string, number> | undefined;
  const strikes = ar?.strikes as Record<string, number> | undefined;
  const greeks = ar?.greeks as Record<string, number> | undefined;

  return (
    <div className="glass-card p-6 space-y-4">
      <h3 className="text-lg font-semibold text-text">
        {item.symbol} - {STRATEGY_LABELS[item.strategy_type] ?? item.strategy_type}
      </h3>
      <p className="text-sm text-text-muted">
        {item.expiration_date} · ${item.current_price?.toFixed(2)} · {new Date(item.created_at).toLocaleString()}
      </p>
      {strikes && (
        <div className="grid grid-cols-2 gap-2">
          {strikes.short_strike != null && <div><span className="text-text-muted">Short Strike:</span> ${strikes.short_strike}</div>}
          {strikes.long_strike != null && <div><span className="text-text-muted">Long Strike:</span> ${strikes.long_strike}</div>}
          {strikes.strike != null && <div><span className="text-text-muted">Strike:</span> ${strikes.strike}</div>}
        </div>
      )}
      {metrics && (
        <div className="grid grid-cols-2 gap-2">
          {Object.entries(metrics).map(([k, v]) => (
            <div key={k}>
              <span className="text-text-muted capitalize">{k.replace(/_/g, ' ')}:</span>{' '}
              {typeof v === 'number' && (k.includes('probability') || k.includes('profit')) ? `${(v * 100).toFixed(1)}%` : `$${Number(v).toFixed(2)}`}
            </div>
          ))}
        </div>
      )}
      {greeks && (
        <div>
          <p className="text-sm text-text-muted mb-1">Greeks</p>
          <div className="flex flex-wrap gap-3 text-sm">
            {Object.entries(greeks).map(([k, v]) => (
              <span key={k}>{k}: {Number(v).toFixed(3)}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
