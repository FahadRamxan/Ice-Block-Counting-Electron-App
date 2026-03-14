import { useState } from 'react';
import { Mail, Lock, User, LogIn, UserPlus, Sun, Moon, Languages } from 'lucide-react';
import './AuthPage.css';
import { useThemeLanguage } from './ThemeLanguageContext';

function IceCubeLogo() {
  return (
    <div className="ice-cube-scene" aria-hidden>
      <div className="ice-cube">
        <div className="ice-cube-face ice-cube-front" />
        <div className="ice-cube-face ice-cube-back" />
        <div className="ice-cube-face ice-cube-right" />
        <div className="ice-cube-face ice-cube-left" />
        <div className="ice-cube-face ice-cube-top" />
        <div className="ice-cube-face ice-cube-bottom" />
      </div>
    </div>
  );
}

type AuthMode = 'login' | 'signup';

type AuthPageProps = {
  onLogin: (user: { name: string; email: string }) => void;
};

export default function AuthPage({ onLogin }: AuthPageProps) {
  const { theme, setTheme, locale, setLocale, t } = useThemeLanguage();
  const [mode, setMode] = useState<AuthMode>('login');
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [signName, setSignName] = useState('');
  const [signEmail, setSignEmail] = useState('');
  const [signPassword, setSignPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!loginEmail.trim()) {
      setError(t('errEmail'));
      return;
    }
    if (!loginPassword) {
      setError(t('errPassword'));
      return;
    }
    setLoading(true);
    await new Promise((r) => setTimeout(r, 600));
    setLoading(false);
    onLogin({ name: loginEmail.split('@')[0], email: loginEmail });
  };

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!signName.trim()) {
      setError(t('errName'));
      return;
    }
    if (!signEmail.trim()) {
      setError(t('errEmail'));
      return;
    }
    if (!signPassword || signPassword.length < 6) {
      setError(t('errPasswordLen'));
      return;
    }
    setLoading(true);
    await new Promise((r) => setTimeout(r, 600));
    setLoading(false);
    onLogin({ name: signName.trim(), email: signEmail.trim() });
  };

  return (
    <div className="auth-page">
      <div className="auth-toolbar">
        <div className="shell-toggle-group" role="group" aria-label="Theme">
          <button
            type="button"
            className={theme === 'light' ? 'active' : ''}
            onClick={() => setTheme('light')}
            title={t('themeLight')}
          >
            <Sun size={16} /> {t('themeLight')}
          </button>
          <button
            type="button"
            className={theme === 'dark' ? 'active' : ''}
            onClick={() => setTheme('dark')}
            title={t('themeDark')}
          >
            <Moon size={16} /> {t('themeDark')}
          </button>
        </div>
        <div className="shell-toggle-group" role="group" aria-label="Language">
          <button
            type="button"
            className={locale === 'en' ? 'active' : ''}
            onClick={() => setLocale('en')}
          >
            <Languages size={16} /> {t('langEnglish')}
          </button>
          <button
            type="button"
            className={locale === 'ur' ? 'active' : ''}
            onClick={() => setLocale('ur')}
          >
            اردو
          </button>
        </div>
      </div>

      <div className="auth-left">
        <div className="auth-ice-blocks" aria-hidden>
          <div className="ice-block ice-block-1" />
          <div className="ice-block ice-block-2" />
          <div className="ice-block ice-block-3" />
          <div className="ice-block ice-block-4" />
          <div className="ice-block ice-block-5" />
          <div className="ice-block ice-block-6" />
        </div>
        <div className="auth-brand">
          <div className="auth-logo" aria-hidden>
            <IceCubeLogo />
          </div>
          <h1 className="auth-title">{t('authTitle')}</h1>
          <p className="auth-tagline">{t('authTagline')}</p>
        </div>
      </div>

      <div className="auth-right">
        <div className="auth-ice-blocks auth-ice-blocks-right" aria-hidden>
          <div className="ice-block ice-block-r1" />
          <div className="ice-block ice-block-r2" />
          <div className="ice-block ice-block-r3" />
          <div className="ice-block ice-block-r4" />
          <div className="ice-block ice-block-r5" />
          <div className="ice-block ice-block-r6" />
          <div className="ice-block ice-block-r7" />
          <div className="ice-block ice-block-r8" />
        </div>
        <div className="auth-form-wrap">
          <div className="auth-form-logo" aria-hidden>
            <IceCubeLogo />
          </div>
          <div className="auth-tabs">
            <button
              type="button"
              className={`auth-tab ${mode === 'login' ? 'active' : ''}`}
              onClick={() => {
                setMode('login');
                setError('');
              }}
            >
              <LogIn size={18} /> {t('logIn')}
            </button>
            <button
              type="button"
              className={`auth-tab ${mode === 'signup' ? 'active' : ''}`}
              onClick={() => {
                setMode('signup');
                setError('');
              }}
            >
              <UserPlus size={18} /> {t('signUp')}
            </button>
          </div>

          {error && (
            <div className="auth-error" role="alert">
              {error}
            </div>
          )}

          {mode === 'login' ? (
            <form onSubmit={handleLogin} className="auth-form">
              <label className="auth-label">
                <Mail size={18} />
                {t('email')}
              </label>
              <input
                type="email"
                className="auth-input"
                placeholder={t('phEmail')}
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                autoComplete="email"
              />
              <label className="auth-label">
                <Lock size={18} />
                {t('password')}
              </label>
              <input
                type="password"
                className="auth-input"
                placeholder="••••••••"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                autoComplete="current-password"
              />
              <button type="submit" className="auth-submit" disabled={loading}>
                {loading ? t('signingIn') : t('logIn')}
              </button>
            </form>
          ) : (
            <form onSubmit={handleSignup} className="auth-form">
              <label className="auth-label">
                <User size={18} />
                {t('name')}
              </label>
              <input
                type="text"
                className="auth-input"
                placeholder={t('phName')}
                value={signName}
                onChange={(e) => setSignName(e.target.value)}
                autoComplete="name"
              />
              <label className="auth-label">
                <Mail size={18} />
                {t('email')}
              </label>
              <input
                type="email"
                className="auth-input"
                placeholder={t('phEmail')}
                value={signEmail}
                onChange={(e) => setSignEmail(e.target.value)}
                autoComplete="email"
              />
              <label className="auth-label">
                <Lock size={18} />
                {t('password')}
              </label>
              <input
                type="password"
                className="auth-input"
                placeholder={t('phPasswordNew')}
                value={signPassword}
                onChange={(e) => setSignPassword(e.target.value)}
                autoComplete="new-password"
              />
              <button type="submit" className="auth-submit" disabled={loading}>
                {loading ? t('creatingAccount') : t('signUp')}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
