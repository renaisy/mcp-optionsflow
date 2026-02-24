/**
 * Dashboard page
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { TrendingUp, Calculator, LineChart, History, Loader2 } from 'lucide-react';
import { optionsAPI } from '../services/api';

interface MarketMetric {
  label: string;
  value: string;
  change?: string;
  changeClass?: string;
  loading?: boolean;
}

type MarketTab = 'us' | 'cn';

export const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [marketTab, setMarketTab] = useState<MarketTab>('us');
  const [usMetrics, setUsMetrics] = useState<MarketMetric[]>([
    { label: 'S&P 500', value: '—', change: '—', loading: true },
    { label: 'VIX Index', value: '—', change: '—', loading: true },
    { label: 'Risk-Free Rate', value: '—', change: '13-Week T-Bill', loading: true },
  ]);
  const [cnMetrics, setCnMetrics] = useState<MarketMetric[]>([
    { label: '上证50ETF', value: '—', change: '—', loading: true },
    { label: '沪深300ETF', value: '—', change: '—', loading: true },
    { label: '无风险利率', value: '—', change: '参考利率', loading: true },
  ]);

  const formatChange = (current?: number, previous?: number) => {
    if (current == null || previous == null || previous === 0) return null;
    const pct = ((current - previous) / previous) * 100;
    return { text: `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`, isPositive: pct >= 0 };
  };

  const getStockPrice = (d: Record<string, unknown> | null | undefined) => {
    if (!d || typeof d !== 'object') return null;
    const v = d.currentPrice ?? d.current_price;
    return typeof v === 'number' && !Number.isNaN(v) ? v : null;
  };

  const getStockPrevClose = (d: Record<string, unknown> | null | undefined) => {
    if (!d || typeof d !== 'object') return null;
    const v = d.previousClose ?? d.previous_close;
    return typeof v === 'number' && !Number.isNaN(v) ? v : null;
  };

  const getRateValue = (d: Record<string, unknown> | null | undefined) => {
    if (!d || typeof d !== 'object') return null;
    const pct = d.percentage;
    if (typeof pct === 'string' && pct) return pct;
    const r = d.risk_free_rate;
    return typeof r === 'number' && !Number.isNaN(r) ? `${(r * 100).toFixed(2)}%` : null;
  };

  useEffect(() => {
    const loadUs = async () => {
      try {
        const [spRes, vixRes, rateRes] = await Promise.allSettled([
          optionsAPI.getStockInfo('SPY'),
          optionsAPI.getStockInfo('^VIX'),
          optionsAPI.getRiskFreeRate(),
        ]);

        const next: MarketMetric[] = [];

        const spData = spRes.status === 'fulfilled' ? (spRes.value as { data?: unknown }).data : null;
        const price = getStockPrice(spData as Record<string, unknown>);
        const prevClose = getStockPrevClose(spData as Record<string, unknown>);
        const ch1 = formatChange(price ?? undefined, prevClose ?? undefined);
        next.push({
          label: 'S&P 500',
          value: price != null ? price.toLocaleString(undefined, { maximumFractionDigits: 2 }) : '—',
          change: ch1?.text ?? '—',
          changeClass: ch1 ? (ch1.isPositive ? 'positive' : 'negative') : 'text-text-muted',
          loading: false,
        });

        const vixData = vixRes.status === 'fulfilled' ? (vixRes.value as { data?: unknown }).data : null;
        const vixPrice = getStockPrice(vixData as Record<string, unknown>);
        const vixPrev = getStockPrevClose(vixData as Record<string, unknown>);
        const ch2 = formatChange(vixPrice ?? undefined, vixPrev ?? undefined);
        next.push({
          label: 'VIX Index',
          value: vixPrice != null ? vixPrice.toFixed(2) : '—',
          change: ch2?.text ?? '—',
          changeClass: ch2 ? (ch2.isPositive ? 'negative' : 'positive') : 'text-text-muted',
          loading: false,
        });

        const rateData = rateRes.status === 'fulfilled' ? (rateRes.value as { data?: unknown }).data : null;
        const rateVal = getRateValue(rateData as Record<string, unknown>);
        next.push({
          label: 'Risk-Free Rate',
          value: rateVal ?? '—',
          change: '13-Week T-Bill',
          changeClass: 'text-text-muted',
          loading: false,
        });

        setUsMetrics(next);
      } catch {
        setUsMetrics((prev) => prev.map((m) => ({ ...m, loading: false })));
      }
    };

    const loadCn = async () => {
      try {
        const [s50Res, s300Res, rateRes] = await Promise.allSettled([
          optionsAPI.getStockInfo('510050'),
          optionsAPI.getStockInfo('510300'),
          optionsAPI.getRiskFreeRate('cn'),
        ]);

        const next: MarketMetric[] = [];

        const s50Data = s50Res.status === 'fulfilled' ? (s50Res.value as { data?: unknown }).data : null;
        const s50Price = getStockPrice(s50Data as Record<string, unknown>);
        const s50Prev = getStockPrevClose(s50Data as Record<string, unknown>);
        const ch3 = formatChange(s50Price ?? undefined, s50Prev ?? undefined);
        next.push({
          label: '上证50ETF',
          value: s50Price != null ? s50Price.toFixed(3) : '—',
          change: ch3?.text ?? '—',
          changeClass: ch3 ? (ch3.isPositive ? 'positive' : 'negative') : 'text-text-muted',
          loading: false,
        });

        const s300Data = s300Res.status === 'fulfilled' ? (s300Res.value as { data?: unknown }).data : null;
        const s300Price = getStockPrice(s300Data as Record<string, unknown>);
        const s300Prev = getStockPrevClose(s300Data as Record<string, unknown>);
        const ch4 = formatChange(s300Price ?? undefined, s300Prev ?? undefined);
        next.push({
          label: '沪深300ETF',
          value: s300Price != null ? s300Price.toFixed(3) : '—',
          change: ch4?.text ?? '—',
          changeClass: ch4 ? (ch4.isPositive ? 'positive' : 'negative') : 'text-text-muted',
          loading: false,
        });

        const cnRateData = rateRes.status === 'fulfilled' ? (rateRes.value as { data?: unknown }).data : null;
        const cnRateVal = getRateValue(cnRateData as Record<string, unknown>);
        next.push({
          label: '无风险利率',
          value: cnRateVal ?? '—',
          change: '参考利率',
          changeClass: 'text-text-muted',
          loading: false,
        });

        setCnMetrics(next);
      } catch {
        setCnMetrics((prev) => prev.map((m) => ({ ...m, loading: false })));
      }
    };

    loadUs();
    loadCn();
  }, []);

  const quickActions = [
    { icon: LineChart, titleKey: 'dashboard.optionsChain', descKey: 'dashboard.optionsChainDesc', path: '/options', color: 'from-primary to-primary-dark' },
    { icon: Calculator, titleKey: 'dashboard.strategyAnalysis', descKey: 'dashboard.strategyAnalysisDesc', path: '/strategies', color: 'from-functional-info to-primary-dark' },
    { icon: TrendingUp, titleKey: 'dashboard.greeksVisualizer', descKey: 'dashboard.greeksVisualizerDesc', path: '/greeks', color: 'from-functional-success to-primary-dark' },
    { icon: History, titleKey: 'dashboard.history', descKey: 'dashboard.historyDesc', path: '/history', color: 'from-functional-warning to-primary-dark' },
  ];

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="glass-card p-8">
        <h1 className="text-3xl font-bold text-text mb-2">
          {t('dashboard.welcome')} <span className="gradient-text">海山云创OptionsFlow平台</span>
        </h1>
        <p className="text-text-secondary text-lg">{t('dashboard.subtitle')}</p>
      </div>

      <div>
        <h2 className="text-xl font-bold text-text mb-4">{t('dashboard.quickActions')}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {quickActions.map((action, index) => {
            const Icon = action.icon;
            return (
              <button
                key={index}
                onClick={() => navigate(action.path)}
                className="glass-card p-6 text-left hover:scale-105 transition-all neon-glow"
              >
                <div className={`inline-flex p-3 rounded-lg bg-gradient-to-r ${action.color} mb-4`}>
                  <Icon className="w-6 h-6 text-white" />
                </div>
                <h3 className="text-lg font-semibold text-text mb-1">{t(action.titleKey)}</h3>
                <p className="text-sm text-text-muted">{t(action.descKey)}</p>
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <h2 className="text-xl font-bold text-text">{t('dashboard.marketOverview')}</h2>
          <div className="flex rounded-lg overflow-hidden border border-white/10 bg-background-light/50 p-0.5">
            <button
              onClick={() => setMarketTab('us')}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                marketTab === 'us' ? 'bg-primary text-white rounded' : 'text-text-secondary hover:text-text'
              }`}
            >
              {t('dashboard.usMarket')}
            </button>
            <button
              onClick={() => setMarketTab('cn')}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                marketTab === 'cn' ? 'bg-primary text-white rounded' : 'text-text-secondary hover:text-text'
              }`}
            >
              {t('dashboard.chinaMarket')}
            </button>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {(marketTab === 'us' ? usMetrics : cnMetrics).map((m, i) => (
            <div key={m.label} className="metric-card">
              <p className="metric-label">{m.label}</p>
              <p className={`metric-value ${i === 0 ? 'text-functional-success' : ''} ${i === 1 ? 'text-functional-warning' : ''} ${i === 2 ? 'text-primary' : ''}`}>
                {m.loading ? <Loader2 className="w-6 h-6 animate-spin inline" /> : m.value}
              </p>
              <p className={`metric-change ${m.changeClass ?? ''}`}>{m.change ?? '—'}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-text-muted">
          {marketTab === 'us' ? t('dashboard.dataSourceUs') : t('dashboard.dataSourceCn')}
        </p>
      </div>

      <div className="glass-card p-6">
        <h3 className="text-lg font-semibold text-text mb-3">{t('dashboard.gettingStarted')}</h3>
        <ul className="space-y-2 text-text-secondary">
          <li className="flex items-start gap-2">
            <span className="text-primary font-bold">1.</span>
            <span>{t('dashboard.step1')}</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary font-bold">2.</span>
            <span>{t('dashboard.step2')}</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary font-bold">3.</span>
            <span>{t('dashboard.step3')}</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary font-bold">4.</span>
            <span>{t('dashboard.step4')}</span>
          </li>
        </ul>
      </div>
    </div>
  );
};
