import { useState } from 'react';
import { Mail, Lock, User, LogIn, UserPlus } from 'lucide-react';
import './AuthPage.css';

/** Shared logo: 3D ice cube rotating like a Rubik's cube (left brand + right form). */
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
      setError('Please enter your email.');
      return;
    }
    if (!loginPassword) {
      setError('Please enter your password.');
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
      setError('Please enter your name.');
      return;
    }
    if (!signEmail.trim()) {
      setError('Please enter your email.');
      return;
    }
    if (!signPassword || signPassword.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }
    setLoading(true);
    await new Promise((r) => setTimeout(r, 600));
    setLoading(false);
    onLogin({ name: signName.trim(), email: signEmail.trim() });
  };

  return (
    <div className="auth-page">
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
          <h1 className="auth-title">Awan Ice Block Counter</h1>
          <p className="auth-tagline">Count and track ice blocks across your factory</p>
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
              onClick={() => { setMode('login'); setError(''); }}
            >
              <LogIn size={18} /> Log in
            </button>
            <button
              type="button"
              className={`auth-tab ${mode === 'signup' ? 'active' : ''}`}
              onClick={() => { setMode('signup'); setError(''); }}
            >
              <UserPlus size={18} /> Sign up
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
                Email
              </label>
              <input
                type="email"
                className="auth-input"
                placeholder="you@company.com"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                autoComplete="email"
              />
              <label className="auth-label">
                <Lock size={18} />
                Password
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
                {loading ? 'Signing in…' : 'Log in'}
              </button>
            </form>
          ) : (
            <form onSubmit={handleSignup} className="auth-form">
              <label className="auth-label">
                <User size={18} />
                Name
              </label>
              <input
                type="text"
                className="auth-input"
                placeholder="Your name"
                value={signName}
                onChange={(e) => setSignName(e.target.value)}
                autoComplete="name"
              />
              <label className="auth-label">
                <Mail size={18} />
                Email
              </label>
              <input
                type="email"
                className="auth-input"
                placeholder="you@company.com"
                value={signEmail}
                onChange={(e) => setSignEmail(e.target.value)}
                autoComplete="email"
              />
              <label className="auth-label">
                <Lock size={18} />
                Password
              </label>
              <input
                type="password"
                className="auth-input"
                placeholder="At least 6 characters"
                value={signPassword}
                onChange={(e) => setSignPassword(e.target.value)}
                autoComplete="new-password"
              />
              <button type="submit" className="auth-submit" disabled={loading}>
                {loading ? 'Creating account…' : 'Sign up'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
