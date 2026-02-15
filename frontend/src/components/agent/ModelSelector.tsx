/**
 * Model selector - switch between available LLM models with status
 */
import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Cpu, RefreshCw, ChevronDown, Check } from 'lucide-react';
import { agentAPI, type AgentModel } from '../../services/api';

interface ModelSelectorProps {
  selectedModel: string | null;
  onSelect: (modelId: string) => void;
  disabled?: boolean;
}

function StatusDot({ status }: { status: AgentModel['status'] }) {
  const color =
    status === 'running' ? 'bg-functional-success' :
    status === 'available' ? 'bg-functional-success' :
    status === 'unavailable' ? 'bg-functional-danger' :
    'bg-text-muted';
  const pulse = status === 'running' ? 'animate-pulse' : '';
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${color} ${pulse}`}
      title={status}
    />
  );
}

export const ModelSelector: React.FC<ModelSelectorProps> = ({
  selectedModel,
  onSelect,
  disabled = false,
}) => {
  const { t } = useTranslation();
  const [models, setModels] = useState<AgentModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const fetchModels = () => {
    setLoading(true);
    agentAPI
      .getModels()
      .then((res) => {
        const data = res.data;
        setModels(Array.isArray(data) ? data : []);
      })
      .catch(() => setModels([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchModels();
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const current = models.find((m) => m.id === selectedModel) || models.find((m) => m.is_current);
  const displayModel = selectedModel || current?.id || '';

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => !disabled && setOpen((o) => !o)}
        disabled={disabled}
        className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors ${
          open
            ? 'bg-primary/20 border-primary/40'
            : 'bg-background-light/30 border-white/10 hover:border-primary/30'
        } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
      >
        <Cpu className="w-4 h-4 text-primary shrink-0" />
        {loading ? (
          <span className="text-sm text-text-muted">{t('agent.modelsLoading')}</span>
        ) : (
          <>
            <StatusDot status={current?.status ?? 'unknown'} />
            <span className="text-sm text-text truncate max-w-[140px]">
              {current?.name || displayModel || t('agent.selectModel')}
            </span>
            <ChevronDown
              className={`w-4 h-4 text-text-muted shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
            />
          </>
        )}
      </button>

      {open && !loading && (
        <div className="absolute top-full left-0 mt-2 w-64 max-h-72 overflow-y-auto glass-card rounded-xl border border-white/10 shadow-xl z-50 py-2">
          <div className="flex items-center justify-between px-3 py-1.5 mb-1">
            <span className="text-xs text-text-muted font-medium">{t('agent.modelSelector')}</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                fetchModels();
              }}
              className="p-1.5 rounded hover:bg-white/10 text-text-muted hover:text-text"
              title={t('agent.refreshModels')}
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
          {models.length === 0 ? (
            <div className="px-4 py-6 text-center text-sm text-text-muted">
              {t('agent.noModels')}
            </div>
          ) : (
            <div className="space-y-0.5">
              {models.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => {
                    onSelect(m.id);
                    setOpen(false);
                  }}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 text-left rounded-lg transition-colors ${
                    m.id === displayModel
                      ? 'bg-primary/20 text-primary'
                      : 'hover:bg-white/5 text-text'
                  }`}
                >
                  <StatusDot status={m.status} />
                  <span className="flex-1 truncate text-sm">{m.name}</span>
                  <span className="text-xs text-text-muted capitalize">{m.status}</span>
                  {m.id === displayModel && <Check className="w-4 h-4 shrink-0 text-primary" />}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
