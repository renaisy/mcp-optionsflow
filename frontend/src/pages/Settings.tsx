/**
 * Settings page - Basic configuration
 */
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Settings as SettingsIcon, CheckCircle, XCircle } from 'lucide-react';
import { useAuthStore } from '../store';
import { optionsAPI, agentAPI } from '../services/api';

interface ProviderStatus {
  name: string;
  priority: number;
  is_available: boolean;
  request_count?: number;
  error_count?: number;
  note?: string;
}

const PROVIDER_DEFAULTS: Record<string, { baseUrl: string; model: string }> = {
  openai: { baseUrl: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  glm: { baseUrl: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4' },
  ollama: { baseUrl: 'http://localhost:11434/v1', model: 'llama3' },
  vllm: { baseUrl: 'http://localhost:8000/v1', model: '' },
};

export const Settings: React.FC = () => {
  const { t } = useTranslation();
  const { user, logout } = useAuthStore();
  const [sourcesStatus, setSourcesStatus] = useState<{
    multi_source_enabled?: boolean;
    providers?: ProviderStatus[];
    available_providers?: number;
    message?: string;
  } | null>(null);

  const [llmConfig, setLlmConfig] = useState<{
    provider: string;
    api_key?: string;
    base_url?: string;
    model: string;
    enabled?: boolean;
  }>({
    provider: 'openai',
    base_url: PROVIDER_DEFAULTS.openai.baseUrl,
    model: PROVIDER_DEFAULTS.openai.model,
    enabled: true,
  });
  const [llmSaving, setLlmSaving] = useState(false);
  const [llmSaved, setLlmSaved] = useState(false);

  useEffect(() => {
    optionsAPI.getSourcesStatus()
      .then((res) => setSourcesStatus(res.data as typeof sourcesStatus))
      .catch(() =>
        setSourcesStatus({
          multi_source_enabled: false,
          message: "Failed to fetch",
          providers: [
            { name: "Yahoo Finance", priority: 100, is_available: true, note: "Default" },
            { name: "MarketData.app", priority: 90, is_available: false, note: "API error" },
            { name: "Alpha Vantage", priority: 80, is_available: false, note: "API error" },
          ],
        })
      );
  }, []);

  useEffect(() => {
    agentAPI.getConfig()
      .then((res) => {
        const c = res.data;
        if (c) {
          setLlmConfig({
            provider: c.provider || 'openai',
            base_url: c.base_url || PROVIDER_DEFAULTS[c.provider]?.baseUrl || '',
            model: c.model || PROVIDER_DEFAULTS[c.provider]?.model || '',
            enabled: c.enabled !== false,
          });
        }
      })
      .catch(() => {});
  }, []);

  const handleProviderChange = (provider: string) => {
    const def = PROVIDER_DEFAULTS[provider];
    setLlmConfig((prev) => ({
      ...prev,
      provider,
      base_url: def?.baseUrl ?? prev.base_url,
      model: def?.model ?? prev.model,
    }));
  };

  const saveLlmConfig = () => {
    setLlmSaving(true);
    setLlmSaved(false);
    agentAPI.putConfig({
      provider: llmConfig.provider,
      api_key: llmConfig.api_key || undefined,
      base_url: llmConfig.base_url || undefined,
      model: llmConfig.model,
      enabled: llmConfig.enabled,
    })
      .then(() => {
        setLlmSaved(true);
        setTimeout(() => setLlmSaved(false), 3000);
      })
      .catch(() => {})
      .finally(() => setLlmSaving(false));
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="glass-card p-6">
        <h1 className="text-2xl font-bold text-text mb-4 flex items-center gap-2">
          <SettingsIcon className="w-8 h-8 text-primary" />
          {t('settings.title')}
        </h1>

        <div className="space-y-6">
          <section>
            <h2 className="text-lg font-semibold text-text mb-3">{t('settings.account')}</h2>
            <div className="glass-card p-4 space-y-2">
              <p className="text-text-secondary">
                <span className="text-text-muted">Username:</span> {user?.username ?? '—'}
              </p>
              <p className="text-text-secondary">
                <span className="text-text-muted">Email:</span> {user?.email ?? '—'}
              </p>
              <button onClick={logout} className="btn-secondary mt-2">
                {t('nav.logout')}
              </button>
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-text mb-3">{t('settings.dataSources')}</h2>
            <div className="glass-card p-4 space-y-3 text-text-secondary text-sm">
              {sourcesStatus?.multi_source_enabled ? (
                <p className="text-functional-success flex items-center gap-2">
                  <CheckCircle className="w-4 h-4" />
                  Multi-source failover active ({sourcesStatus.available_providers ?? 0} available)
                </p>
              ) : sourcesStatus?.message ? (
                <p className="flex items-center gap-2 text-functional-warning">
                  <XCircle className="w-4 h-4 flex-shrink-0" />
                  {sourcesStatus.message}
                </p>
              ) : null}
              {sourcesStatus?.providers && sourcesStatus.providers.length > 0 ? (
                <div className="space-y-2 pt-1">
                  <p className="text-text-muted text-xs">All configured sources:</p>
                  {sourcesStatus.providers.map((p) => (
                    <div key={p.name} className="flex items-center justify-between gap-3">
                      <span>{p.name}</span>
                      <div className="flex items-center gap-2 text-xs">
                        {p.is_available ? (
                          <span className="text-functional-success">Available</span>
                        ) : (
                          <span className="text-functional-warning">Unavailable</span>
                        )}
                        {p.note && <span className="text-text-muted">({p.note})</span>}
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
              {(!sourcesStatus?.providers || sourcesStatus.providers.length === 0) && sourcesStatus && (
                <p className="text-text-muted">No provider info available</p>
              )}
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-text mb-3">{t('settings.llmConfig')}</h2>
            <div className="glass-card p-4 space-y-4">
              <div className="flex flex-col gap-1">
                <label className="text-sm text-text-secondary">{t('settings.provider')}</label>
                <select
                  value={llmConfig.provider}
                  onChange={(e) => handleProviderChange(e.target.value)}
                  className="input-field max-w-xs"
                >
                  <option value="openai">{t('settings.providerOpenAI')}</option>
                  <option value="glm">{t('settings.providerGlm')}</option>
                  <option value="ollama">{t('settings.providerOllama')}</option>
                  <option value="vllm">{t('settings.providerVllm')}</option>
                </select>
              </div>
              {llmConfig.provider !== 'ollama' && (
                <div className="flex flex-col gap-1">
                  <label className="text-sm text-text-secondary">{t('settings.apiKey')}</label>
                  <input
                    type="password"
                    value={llmConfig.api_key ?? ''}
                    onChange={(e) => setLlmConfig((p) => ({ ...p, api_key: e.target.value }))}
                    placeholder={llmConfig.provider === 'ollama' ? '' : 'sk-...'}
                    className="input-field max-w-md"
                  />
                </div>
              )}
              <div className="flex flex-col gap-1">
                <label className="text-sm text-text-secondary">{t('settings.baseUrl')}</label>
                <input
                  type="text"
                  value={llmConfig.base_url ?? ''}
                  onChange={(e) => setLlmConfig((p) => ({ ...p, base_url: e.target.value }))}
                  placeholder="https://..."
                  className="input-field max-w-md"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-sm text-text-secondary">{t('settings.model')}</label>
                <input
                  type="text"
                  value={llmConfig.model ?? ''}
                  onChange={(e) => setLlmConfig((p) => ({ ...p, model: e.target.value }))}
                  placeholder="gpt-4o-mini, glm-4, llama3..."
                  className="input-field max-w-md"
                />
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={saveLlmConfig}
                  disabled={llmSaving || !llmConfig.model.trim()}
                  className="btn-primary disabled:opacity-50"
                >
                  {llmSaving ? t('common.loading') : t('settings.saveConfig')}
                </button>
                {llmSaved && (
                  <span className="text-functional-success text-sm flex items-center gap-1">
                    <CheckCircle className="w-4 h-4" />{t('settings.configSaved')}
                  </span>
                )}
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-text mb-3">{t('settings.application')}</h2>
            <div className="glass-card p-4 space-y-2 text-text-secondary text-sm">
              <p>海山云创OptionsFlow平台 v1.0.0</p>
              <p>Options strategy analysis platform with real-time data and visualization.</p>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};
