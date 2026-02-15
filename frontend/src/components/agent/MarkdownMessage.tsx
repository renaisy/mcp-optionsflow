/**
 * Renders assistant message with formatted markdown preview and collapsible raw MD
 */
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChevronDown, ChevronRight, FileCode } from 'lucide-react';

interface MarkdownMessageProps {
  content: string;
  isStreaming?: boolean;
}

const markdownComponents: React.ComponentProps<typeof ReactMarkdown>['components'] = {
  h1: ({ children }) => <h1 className="text-xl font-bold text-text mt-4 mb-2 first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="text-lg font-semibold text-text mt-4 mb-2">{children}</h2>,
  h3: ({ children }) => <h3 className="text-base font-semibold text-text mt-3 mb-1">{children}</h3>,
  p: ({ children }) => <p className="text-sm text-text-secondary mb-2 last:mb-0 leading-relaxed">{children}</p>,
  ul: ({ children }) => <ul className="list-disc list-inside text-sm text-text-secondary mb-2 space-y-1">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal list-inside text-sm text-text-secondary mb-2 space-y-1">{children}</ol>,
  li: ({ children }) => <li className="text-text-secondary">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-primary/50 pl-4 my-2 text-text-muted italic">
      {children}
    </blockquote>
  ),
  code: ({ className, children, ...props }) => {
    const isBlock = className?.includes('language-');
    if (isBlock) {
      return (
        <pre className="bg-background/80 rounded-lg p-4 my-2 overflow-x-auto border border-white/10">
          <code className="text-sm font-mono text-text" {...props}>{children}</code>
        </pre>
      );
    }
    return (
      <code className="bg-background/60 px-1.5 py-0.5 rounded text-primary font-mono text-xs" {...props}>
        {children}
      </code>
    );
  },
  pre: ({ children }) => <>{children}</>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
      {children}
    </a>
  ),
  strong: ({ children }) => <strong className="font-semibold text-text">{children}</strong>,
  table: ({ children }) => (
    <div className="overflow-x-auto my-3 rounded-lg border border-white/10">
      <table className="min-w-full text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-background-light/50">{children}</thead>,
  tbody: ({ children }) => <tbody className="divide-y divide-white/5">{children}</tbody>,
  tr: ({ children }) => <tr className="hover:bg-background-light/30">{children}</tr>,
  th: ({ children }) => <th className="px-4 py-2 text-left text-text-secondary font-medium">{children}</th>,
  td: ({ children }) => <td className="px-4 py-2 text-text-secondary">{children}</td>,
  hr: () => <hr className="border-white/10 my-4" />,
};

export const MarkdownMessage: React.FC<MarkdownMessageProps> = ({ content, isStreaming = false }) => {
  const { t } = useTranslation();
  const [rawExpanded, setRawExpanded] = useState(false);
  const hasContent = content.trim().length > 0;
  const showRawToggle = hasContent && !isStreaming;

  return (
    <div className="space-y-3">
      <div className="prose-sm prose-invert max-w-none">
        {hasContent ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {content}
          </ReactMarkdown>
        ) : null}
      </div>

      {showRawToggle && (
        <div className="mt-3 pt-3 border-t border-white/10">
          <button
            type="button"
            onClick={() => setRawExpanded((v) => !v)}
            className="flex items-center gap-2 text-xs text-text-muted hover:text-primary transition-colors"
          >
            {rawExpanded ? (
              <ChevronDown className="w-3.5 h-3.5" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5" />
            )}
            <FileCode className="w-3.5 h-3.5" />
            {t('agent.rawMarkdown')} ({rawExpanded ? t('agent.hideRaw') : t('agent.showRaw')})
          </button>
          {rawExpanded && (
            <pre className="mt-2 p-3 rounded-lg bg-background/80 border border-white/10 text-xs text-text-muted overflow-x-auto max-h-48 overflow-y-auto whitespace-pre-wrap break-words">
              {content}
            </pre>
          )}
        </div>
      )}
    </div>
  );
};
