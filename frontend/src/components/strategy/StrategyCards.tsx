/**
 * Shared strategy result cards - used by StrategyAnalysis and AgentChat
 */
import React from 'react';
import { useTranslation } from 'react-i18next';
import { Calculator, BarChart3, TrendingUp, GitCompare, Info } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import type { StrategyAnalysisResult } from '../../types/strategy';

const STRATEGY_KEYS: Record<string, string> = {
  ccs: 'strategyAnalysis.strategyCcs',
  pcs: 'strategyAnalysis.strategyPcs',
  csp: 'strategyAnalysis.strategyCsp',
  cc: 'strategyAnalysis.strategyCc',
};

export function StrategyResultCard({ result, compact = false }: { result: StrategyAnalysisResult; compact?: boolean }) {
  const { t } = useTranslation();
  const analysis = (result.full_analysis || result) as unknown as Record<string, unknown>;
  const metrics = analysis.metrics as Record<string, number> | undefined;
  const strikes = analysis.strikes as Record<string, number> | undefined;
  const greeks = analysis.greeks as Record<string, number> | undefined;
  const isChina = /^\d{6}$/.test(result.symbol);
  const prefix = isChina ? '' : '$';
  const cardClass = compact ? 'p-4 rounded-xl bg-background-light/40 border border-white/10 space-y-4' : 'glass-card p-6 space-y-6';
  const metricClass = compact ? 'p-3 rounded-lg bg-background/50 border border-white/5 space-y-1' : 'metric-card';

  return (
    <div className={cardClass}>
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-primary/10">
          <Calculator className="w-6 h-6 text-primary" />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-text">
            {result.symbol} — {t(STRATEGY_KEYS[result.strategy_type] ?? '') || result.strategy_type}
          </h2>
          <p className="text-sm text-text-muted">{result.expiration_date}</p>
        </div>
      </div>

      <div className={`grid gap-3 ${compact ? 'grid-cols-2' : 'grid-cols-2 md:grid-cols-4'}`}>
        <div className={metricClass}>
          <p className="metric-label">{t('strategyAnalysis.currentPrice')}</p>
          <p className={`metric-value ${compact ? 'text-xl' : ''}`}>{prefix}{result.current_price?.toFixed(2) ?? '—'}</p>
        </div>
        <div className={metricClass}>
          <p className="metric-label">{t('strategyAnalysis.expiration')}</p>
          <p className={`metric-value ${compact ? 'text-base' : 'text-lg'}`}>{result.expiration_date ?? '—'}</p>
        </div>
        {(strikes?.short_strike ?? strikes?.long_strike ?? strikes?.strike) != null && (
          <div className={`${metricClass} ${compact ? '' : 'col-span-2'}`}>
            <p className="metric-label">{t('strategyAnalysis.strikes')}</p>
            <p className="metric-value text-lg">
              {strikes?.short_strike != null && strikes?.long_strike != null
                ? `${prefix}${strikes.long_strike} / ${prefix}${strikes.short_strike}`
                : strikes?.strike != null
                  ? `${prefix}${strikes.strike}`
                  : '—'}
            </p>
          </div>
        )}
      </div>

      {metrics && (
        <div className={`grid ${compact ? 'grid-cols-2 gap-3' : 'grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4'}`}>
          {metrics.credit != null && (
            <div className={`${metricClass} border-functional-success/20`}>
              <p className="metric-label">{t('strategyAnalysis.credit')}</p>
              <p className={`metric-value text-functional-success ${compact ? 'text-lg' : ''}`}>{prefix}{metrics.credit.toFixed(2)}</p>
            </div>
          )}
          {metrics.premium != null && (
            <div className={`${metricClass} border-functional-success/20`}>
              <p className="metric-label">{t('strategyAnalysis.premium')}</p>
              <p className={`metric-value text-functional-success ${compact ? 'text-lg' : ''}`}>{prefix}{metrics.premium?.toFixed(2)}</p>
            </div>
          )}
          {metrics.max_profit != null && (
            <div className={`${metricClass} border-functional-success/20`}>
              <p className="metric-label">{t('strategyAnalysis.maxProfit')}</p>
              <p className={`metric-value text-functional-success ${compact ? 'text-lg' : ''}`}>{prefix}{metrics.max_profit?.toFixed(2)}</p>
            </div>
          )}
          {metrics.max_loss != null && (
            <div className={`${metricClass} border-functional-danger/20`}>
              <p className="metric-label">{t('strategyAnalysis.maxLoss')}</p>
              <p className={`metric-value text-functional-danger ${compact ? 'text-lg' : ''}`}>{prefix}{metrics.max_loss?.toFixed(2)}</p>
            </div>
          )}
          {metrics.probability_of_profit != null && (
            <div className={metricClass}>
              <p className="metric-label">{t('strategyAnalysis.probOfProfit')}</p>
              <p className={`metric-value ${compact ? 'text-lg' : ''}`}>{(metrics.probability_of_profit * 100).toFixed(1)}%</p>
            </div>
          )}
          {metrics.risk_reward_ratio != null && (
            <div className={metricClass}>
              <p className="metric-label">{t('strategyAnalysis.riskReward')}</p>
              <p className={`metric-value ${compact ? 'text-lg' : ''}`}>{metrics.risk_reward_ratio.toFixed(2)}</p>
            </div>
          )}
        </div>
      )}

      {greeks && (greeks.net_delta != null || greeks.delta != null || greeks.net_theta != null) && (
        <div className="pt-4 border-t border-white/10">
          <h3 className="text-sm font-medium text-text-secondary mb-2">{t('strategyAnalysis.greeks')}</h3>
          <div className="flex flex-wrap gap-6 text-sm">
            {greeks.net_delta != null && <span className="text-text">{t('strategyAnalysis.netDelta')}: <span className="font-mono">{greeks.net_delta.toFixed(3)}</span></span>}
            {greeks.delta != null && greeks.net_delta == null && <span className="text-text">{t('strategyAnalysis.delta')}: <span className="font-mono">{greeks.delta.toFixed(3)}</span></span>}
            {greeks.net_theta != null && <span className="text-text">{t('strategyAnalysis.netTheta')}: <span className="font-mono">{greeks.net_theta.toFixed(2)}</span></span>}
            {greeks.theta != null && greeks.net_theta == null && <span className="text-text">{t('strategyAnalysis.theta')}: <span className="font-mono">{greeks.theta.toFixed(2)}</span></span>}
            {greeks.net_gamma != null && <span className="text-text">{t('strategyAnalysis.netGamma')}: <span className="font-mono">{greeks.net_gamma.toFixed(4)}</span></span>}
          </div>
        </div>
      )}
    </div>
  );
}

export function PnlScenarioCard({ data }: { data: Record<string, unknown> }) {
  const { t } = useTranslation();
  const scenarios = data.scenarios as Array<{ stock_price: number; pnl: number; status: string }> | undefined;
  const currentPrice = data.current_price as number | undefined;
  const strategy = (data.strategy as string) || 'Strategy';
  const keyLevels = data.key_levels as { max_profit?: { stock_price: number; pnl: number }; max_loss?: { stock_price: number; pnl: number } } | undefined;
  const isChina = /^\d{6}$/.test(String(data.symbol ?? ''));
  const prefix = isChina ? '' : '$';

  if (!scenarios?.length) return null;

  const chartData = scenarios.map((s) => ({ price: s.stock_price, pnl: s.pnl, name: `${s.stock_price.toFixed(0)}` }));
  const currentPriceLabel = currentPrice != null ? chartData.reduce((a, b) => (Math.abs(b.price - currentPrice) < Math.abs(a.price - currentPrice) ? b : a))?.name : null;
  const chartPnlLabel = t('strategyAnalysis.chartPnl');
  const chartCurrentLabel = t('strategyAnalysis.chartCurrent');

  return (
    <div className="glass-card p-6 space-y-6">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-primary/10">
          <BarChart3 className="w-6 h-6 text-primary" />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-text">{t('strategyAnalysis.pnlAtExpiration')}</h2>
          <p className="text-sm text-text-muted">{String(data.symbol ?? '')} — {strategy} — {String(data.expiration_date ?? '')}</p>
        </div>
      </div>

      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
            <XAxis dataKey="name" stroke="#94A3B8" fontSize={11} />
            <YAxis stroke="#94A3B8" fontSize={11} tickFormatter={(v) => `${prefix}${v}`} />
            <Tooltip
              formatter={(v: number | undefined) => (v != null ? [`${prefix}${v.toFixed(2)}`, chartPnlLabel] as [string, string] : ['—', chartPnlLabel])}
              labelFormatter={(_, payload) => payload?.[0] ? `${t('strategyAnalysis.chartStock')}: ${prefix}${(payload[0].payload as { price: number }).price.toFixed(2)}` : ''}
            />
            {currentPriceLabel && <ReferenceLine x={currentPriceLabel} stroke="#00D4FF" strokeDasharray="4 4" label={chartCurrentLabel} />}
            <ReferenceLine y={0} stroke="#64748B" />
            <Line type="monotone" dataKey="pnl" stroke="#10B981" strokeWidth={2} dot={false} name={chartPnlLabel} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        <div className="p-3 rounded-lg bg-background-light/50">
          <p className="text-text-muted">{t('strategyAnalysis.currentPrice')}</p>
          <p className="font-semibold text-text">{prefix}{currentPrice?.toFixed(2) ?? '—'}</p>
        </div>
        {keyLevels?.max_profit && (
          <div className="p-3 rounded-lg bg-functional-success/10">
            <p className="text-text-muted">{t('strategyAnalysis.maxProfit')}</p>
            <p className="font-semibold text-functional-success">{prefix}{keyLevels.max_profit.pnl.toFixed(2)}</p>
          </div>
        )}
        {keyLevels?.max_loss && (
          <div className="p-3 rounded-lg bg-functional-danger/10">
            <p className="text-text-muted">{t('strategyAnalysis.maxLoss')}</p>
            <p className="font-semibold text-functional-danger">{prefix}{keyLevels.max_loss.pnl.toFixed(2)}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export function FindBestCard({ data }: { data: Record<string, unknown> }) {
  const { t } = useTranslation();
  const best = data.best_strategies as Array<{ strategy: string; analysis: StrategyAnalysisResult; score: number }> | undefined;
  const recommendation = data.recommendation as { strategy?: string; analysis: StrategyAnalysisResult; score?: number } | undefined;
  const strategiesFound = (data.strategies_found as number | undefined) ?? 0;

  return (
    <div className="glass-card p-6 space-y-6">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-primary/10">
          <TrendingUp className="w-6 h-6 text-primary" />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-text">{t('strategyAnalysis.bestStrategies')}</h2>
          <p className="text-sm text-text-muted">{String(data.symbol ?? '')} — {t('strategyAnalysis.foundStrategies', { count: strategiesFound })}</p>
        </div>
      </div>

      {recommendation && (
        <div className="p-4 rounded-xl bg-primary/10 border border-primary/20">
          <div className="flex items-center gap-2 mb-3">
            <span className="px-2 py-0.5 rounded text-xs font-medium bg-primary/20 text-primary">{t('strategyAnalysis.topRecommendation')}</span>
            <span className="text-sm text-text-muted">{t('strategyAnalysis.score')}: {recommendation?.score?.toFixed(2) ?? '—'}</span>
          </div>
          <StrategyResultCard result={(recommendation as { analysis: StrategyAnalysisResult }).analysis} />
        </div>
      )}

      {best && best.length > 1 && (
        <div className="space-y-4 mt-6">
          <h3 className="text-sm font-medium text-text-secondary">{t('strategyAnalysis.otherOptions')}</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {best.slice(1, 4).map((item, i) => (
              <div key={i} className="p-4 rounded-lg bg-background-light/50 hover:bg-background-light/70 transition-colors">
                <StrategyResultCard result={item.analysis} />
              </div>
            ))}
          </div>
        </div>
      )}

      {(!best || best.length === 0) && !recommendation && (
        <p className="text-text-muted text-center py-8">{t('strategyAnalysis.noStrategiesCriteria')}</p>
      )}
    </div>
  );
}

export function CompareResultsCard({ results }: { results: StrategyAnalysisResult[] }) {
  const { t } = useTranslation();
  return (
    <div className="glass-card p-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 rounded-lg bg-primary/10">
          <GitCompare className="w-6 h-6 text-primary" />
        </div>
        <h2 className="text-xl font-semibold text-text">{t('strategyAnalysis.strategyComparison')}</h2>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {results.map((r, i) => (
          <StrategyResultCard key={i} result={r} compact />
        ))}
      </div>
    </div>
  );
}

export function StockInfoCard({ data }: { data: Record<string, unknown> }) {
  const { t } = useTranslation();
  const symbol = (data.symbol as string) || '';
  const isChina = /^\d{6}$/.test(symbol);
  const prefix = isChina ? '' : '$';

  return (
    <div className="glass-card p-6 space-y-4">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-primary/10">
          <Info className="w-6 h-6 text-primary" />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-text">{symbol} — {t('strategyAnalysis.currentPrice')}</h2>
          <p className="text-sm text-text-muted">{data.companyName as string || ''}</p>
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-3 rounded-lg bg-background-light/50">
          <p className="text-text-muted text-sm">{t('strategyAnalysis.currentPrice')}</p>
          <p className="font-semibold text-text">{prefix}{(data.currentPrice as number)?.toFixed(2) ?? '—'}</p>
        </div>
        {data.volume != null && (
          <div className="p-3 rounded-lg bg-background-light/50">
            <p className="text-text-muted text-sm">Volume</p>
            <p className="font-semibold text-text">{(data.volume as number).toLocaleString()}</p>
          </div>
        )}
        {data.marketCap != null && (
          <div className="p-3 rounded-lg bg-background-light/50">
            <p className="text-text-muted text-sm">Market Cap</p>
            <p className="font-semibold text-text">{prefix}{((data.marketCap as number) / 1e9).toFixed(2)}B</p>
          </div>
        )}
        {data.dividendYield != null && (data.dividendYield as number) > 0 && (
          <div className="p-3 rounded-lg bg-background-light/50">
            <p className="text-text-muted text-sm">Dividend Yield</p>
            <p className="font-semibold text-text">{((data.dividendYield as number) * 100).toFixed(2)}%</p>
          </div>
        )}
      </div>
    </div>
  );
}
