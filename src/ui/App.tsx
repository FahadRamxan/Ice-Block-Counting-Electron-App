import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Play,
  Loader2,
  XCircle,
  Blocks,
  Server,
  Film,
  Home,
  Trash2,
  Plus,
  Calendar,
  ChevronRight,
  ChevronDown,
  Sun,
  Moon,
  LogOut,
} from 'lucide-react';
import { useThemeLanguage } from './ThemeLanguageContext';
import { api, nvrs as nvrsApi, recordings as recordingsApi, runs, type TestVideoRunResult } from './lib/api';
import type { RecordingSlot } from './lib/api';
import AuthPage from './AuthPage';
import FloatingIceBackdrop from './FloatingIceBackdrop';
import './index.css';

const AUTH_STORAGE_KEY = 'awan_ice_user';

type Page = 'home' | 'nvrs' | 'recordings' | 'test';

function getStoredUser(): { name: string; email: string } | null {
  try {
    const s = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!s) return null;
    const u = JSON.parse(s) as { name?: string; email?: string };
    return u?.name && u?.email ? { name: u.name, email: u.email } : null;
  } catch {
    return null;
  }
}

export default function App() {
  const { t, theme, setTheme, locale, setLocale } = useThemeLanguage();
  const [user, setUser] = useState<{ name: string; email: string } | null>(getStoredUser);
  const [page, setPage] = useState<Page>('home');
  const [backendDown, setBackendDown] = useState(false);
  const [loading, setLoading] = useState(true);

  // NVRs
  const [nvrList, setNvrList] = useState<{ id: number; name: string; ip: string; port: number; username: string; created_at: string }[]>([]);
  const [nvrLoading, setNvrLoading] = useState(false);
  const [nvrForm, setNvrForm] = useState({ name: '', ip: '', port: 37777, username: '', password: '' });
  const [nvrError, setNvrError] = useState<string | null>(null);

  // Recordings
  const [recNvrId, setRecNvrId] = useState<number | ''>('');
  const [recDate, setRecDate] = useState(() => new Date().toISOString().slice(0, 10));
  /** Cameras 1–15 (UI); API uses 0–14. */
  const [recChannelsSelected, setRecChannelsSelected] = useState<number[]>(() =>
    Array.from({ length: 15 }, (_, i) => i + 1),
  );
  const [channelMenuOpen, setChannelMenuOpen] = useState(false);
  const channelMenuRef = useRef<HTMLDivElement>(null);
  const [runForDateMsg, setRunForDateMsg] = useState<string | null>(null);
  const [recLoading, setRecLoading] = useState(false);
  const [recData, setRecData] = useState<Awaited<ReturnType<typeof recordingsApi.byDate>> | null>(null);
  const [recError, setRecError] = useState<string | null>(null);

  // Test model
  const [solutionVideoPath, setSolutionVideoPath] = useState('');
  const [solutionRunning, setSolutionRunning] = useState(false);
  const [solutionError, setSolutionError] = useState<string | null>(null);
  const [solutionResult, setSolutionResult] = useState<TestVideoRunResult | null>(null);
  const [runProgress, setRunProgress] = useState<{ done: number; total: number; pct: number; line: string } | null>(null);
  const [maxFrames, setMaxFrames] = useState(100);
  const [accountOpen, setAccountOpen] = useState(false);
  const accountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!accountOpen) return;
    const onDown = (e: MouseEvent) => {
      if (accountRef.current && !accountRef.current.contains(e.target as Node)) setAccountOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setAccountOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [accountOpen]);

  useEffect(() => {
    if (!channelMenuOpen) return;
    const onDown = (e: MouseEvent) => {
      if (channelMenuRef.current && !channelMenuRef.current.contains(e.target as Node)) setChannelMenuOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [channelMenuOpen]);

  const loadNvrs = useCallback(async () => {
    setNvrLoading(true);
    setNvrError(null);
    try {
      const list = await nvrsApi.list();
      setNvrList(list);
      setRecNvrId((prev) => (prev === '' && list.length ? list[0].id : prev));
    } catch (e) {
      setNvrError((e as Error).message);
    } finally {
      setNvrLoading(false);
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    api<{ status: string }>('/api/status')
      .then(() => mounted && setBackendDown(false))
      .catch(() => mounted && setBackendDown(true));
    setLoading(false);
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (user && (page === 'nvrs' || page === 'recordings')) loadNvrs();
  }, [user, page, loadNvrs]);

  const handleAddNvr = async () => {
    if (!nvrForm.ip.trim()) {
      setNvrError(t('ipRequired'));
      return;
    }
    setNvrError(null);
    try {
      await nvrsApi.add({
        name: nvrForm.name.trim() || 'NVR',
        ip: nvrForm.ip.trim(),
        port: nvrForm.port,
        username: nvrForm.username,
        password: nvrForm.password,
      });
      setNvrForm({ name: '', ip: '', port: 37777, username: '', password: '' });
      await loadNvrs();
    } catch (e) {
      setNvrError((e as Error).message);
    }
  };

  const handleDeleteNvr = async (id: number) => {
    if (!confirm(t('confirmRemoveNvr'))) return;
    try {
      await nvrsApi.delete(id);
      await loadNvrs();
      if (recNvrId === id) setRecNvrId(nvrList.find((n) => n.id !== id)?.id ?? '');
    } catch (e) {
      setNvrError((e as Error).message);
    }
  };

  const loadRecordings = async () => {
    if (recNvrId === '' || !recDate) return;
    if (recChannelsSelected.length === 0) {
      setRecError(t('channelsPickOne'));
      return;
    }
    setRecLoading(true);
    setRecError(null);
    setRecData(null);
    setRunForDateMsg(null);
    try {
      const zeroBased = [...recChannelsSelected].sort((a, b) => a - b).map((c) => c - 1);
      const data = await recordingsApi.byDate(Number(recNvrId), recDate, zeroBased);
      setRecData(data);
    } catch (e) {
      setRecError((e as Error).message);
    } finally {
      setRecLoading(false);
    }
  };

  const toggleRecChannel = (ch: number) => {
    setRecChannelsSelected((prev) =>
      prev.includes(ch) ? prev.filter((c) => c !== ch) : [...prev, ch].sort((a, b) => a - b),
    );
  };

  const runModelOnSelection = async () => {
    if (recNvrId === '' || !recDate || recChannelsSelected.length === 0) {
      setRunForDateMsg(t('channelsPickOne'));
      return;
    }
    setRunForDateMsg(null);
    try {
      const r = await runs.runForDate({
        date: recDate,
        nvr_id: Number(recNvrId),
        channels: recChannelsSelected,
      });
      setRunForDateMsg(r.message || t('runModelChannelsStub'));
    } catch (e) {
      setRunForDateMsg((e as Error).message);
    }
  };

  const handleRunSolutionVideo = async () => {
    const path = solutionVideoPath.trim();
    if (!path) {
      setSolutionError(t('enterVideoPath'));
      return;
    }
    setSolutionError(null);
    setSolutionResult(null);
    setRunProgress(null);
    setSolutionRunning(true);
    try {
      await runs.testVideo(path, maxFrames > 0 ? maxFrames : null);
      const poll = async () => {
        const j = (await runs.jobProgress()) as {
          running: boolean;
          error: string | null;
          result?: TestVideoRunResult | null;
          frames_done?: number;
          frames_total?: number;
          percent?: number;
          current?: string | null;
        };
        if (j.frames_total) {
          setRunProgress({
            done: j.frames_done || 0,
            total: j.frames_total,
            pct: j.percent ?? 0,
            line: j.current || '',
          });
        }
        if (!j.running) {
          setSolutionRunning(false);
          setRunProgress(null);
          if (j.error) setSolutionError(j.error);
          else if (j.result) setSolutionResult(j.result as TestVideoRunResult);
          return true;
        }
        return false;
      };
      while (!(await poll())) {
        await new Promise((r) => setTimeout(r, 800));
      }
    } catch (e) {
      setSolutionRunning(false);
      setSolutionError((e as Error).message);
    }
  };

  const handleLogin = (loggedInUser: { name: string; email: string }) => {
    setUser(loggedInUser);
    try {
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(loggedInUser));
    } catch (_) {}
  };

  const handleLogout = () => {
    setUser(null);
    try {
      localStorage.removeItem(AUTH_STORAGE_KEY);
    } catch (_) {}
  };

  if (!user) return <AuthPage onLogin={handleLogin} />;
  if (loading) {
    return (
      <div className="app app-shell">
        <FloatingIceBackdrop />
        <main className="shell-main" style={{ display: 'flex', justifyContent: 'center', padding: 48, zIndex: 1 }}>
          <Loader2 size={40} className="spin" />
        </main>
      </div>
    );
  }

  return (
    <div className="app app-shell">
      <FloatingIceBackdrop />
      <header className="shell-header">
        <div className="shell-header-bar">
          <button type="button" className="shell-brand" onClick={() => setPage('home')}>
            <Blocks size={26} className="shell-brand-icon" aria-hidden />
            <span className="shell-brand-text">{t('brandIceFactory')}</span>
          </button>
          <nav className="shell-nav" aria-label="Main">
            <button type="button" className={page === 'home' ? 'active' : ''} onClick={() => setPage('home')}>
              <Home size={18} /> {t('navHome')}
            </button>
            <button type="button" className={page === 'nvrs' ? 'active' : ''} onClick={() => setPage('nvrs')}>
              <Server size={18} /> {t('navNvrs')}
            </button>
            <button type="button" className={page === 'recordings' ? 'active' : ''} onClick={() => setPage('recordings')}>
              <Film size={18} /> {t('navRecordings')}
            </button>
            <button type="button" className={page === 'test' ? 'active' : ''} onClick={() => setPage('test')}>
              <Play size={18} /> {t('navTestModel')}
            </button>
          </nav>
          <div className="shell-toolbar" aria-label="Display">
            <div className="shell-toggle-group shell-toggle-compact" role="group" aria-label={t('themeLight')}>
              <button
                type="button"
                className={theme === 'light' ? 'active' : ''}
                onClick={() => setTheme('light')}
                title={t('themeLight')}
                aria-label={t('themeLight')}
              >
                <Sun size={17} />
              </button>
              <button
                type="button"
                className={theme === 'dark' ? 'active' : ''}
                onClick={() => setTheme('dark')}
                title={t('themeDark')}
                aria-label={t('themeDark')}
              >
                <Moon size={17} />
              </button>
            </div>
            <div className="shell-toggle-group" role="group" aria-label="Language">
              <button type="button" className={locale === 'en' ? 'active' : ''} onClick={() => setLocale('en')} title={t('langEnglish')}>
                EN
              </button>
              <button type="button" className={locale === 'ur' ? 'active' : ''} onClick={() => setLocale('ur')} title={t('langUrdu')}>
                اردو
              </button>
            </div>
          </div>
          <div className="shell-account" ref={accountRef}>
            <button
              type="button"
              className={`shell-account-btn${accountOpen ? ' open' : ''}`}
              onClick={() => setAccountOpen((o) => !o)}
              aria-expanded={accountOpen}
              aria-haspopup="true"
              aria-label="Account"
              title={user.name}
            >
              <span className="shell-account-initial" aria-hidden>
                {(user.name || user.email || '?').trim().charAt(0).toUpperCase()}
              </span>
            </button>
            {accountOpen && (
              <div className="shell-account-dropdown" role="menu">
                <div className="shell-account-head">
                  <div className="shell-account-avatar" aria-hidden>
                    {(user.name || user.email || '?').trim().charAt(0).toUpperCase()}
                  </div>
                  <div className="shell-account-meta">
                    <div className="shell-account-name">{user.name}</div>
                    <div className="shell-account-email">{user.email}</div>
                  </div>
                </div>
                <div className="shell-account-divider" />
                <button
                  type="button"
                  className="shell-account-logout"
                  role="menuitem"
                  onClick={() => {
                    setAccountOpen(false);
                    handleLogout();
                  }}
                >
                  <LogOut size={18} aria-hidden />
                  {t('logOut')}
                </button>
              </div>
            )}
          </div>
        </div>
        {backendDown && <p className="shell-banner">{t('backendUnreachable')}</p>}
      </header>

      <main className="shell-main">
        {page === 'home' && (
          <div className="page page-home">
            <div className="page-hero">
              <h1>{t('homeTitle')}</h1>
              <p>{t('homeSubtitle')}</p>
              <div className="page-hero-actions">
                <button type="button" className="primary" onClick={() => setPage('nvrs')}>
                  {t('configureNvrs')} <ChevronRight size={18} />
                </button>
                <button type="button" onClick={() => setPage('recordings')}>
                  {t('viewRecordings')}
                </button>
                <button type="button" onClick={() => setPage('test')}>
                  {t('testModel')}
                </button>
              </div>
            </div>
            <div className="page-cards">
              <article className="tile" onClick={() => setPage('nvrs')} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && setPage('nvrs')}>
                <Server size={28} />
                <h3>{t('tileNvrsTitle')}</h3>
                <p>{t('tileNvrsDesc')}</p>
                <span className="tile-meta">
                  {nvrList.length} {t('tileNvrsMeta')}
                </span>
              </article>
              <article className="tile" onClick={() => setPage('recordings')} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && setPage('recordings')}>
                <Film size={28} />
                <h3>{t('tileRecTitle')}</h3>
                <p>{t('tileRecDesc')}</p>
              </article>
              <article className="tile" onClick={() => setPage('test')} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && setPage('test')}>
                <Play size={28} />
                <h3>{t('tileTestTitle')}</h3>
                <p>{t('tileTestDesc')}</p>
              </article>
            </div>
          </div>
        )}

        {page === 'nvrs' && (
          <div className="page page-nvrs">
            <div className="page-head">
              <h1>{t('nvrConfigTitle')}</h1>
              <p className="page-sub">{t('nvrConfigSub')}</p>
            </div>
            <section className="panel">
              <h2>{t('addNvrSection')}</h2>
              <div className="form-grid">
                <div className="form-group">
                  <label>{t('labelName')}</label>
                  <input value={nvrForm.name} onChange={(e) => setNvrForm((f) => ({ ...f, name: e.target.value }))} placeholder="Building A" />
                </div>
                <div className="form-group">
                  <label>{t('labelIp')}</label>
                  <input value={nvrForm.ip} onChange={(e) => setNvrForm((f) => ({ ...f, ip: e.target.value }))} placeholder="192.168.1.108" />
                </div>
                <div className="form-group">
                  <label>{t('labelPort')}</label>
                  <input type="number" value={nvrForm.port} onChange={(e) => setNvrForm((f) => ({ ...f, port: parseInt(e.target.value, 10) || 37777 }))} />
                </div>
                <div className="form-group">
                  <label>{t('labelUsername')}</label>
                  <input value={nvrForm.username} onChange={(e) => setNvrForm((f) => ({ ...f, username: e.target.value }))} autoComplete="username" />
                </div>
                <div className="form-group">
                  <label>{t('labelPassword')}</label>
                  <input type="password" value={nvrForm.password} onChange={(e) => setNvrForm((f) => ({ ...f, password: e.target.value }))} autoComplete="current-password" />
                </div>
                <div className="form-group form-group-actions">
                  <label className="visually-hidden">{t('addNvrBtn')}</label>
                  <button type="button" className="primary" onClick={handleAddNvr}>
                    <Plus size={18} /> {t('addNvrBtn')}
                  </button>
                </div>
              </div>
              {nvrError && (
                <p className="inline-error" role="alert">
                  <XCircle size={16} /> {nvrError}
                </p>
              )}
            </section>
            <section className="panel">
              <h2>{t('registeredNvrs')}</h2>
              {nvrLoading ? (
                <Loader2 className="spin" size={28} />
              ) : nvrList.length === 0 ? (
                <p className="empty-hint">{t('noNvrsYet')}</p>
              ) : (
                <ul className="nvr-table">
                  {nvrList.map((n) => (
                    <li key={n.id}>
                      <div className="nvr-table-main">
                        <strong>{n.name}</strong>
                        <span className="mono">{n.ip}:{n.port}</span>
                        <span className="muted">{n.username}</span>
                      </div>
                      <button type="button" className="danger btn-icon" aria-label={t('deleteAria')} onClick={() => handleDeleteNvr(n.id)}>
                        <Trash2 size={18} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        )}

        {page === 'recordings' && (
          <div className="page page-recordings">
            <div className="page-head">
              <h1>{t('recTitle')}</h1>
              <p className="page-sub">{t('recSub')}</p>
            </div>
            <section className="panel panel-toolbar">
              <p className="form-hint" style={{ marginBottom: 14 }}>
                {t('channelsMultiHint')}
              </p>
              <div className="toolbar-row">
                <div className="form-group">
                  <label>{t('labelNvr')}</label>
                  <select
                    className="select-lg"
                    value={recNvrId === '' ? '' : String(recNvrId)}
                    onChange={(e) => setRecNvrId(e.target.value ? Number(e.target.value) : '')}
                  >
                    {nvrList.length === 0 && <option value="">{t('addNvrsFirst')}</option>}
                    {nvrList.map((n) => (
                      <option key={n.id} value={n.id}>
                        {n.name} — {n.ip}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>{t('labelDate')}</label>
                  <div className="input-with-icon">
                    <Calendar size={18} />
                    <input type="date" value={recDate} onChange={(e) => setRecDate(e.target.value)} />
                  </div>
                </div>
                <div className="form-group channel-multiselect-wrap" ref={channelMenuRef}>
                  <label>{t('channelsMultiLabel')} (1–15)</label>
                  <div className="channel-multiselect">
                    <button
                      type="button"
                      className="channel-multiselect-trigger"
                      onClick={() => setChannelMenuOpen((o) => !o)}
                      aria-expanded={channelMenuOpen}
                    >
                      <span className="channel-multiselect-trigger-label" title={
                        recChannelsSelected.length === 15
                          ? t('channelsAll')
                          : recChannelsSelected.length === 0
                            ? t('channelsPlaceholder')
                            : t('channelsSelectedCount', { n: recChannelsSelected.length })
                      }>
                        {recChannelsSelected.length === 15
                          ? t('channelsAll')
                          : recChannelsSelected.length === 0
                            ? t('channelsPlaceholder')
                            : t('channelsSelectedCount', { n: recChannelsSelected.length })}
                      </span>
                      <ChevronDown size={18} className={channelMenuOpen ? 'flip' : ''} />
                    </button>
                    {channelMenuOpen && (
                      <div className="channel-multiselect-panel" role="listbox">
                        <div className="channel-multiselect-actions">
                          <button
                            type="button"
                            className="btn-linkish"
                            onClick={() => setRecChannelsSelected(Array.from({ length: 15 }, (_, i) => i + 1))}
                          >
                            {t('channelsSelectAll')}
                          </button>
                          <button type="button" className="btn-linkish" onClick={() => setRecChannelsSelected([])}>
                            {t('channelsClear')}
                          </button>
                        </div>
                        <div className="channel-multiselect-grid">
                          {Array.from({ length: 15 }, (_, i) => i + 1).map((ch) => (
                            <label key={ch} className="channel-multiselect-item">
                              <input
                                type="checkbox"
                                checked={recChannelsSelected.includes(ch)}
                                onChange={() => toggleRecChannel(ch)}
                              />
                              <span>{t('channelN')} {ch}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
                <div className="form-group form-group-actions">
                  <label className="visually-hidden">{t('loadRecordings')}</label>
                  <button
                    type="button"
                    className="primary"
                    disabled={recNvrId === '' || recLoading || recChannelsSelected.length === 0}
                    onClick={loadRecordings}
                  >
                    {recLoading ? <Loader2 size={18} className="spin" /> : <Film size={18} />}
                    {t('loadRecordings')}
                  </button>
                </div>
                <div className="form-group form-group-actions">
                  <label className="visually-hidden">{t('runModelOnChannels')}</label>
                  <button
                    type="button"
                    disabled={recNvrId === '' || recChannelsSelected.length === 0}
                    onClick={runModelOnSelection}
                  >
                    <Play size={18} /> {t('runModelOnChannels')}
                  </button>
                </div>
              </div>
              {runForDateMsg && (
                <p className="form-hint" style={{ marginTop: 12 }}>
                  {runForDateMsg}
                </p>
              )}
            </section>
            {recError && (
              <div className="recordings-error" role="alert">
                <XCircle size={18} /> {recError}
              </div>
            )}
            {recData && (
              <div className="recordings-results">
                {recData.error && !Object.keys(recData.recordings_by_channel || {}).length && (
                  <p className="inline-error">{recData.error}</p>
                )}
                <p className="results-summary">
                  <strong>{recData.nvr_name}</strong> · {recData.date}
                  {recData.nvr_channels != null && (
                    <>
                      {' '}
                      · {recData.nvr_channels} {t('channelsOnDevice')}
                    </>
                  )}
                </p>
                {Object.entries(recData.recordings_by_channel || {})
                  .sort(([a], [b]) => Number(a) - Number(b))
                  .map(([ch, rows]) => {
                  const err = rows && typeof rows === 'object' && 'error' in rows ? (rows as { error: string }).error : null;
                  const list = Array.isArray(rows) ? (rows as RecordingSlot[]) : [];
                  const chNum = Number(ch) + 1;
                  return (
                    <section key={ch} className="channel-block">
                      <h3>
                        {t('channelN')} {chNum}
                      </h3>
                      {err ? (
                        <p className="inline-error">{err}</p>
                      ) : list.length === 0 ? (
                        <p className="empty-hint">{t('noRecDay')}</p>
                      ) : (
                        <div className="table-wrap">
                          <table className="results-table">
                            <thead>
                              <tr>
                                <th>{t('thStart')}</th>
                                <th>{t('thEnd')}</th>
                                <th>{t('thSize')}</th>
                              </tr>
                            </thead>
                            <tbody>
                              {list.map((r, i) => (
                                <tr key={i}>
                                  <td>{r.start_ts}</td>
                                  <td>{r.end_ts}</td>
                                  <td>{r.size ?? '—'}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </section>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {page === 'test' && (
          <div className="page page-test">
            <div className="page-head">
              <h1>{t('testTitle')}</h1>
              <p className="page-sub">{t('testSub')}</p>
            </div>
            <section className="panel">
              <p className="form-hint" style={{ marginBottom: 12 }}>
                {t('frameLimitHint')}
              </p>
              <div className="form-inline" style={{ flexWrap: 'wrap', gap: 14, alignItems: 'flex-end' }}>
                <div className="form-group" style={{ width: 120 }}>
                  <label>{t('maxFrames')}</label>
                  <input
                    type="number"
                    min={0}
                    value={maxFrames}
                    onChange={(e) => setMaxFrames(Math.max(0, parseInt(e.target.value, 10) || 0))}
                  />
                </div>
                <div className="form-group" style={{ flex: 1, minWidth: 280 }}>
                  <label>{t('localVideoPath')}</label>
                  <input
                    value={solutionVideoPath}
                    onChange={(e) => setSolutionVideoPath(e.target.value)}
                    placeholder="D:\path\to\video.mp4"
                  />
                </div>
                <button type="button" className="primary" onClick={handleRunSolutionVideo} disabled={solutionRunning}>
                  {solutionRunning ? <Loader2 size={18} className="spin" /> : <Play size={18} />}
                  {solutionRunning
                    ? t('running')
                    : maxFrames > 0
                      ? t('runFrames', { n: maxFrames })
                      : t('runFull')}
                </button>
              </div>
              {solutionRunning && (
                <div style={{ marginTop: 16 }}>
                  <p style={{ margin: '0 0 8px', color: 'var(--text-muted)' }}>
                    <Loader2 size={16} className="spin" style={{ verticalAlign: 'middle', marginRight: 8 }} />
                    {runProgress && runProgress.total > 0 ? (
                      <>
                        <strong>{runProgress.done.toLocaleString()}</strong> / {runProgress.total.toLocaleString()} ({runProgress.pct}%)
                      </>
                    ) : (
                      <>{t('loadingModel')}</>
                    )}
                  </p>
                  {runProgress && runProgress.total > 0 && (
                    <div className="progress-track">
                      <div className="progress-fill" style={{ width: `${Math.min(100, runProgress.pct)}%` }} />
                    </div>
                  )}
                </div>
              )}
              {solutionError && (
                <div className="recordings-error" role="alert" style={{ marginTop: 12 }}>
                  <XCircle size={18} /> {solutionError}
                </div>
              )}
              {solutionResult && !solutionResult.error && (
                <div style={{ marginTop: 20 }}>
                  <h3 className="results-title">{t('results')}</h3>
                  <div className="kpi-grid">
                    <div className="kpi-card">
                      <div className="kpi-label">{t('kpiTotalBlocks')}</div>
                      <div className="kpi-value">{solutionResult.total_unique_blocks ?? '—'}</div>
                    </div>
                    <div className="kpi-card">
                      <div className="kpi-label">{t('kpiStillPlatform')}</div>
                      <div className="kpi-value">{solutionResult.still_on_platform_end ?? '—'}</div>
                    </div>
                    <div className="kpi-card">
                      <div className="kpi-label">{t('kpiLeftPlatform')}</div>
                      <div className="kpi-value">{solutionResult.left_platform ?? '—'}</div>
                    </div>
                  </div>
                  <p style={{ fontSize: 13 }}>
                    <strong>{t('annotated')}</strong> <code>{solutionResult.output_video}</code>
                  </p>
                  <details>
                    <summary>{t('fullLog')}</summary>
                    <pre className="log-pre">{(solutionResult.logs || []).join('\n')}</pre>
                  </details>
                </div>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
