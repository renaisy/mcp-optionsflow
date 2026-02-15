/**
 * Hook for agent chat conversation history (localStorage)
 */
import { useState, useCallback, useEffect } from 'react';

export interface ConversationMessage {
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: string[];
  toolResults?: Array<{ tool: string; data: unknown }>;
}

export interface StoredConversation {
  id: string;
  title: string;
  messages: ConversationMessage[];
  updatedAt: number;
}

const STORAGE_KEY = 'agent-chat-conversations';
const MAX_TITLE_LEN = 36;

function generateId(): string {
  return `conv_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function titleFromFirstMessage(content: string): string {
  const trimmed = content.trim();
  if (!trimmed) return 'New Chat';
  if (trimmed.length <= MAX_TITLE_LEN) return trimmed;
  return trimmed.slice(0, MAX_TITLE_LEN) + '…';
}

function loadConversations(): StoredConversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

function saveConversations(list: StoredConversation[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch (e) {
    console.warn('Failed to save conversations:', e);
  }
}

export function useAgentConversations() {
  const [conversations, setConversations] = useState<StoredConversation[]>(loadConversations);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const active = conversations.find((c) => c.id === activeId) ?? null;

  const persist = useCallback((list: StoredConversation[]) => {
    setConversations(list);
    saveConversations(list);
  }, []);

  const createNew = useCallback(() => {
    const id = generateId();
    const conv: StoredConversation = {
      id,
      title: 'New Chat',
      messages: [],
      updatedAt: Date.now(),
    };
    setConversations((prev) => {
      const next = [conv, ...prev];
      saveConversations(next);
      return next;
    });
    setActiveId(id);
    return id;
  }, []);

  const selectConversation = useCallback((id: string) => {
    setActiveId(id);
  }, []);

  const updateConversation = useCallback(
    (id: string, updater: (c: StoredConversation) => Partial<StoredConversation>) => {
      setConversations((prev) => {
        const next = prev.map((c) =>
          c.id === id ? { ...c, ...updater(c), updatedAt: Date.now() } : c
        );
        saveConversations(next);
        return next;
      });
    },
    []
  );

  const saveMessages = useCallback(
    (id: string, messages: ConversationMessage[], firstUserContent?: string) => {
      updateConversation(id, (c) => {
        const title =
          firstUserContent !== undefined
            ? titleFromFirstMessage(firstUserContent)
            : c.messages.length === 0 && messages.length > 0
              ? titleFromFirstMessage(messages[0]?.content ?? '')
              : c.title;
        return { messages, title };
      });
    },
    [updateConversation]
  );

  const deleteConversation = useCallback(
    (id: string) => {
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== id);
        saveConversations(next);
        if (activeId === id) {
          setActiveId(next[0]?.id ?? null);
        }
        return next;
      });
    },
    [activeId]
  );

  const ensureActive = useCallback(() => {
    if (conversations.length === 0) {
      createNew();
    } else if (!activeId || !conversations.some((c) => c.id === activeId)) {
      setActiveId(conversations[0].id);
    }
  }, [conversations, activeId, createNew]);

  useEffect(() => {
    ensureActive();
  }, [ensureActive]);

  const toggleSidebar = useCallback(() => setSidebarOpen((o) => !o), []);

  return {
    conversations,
    activeId,
    active,
    sidebarOpen,
    toggleSidebar,
    createNew,
    selectConversation,
    saveMessages,
    deleteConversation,
    updateConversation,
  };
}
