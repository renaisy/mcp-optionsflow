/**
 * Header component with language switcher
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { TrendingUp, User, LogOut, Menu, Globe } from 'lucide-react';
import { useAuthStore, useUIStore } from '../../store';
import { SUPPORTED_LANGS, type SupportedLang } from '../../i18n';

const LANG_LABELS: Record<SupportedLang, string> = {
  en: 'English',
  zh: '中文',
};

export const Header: React.FC = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const { user, logout } = useAuthStore();
  const { toggleSidebar } = useUIStore();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const changeLang = (lng: SupportedLang) => {
    i18n.changeLanguage(lng);
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-16 bg-background/80 backdrop-blur-md border-b border-white/10">
      <div className="h-full px-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={toggleSidebar}
            className="p-2 hover:bg-background-light rounded-lg transition-colors"
          >
            <Menu className="w-5 h-5 text-text" />
          </button>
          <div
            className="flex items-center gap-2 cursor-pointer"
            onClick={() => navigate('/')}
          >
            <TrendingUp className="w-8 h-8 text-primary" />
            <h1 className="text-xl font-bold gradient-text">海山云创OptionsFlow平台</h1>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Language switcher */}
          <div className="flex items-center gap-1 rounded-lg border border-white/10 overflow-hidden bg-background-light/50">
            <Globe className="w-4 h-4 text-text-muted ml-2" />
            {SUPPORTED_LANGS.map((lng) => (
              <button
                key={lng}
                onClick={() => changeLang(lng)}
                className={`px-3 py-2 text-sm transition-colors ${
                  i18n.language === lng || i18n.language.startsWith(lng)
                    ? 'bg-primary/20 text-primary'
                    : 'text-text-secondary hover:text-text'
                }`}
                title={LANG_LABELS[lng]}
              >
                {LANG_LABELS[lng]}
              </button>
            ))}
          </div>

          {user && (
            <>
              <div className="flex items-center gap-2 px-4 py-2 glass-card">
                <User className="w-4 h-4 text-primary" />
                <span className="text-sm text-text-secondary">{user.username}</span>
              </div>
              <button
                onClick={handleLogout}
                className="p-2 hover:bg-background-light rounded-lg transition-colors"
                title={t('nav.logout')}
              >
                <LogOut className="w-5 h-5 text-text-muted hover:text-functional-danger" />
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  );
};
