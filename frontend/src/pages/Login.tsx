/**
 * Login page
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { TrendingUp, Eye, EyeOff } from 'lucide-react';
import { useAuthStore } from '../store';

export const Login: React.FC = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { login, register } = useAuthStore();
  const [isLogin, setIsLogin] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isLogin) {
        await login(formData.username, formData.password);
        navigate('/');
      } else {
        if (formData.password !== formData.confirmPassword) {
          setError('Passwords do not match');
          setLoading(false);
          return;
        }
        await register(formData.username, formData.email, formData.password);
        navigate('/');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setError('');
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-md glass-card p-8 animate-slide-up">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <TrendingUp className="w-16 h-16 text-primary neon-glow p-3 rounded-xl bg-background-light/50" />
          </div>
          <h1 className="text-3xl font-bold gradient-text">{t('login.title')}</h1>
          <p className="text-text-muted mt-2">{t('login.subtitle')}</p>
        </div>

        <div className="flex mb-6 bg-background-light/50 rounded-lg p-1">
          <button
            onClick={() => setIsLogin(true)}
            className={`flex-1 py-2 rounded-md transition-all ${
              isLogin ? 'bg-primary text-white' : 'text-text-secondary'
            }`}
          >
            {t('login.login')}
          </button>
          <button
            onClick={() => setIsLogin(false)}
            className={`flex-1 py-2 rounded-md transition-all ${
              !isLogin ? 'bg-primary text-white' : 'text-text-secondary'
            }`}
          >
            {t('login.register')}
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">
              {t('login.username')}
            </label>
            <input
              type="text"
              name="username"
              value={formData.username}
              onChange={handleChange}
              className="input-field"
              placeholder={t('login.enterUsername')}
              required
            />
          </div>

          {!isLogin && (
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">
                {t('login.email')}
              </label>
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                className="input-field"
                placeholder={t('login.enterEmail')}
                required={!isLogin}
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">
              {t('login.password')}
            </label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                name="password"
                value={formData.password}
                onChange={handleChange}
                className="input-field pr-10"
                placeholder={t('login.enterPassword')}
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text"
              >
                {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>

          {!isLogin && (
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">
                {t('login.confirmPassword')}
              </label>
              <input
                type={showPassword ? 'text' : 'password'}
                name="confirmPassword"
                value={formData.confirmPassword}
                onChange={handleChange}
                className="input-field"
                placeholder={t('login.confirmPasswordPlaceholder')}
                required={!isLogin}
              />
            </div>
          )}

          {error && (
            <div className="p-3 bg-functional-danger/10 border border-functional-danger/30 rounded-lg">
              <p className="text-sm text-functional-danger">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? t('login.pleaseWait') : isLogin ? t('login.login') : t('login.register')}
          </button>
        </form>

        <p className="text-center text-text-muted text-sm mt-6">
          {isLogin ? t('login.noAccount') : t('login.hasAccount')}
          <button
            onClick={() => setIsLogin(!isLogin)}
            className="text-primary hover:underline"
          >
            {isLogin ? t('login.register') : t('login.login')}
          </button>
        </p>
      </div>
    </div>
  );
};
