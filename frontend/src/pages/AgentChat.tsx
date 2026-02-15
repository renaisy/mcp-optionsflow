/**
 * Agent Chat page - LLM conversation with options/strategy tools
 */
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  MessageSquare,
  Send,
  Loader2,
  PlusCircle,
  Sparkles,
  History,
  Trash2,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { agentAPI } from '../services/api';
import {
  StrategyResultCard,
  PnlScenarioCard,
  FindBestCard,
  CompareResultsCard,
  StockInfoCard,
} from '../components/strategy/StrategyCards';
import { MarkdownMessage } from '../components/agent/MarkdownMessage';
import { ModelSelector } from '../components/agent/ModelSelector';
import { useAgentConversations } from '../hooks/useAgentConversations';
import type { StrategyAnalysisResult } from '../types/strategy';

interface ToolResult {
  tool: string;
  data: unknown;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: string[];
  toolResults?: ToolResult[];
}

export const AgentChat: React.FC = () => {
  const { t } = useTranslation();
  const {
    conversations,
    activeId,
    active,
    sidebarOpen,
    toggleSidebar,
    createNew,
    selectConversation,
    saveMessages,
    deleteConversation,
  } = useAgentConversations();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Sync messages from active conversation
  useEffect(() => {
    if (active) {
      setMessages(active.messages);
    } else {
      setMessages([]);
    }
    setError(null);
  }, [active?.id]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const persistMessages = useCallback(
    (msgs: Message[], firstUserContent?: string) => {
      if (activeId) {
        saveMessages(activeId, msgs, firstUserContent);
      }
    },
    [activeId, saveMessages]
  );

  const handleSend = () => {
    const text = input.trim();
    if (!text || loading) return;

    const streamConvId = activeId;
    const userMsg: Message = { role: 'user', content: text };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInput('');
    setLoading(true);
    setError(null);
    // Persist immediately with new title from first user message if this is first
    if (messages.length === 0) {
      persistMessages(nextMessages, text);
    }

    const chatMessages = nextMessages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    let assistantContent = '';
    const toolCalls: string[] = [];
    const toolResults: ToolResult[] = [];

    agentAPI.chatStream(
      chatMessages,
      (event) => {
      if (event.type === 'error') {
        setError(event.message || 'Unknown error');
        setLoading(false);
        return;
      }
      if (event.type === 'done') {
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          const finalMsg: Message = {
            role: 'assistant',
            content: assistantContent,
            toolCalls: toolCalls.length ? [...toolCalls] : undefined,
            toolResults: toolResults.length ? [...toolResults] : undefined,
          };
          if (last?.role === 'assistant') {
            next[next.length - 1] = finalMsg;
          } else {
            next.push(finalMsg);
          }
          if (streamConvId) saveMessages(streamConvId, next);
          return next;
        });
        setLoading(false);
        return;
      }
      if (event.type === 'tool_call' && event.tool) {
        toolCalls.push(event.tool);
        return;
      }
      if (event.type === 'tool_result' && event.tool && event.data != null) {
        toolResults.push({ tool: event.tool, data: event.data });
        return;
      }
      if (event.type === 'chunk' && event.content) {
        assistantContent += event.content;
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          const msg: Message = {
            role: 'assistant',
            content: assistantContent,
            toolCalls: toolCalls.length ? [...toolCalls] : undefined,
            toolResults: toolResults.length ? [...toolResults] : undefined,
          };
          if (last?.role === 'assistant') {
            next[next.length - 1] = msg;
          } else {
            next.push(msg);
          }
          return next;
        });
      }
    },
      { model: selectedModel || undefined }
    ).catch((e) => {
      setError(e?.message || 'Request failed');
      setLoading(false);
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewChat = () => {
    createNew();
    setMessages([]);
    setError(null);
  };

  const handleDeleteConversation = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    deleteConversation(id);
  };

  const formatDate = (ts: number) => {
    const d = new Date(ts);
    const now = new Date();
    const sameDay = d.toDateString() === now.toDateString();
    if (sameDay) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4 animate-fade-in">
      {/* History sidebar */}
      <aside
        className={`flex flex-col shrink-0 transition-all duration-200 ease-out ${
          sidebarOpen ? 'w-52' : 'w-0 overflow-hidden'
        }`}
      >
          {sidebarOpen && (
            <>
              <div className="flex items-center justify-between h-10 mb-3">
                <span className="text-sm font-medium text-text-secondary flex items-center gap-2">
                  <History className="w-4 h-4 shrink-0" />
                  <span className="truncate">{t('agent.history')}</span>
                </span>
                <button
                  onClick={toggleSidebar}
                  className="p-1.5 rounded-lg hover:bg-white/10 text-text-muted shrink-0"
                  title={sidebarOpen ? t('agent.hideHistory') : t('agent.showHistory')}
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
              </div>
              <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
                <div className="flex-1 min-h-0 overflow-y-auto space-y-1.5 glass-card rounded-xl p-2">
                  {conversations.map((c) => (
                    <div
                      key={c.id}
                      onClick={() => selectConversation(c.id)}
                      className={`group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors border ${
                        c.id === activeId
                          ? 'bg-primary/20 border-primary/30'
                          : 'border-transparent hover:bg-white/5 hover:border-white/5'
                      }`}
                    >
                      <span
                        className="flex-1 min-w-0 truncate text-sm text-text"
                        title={c.title || t('agent.newChat')}
                      >
                        {c.title || t('agent.newChat')}
                      </span>
                      <span className="text-xs text-text-muted shrink-0 tabular-nums">
                        {formatDate(c.updatedAt)}
                      </span>
                      <button
                        onClick={(e) => handleDeleteConversation(e, c.id)}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-functional-danger/20 text-functional-danger shrink-0 transition-opacity"
                        title={t('agent.deleteConversation')}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
      </aside>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header row */}
        <div className="flex items-center justify-between h-10 mb-4 gap-4">
          <div className="flex items-center gap-2 min-w-0 shrink">
            {!sidebarOpen && (
                <button
                  onClick={toggleSidebar}
                  className="p-2 rounded-lg hover:bg-white/10 text-text-muted shrink-0"
                  title={t('agent.showHistory')}
                >
                <ChevronRight className="w-5 h-5" />
            </button>
            )}
            <h1 className="text-xl font-bold text-text flex items-center gap-2 shrink-0">
              <MessageSquare className="w-6 h-6 text-primary shrink-0" />
              <span className="truncate">{t('agent.title')}</span>
            </h1>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <ModelSelector
              selectedModel={selectedModel}
              onSelect={setSelectedModel}
              disabled={loading}
            />
            <button
              onClick={handleNewChat}
              className="btn-secondary flex items-center gap-2 shrink-0"
            >
              <PlusCircle className="w-4 h-4" />
              {t('agent.newChat')}
            </button>
          </div>
        </div>

        {/* Chat card */}
        <div className="flex-1 flex flex-col min-h-0 glass-card rounded-xl overflow-hidden">
          <div className="flex-1 min-h-0 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-64 text-center px-6">
              <div className="p-4 rounded-2xl bg-primary/10 mb-6">
                <Sparkles className="w-12 h-12 text-primary" />
              </div>
              <p className="text-lg font-medium text-text-secondary mb-2">
                {t('agent.placeholder')}
              </p>
              <p className="text-sm text-text-muted max-w-md">
                {t('settings.configRequired')}{' '}
                <Link to="/settings" className="text-primary hover:underline font-medium">
                  {t('agent.goToSettings')}
                </Link>
              </p>
            </div>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-xl px-4 py-3 ${
                  m.role === 'user'
                    ? 'bg-primary/20 border border-primary/30 text-text'
                    : 'bg-background-light/40 border border-white/10 text-text'
                }`}
              >
                {m.toolCalls && m.toolCalls.length > 0 && (
                  <div className="text-xs text-text-muted mb-2 space-y-0.5">
                    {m.toolCalls.map((tc, j) => (
                      <div key={j}>Used: {tc}</div>
                    ))}
                  </div>
                )}
                {m.toolResults && m.toolResults.length > 0 && (
                  <div className="space-y-4 mb-4">
                    {m.toolResults.map((tr, j) => (
                      <div key={j}>
                        {tr.tool === 'get_stock_info' && (
                          <StockInfoCard data={tr.data as Record<string, unknown>} />
                        )}
                        {tr.tool === 'analyze_strategy' && (
                          <StrategyResultCard result={tr.data as StrategyAnalysisResult} />
                        )}
                        {tr.tool === 'compare_strategies' && Array.isArray(tr.data) && (
                          <CompareResultsCard results={tr.data as StrategyAnalysisResult[]} />
                        )}
                        {tr.tool === 'find_best_strategies' && (
                          <FindBestCard data={tr.data as Record<string, unknown>} />
                        )}
                        {tr.tool === 'analyze_pnl_scenarios' && (
                          <PnlScenarioCard data={tr.data as Record<string, unknown>} />
                        )}
                      </div>
                    ))}
                  </div>
                )}
                <div className="text-sm">
                  {m.role === 'user' ? (
                    <div className="whitespace-pre-wrap break-words">{m.content}</div>
                  ) : m.role === 'assistant' && m.content ? (
                    <MarkdownMessage
                      content={m.content}
                      isStreaming={loading && i === messages.length - 1}
                    />
                  ) : m.role === 'assistant' && !m.content && loading && i === messages.length - 1 ? (
                    <span className="flex items-center gap-2 text-text-muted">
                      <Loader2 className="w-4 h-4 animate-spin" />{t('agent.thinking')}
                    </span>
                  ) : null}
                </div>
              </div>
            </div>
          ))}
          {loading && messages[messages.length - 1]?.role === 'user' && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-xl px-4 py-3 bg-background-light/40 border border-white/10">
                <span className="flex items-center gap-2 text-text-muted text-sm">
                  <Loader2 className="w-4 h-4 animate-spin" />{t('agent.thinking')}
                </span>
              </div>
            </div>
          )}
          <div ref={scrollRef} />
          </div>

          {error && (
            <div className="mx-6 mb-2 px-4 py-2 rounded-lg bg-functional-danger/10 border border-functional-danger/30 text-functional-danger text-sm">
              {error}
            </div>
          )}

          <div className="p-4 border-t border-white/10 shrink-0">
            <div className="flex gap-3">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t('agent.placeholder')}
                disabled={loading}
                rows={2}
                className="input-field flex-1 resize-none disabled:opacity-50"
              />
              <button
                onClick={handleSend}
                disabled={loading || !input.trim()}
                className="btn-primary px-5 py-3 rounded-xl self-end disabled:opacity-50 flex items-center gap-2 min-w-[88px] h-[52px] justify-center text-sm font-medium"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 shrink-0 animate-spin" />
                ) : (
                  <Send className="w-4 h-4 shrink-0" />
                )}
                {t('agent.send')}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
