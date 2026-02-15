/**
 * Sidebar component
 */
import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  LayoutDashboard,
  LineChart,
  Calculator,
  MessageSquare,
  TrendingUp,
  History,
  Settings,
} from 'lucide-react';
import { useUIStore } from '../../store';

const menuPaths = [
  { path: '/', icon: LayoutDashboard, labelKey: 'nav.dashboard' as const },
  { path: '/options', icon: LineChart, labelKey: 'nav.optionsChain' as const },
  { path: '/strategies', icon: Calculator, labelKey: 'nav.strategyAnalysis' as const },
  { path: '/chat', icon: MessageSquare, labelKey: 'nav.agent' as const },
  { path: '/greeks', icon: TrendingUp, labelKey: 'nav.greeksVisualizer' as const },
  { path: '/history', icon: History, labelKey: 'nav.history' as const },
  { path: '/settings', icon: Settings, labelKey: 'nav.settings' as const },
];

export const Sidebar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const { sidebarOpen } = useUIStore();

  if (!sidebarOpen) return null;

  return (
    <aside className="fixed left-0 top-16 bottom-0 w-64 bg-background-light/50 backdrop-blur-md border-r border-white/10 z-40">
      <nav className="p-4 space-y-2">
        {menuPaths.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                isActive
                  ? 'bg-primary/10 text-primary border-l-2 border-primary'
                  : 'text-text-secondary hover:bg-background-light hover:text-text'
              }`}
            >
              <Icon className="w-5 h-5" />
              <span className="font-medium">{t(item.labelKey)}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
};
