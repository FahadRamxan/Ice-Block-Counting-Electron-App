import { useState, useEffect, useCallback } from 'react';
import {
  Play,
  Loader2,
  XCircle,
  Blocks,
  User,
  Server,
  Film,
  Home,
  Trash2,
  Plus,
  Calendar,
  ChevronRight,
} from 'lucide-react';
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
  const [user, setUser] = useState<{ name: string; email: string } | null>(getStoredUser);
  const [page, setPage] = useState<Page>('home');
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(true);

  // NVRs
  const [nvrList, setNvrList] = useState<{ id: number; name: string; ip: string; port: number; username: string; created_at: string }[]>([]);
  const [nvrLoading, setNvrLoading] = useState(false);
  const [nvrForm, setNvrForm] = useState({ name: '', ip: '', port: 37777, username: '', password: '' });
  const [nvrError, setNvrError] = useState<string | null>(null);

  // Recordings
  const [recNvrId, setRecNvrId] = useState<number | ''>('');
  const [recDate, setRecDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [channelMode, setChannelMode] = useState<'all' | 'pick'>('all');
  const [channelPick, setChannelPick] = useState<number[]>([]);
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
      .then(() => mounted && setStatus(''))
      .catch(() => mounted && setStatus('Backend not reachable — start Flask: python backend/run_flask.py'));
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
      setNvrError('IP is required');
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
    if (!confirm('Remove this NVR from the list?')) return;
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
    setRecLoading(true);
    setRecError(null);
    setRecData(null);
    try {
      const channels =
        channelMode === 'all'
          ? ('all' as const)
          : channelPick.length
            ? channelPick
            : ('all' as const);
      const data = await recordingsApi.byDate(Number(recNvrId), recDate, channels);
      setRecData(data);
    } catch (e) {
      setRecError((e as Error).message);
    } finally {
      setRecLoading(false);
    }
  };

  const toggleChannel = (ch: number) => {
    setChannelPick((prev) => (prev.includes(ch) ? prev.filter((c) => c !== ch) : [...prev, ch].sort((a, b) => a - b)));
  };

  const handleRunSolutionVideo = async () => {
    const path = solutionVideoPath.trim();
    if (!path) {
      setSolutionError('Enter a local video path');
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

  const nCh = recData?.nvr_channels ?? 16;
  const channelOptions = Array.from({ length: nCh }, (_, i) => i);

  return (
    <div className="app app-shell">
      <FloatingIceBackdrop />
      <header className="shell-header">
        <div className="shell-header-bar">
          <button type="button" className="shell-brand" onClick={() => setPage('home')}>
            <Blocks size={26} className="shell-brand-icon" aria-hidden />
            <span className="shell-brand-text">Ice Factory</span>
          </button>
          <nav className="shell-nav" aria-label="Main">
            <button type="button" className={page === 'home' ? 'active' : ''} onClick={() => setPage('home')}>
              <Home size={18} /> Home
            </button>
            <button type="button" className={page === 'nvrs' ? 'active' : ''} onClick={() => setPage('nvrs')}>
              <Server size={18} /> NVRs
            </button>
            <button type="button" className={page === 'recordings' ? 'active' : ''} onClick={() => setPage('recordings')}>
              <Film size={18} /> Recordings
            </button>
            <button type="button" className={page === 'test' ? 'active' : ''} onClick={() => setPage('test')}>
              <Play size={18} /> Test model
            </button>
          </nav>
          <div className="shell-user">
            <span className="shell-user-name" title={user.email}>
              <User size={16} /> {user.name}
            </span>
            <button type="button" className="shell-logout" onClick={handleLogout}>
              Log out
            </button>
          </div>
        </div>
        {status && <p className="shell-banner">{status}</p>}
      </header>

      <main className="shell-main">
        {page === 'home' && (
          <div className="page page-home">
            <div className="page-hero">
              <h1>Block counter</h1>
              <p>Configure NVRs, browse recordings by date across all channels, and test the model on local video.</p>
              <div className="page-hero-actions">
                <button type="button" className="primary" onClick={() => setPage('nvrs')}>
                  Configure NVRs <ChevronRight size={18} />
                </button>
                <button type="button" onClick={() => setPage('recordings')}>
                  View recordings
                </button>
                <button type="button" onClick={() => setPage('test')}>
                  Test model
                </button>
              </div>
            </div>
            <div className="page-cards">
              <article className="tile" onClick={() => setPage('nvrs')} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && setPage('nvrs')}>
                <Server size={28} />
                <h3>NVRs</h3>
                <p>Add many NVR endpoints. Each device stores multi-channel footage.</p>
                <span className="tile-meta">{nvrList.length} configured</span>
              </article>
              <article className="tile" onClick={() => setPage('recordings')} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && setPage('recordings')}>
                <Film size={28} />
                <h3>Recordings</h3>
                <p>Pick NVR + date. Query all channels at once or filter by channel.</p>
              </article>
              <article className="tile" onClick={() => setPage('test')} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && setPage('test')}>
                <Play size={28} />
                <h3>Test model</h3>
                <p>Run Solution.py-style pipeline on a local file with frame limit.</p>
              </article>
            </div>
          </div>
        )}

        {page === 'nvrs' && (
          <div className="page page-nvrs">
            <div className="page-head">
              <h1>NVR configuration</h1>
              <p className="page-sub">Add as many NVRs as you need. Connection uses Dahua SDK (same as the desktop viewer).</p>
            </div>
            <section className="panel">
              <h2>Add NVR</h2>
              <div className="form-grid">
                <div className="form-group">
                  <label>Name</label>
                  <input value={nvrForm.name} onChange={(e) => setNvrForm((f) => ({ ...f, name: e.target.value }))} placeholder="Building A" />
                </div>
                <div className="form-group">
                  <label>IP / host</label>
                  <input value={nvrForm.ip} onChange={(e) => setNvrForm((f) => ({ ...f, ip: e.target.value }))} placeholder="192.168.1.108" />
                </div>
                <div className="form-group">
                  <label>Port</label>
                  <input type="number" value={nvrForm.port} onChange={(e) => setNvrForm((f) => ({ ...f, port: parseInt(e.target.value, 10) || 37777 }))} />
                </div>
                <div className="form-group">
                  <label>Username</label>
                  <input value={nvrForm.username} onChange={(e) => setNvrForm((f) => ({ ...f, username: e.target.value }))} autoComplete="username" />
                </div>
                <div className="form-group">
                  <label>Password</label>
                  <input type="password" value={nvrForm.password} onChange={(e) => setNvrForm((f) => ({ ...f, password: e.target.value }))} autoComplete="current-password" />
                </div>
                <div className="form-group form-group-actions">
                  <label className="visually-hidden">Add</label>
                  <button type="button" className="primary" onClick={handleAddNvr}>
                    <Plus size={18} /> Add NVR
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
              <h2>Registered NVRs</h2>
              {nvrLoading ? (
                <Loader2 className="spin" size={28} />
              ) : nvrList.length === 0 ? (
                <p className="empty-hint">No NVRs yet. Add one above.</p>
              ) : (
                <ul className="nvr-table">
                  {nvrList.map((n) => (
                    <li key={n.id}>
                      <div className="nvr-table-main">
                        <strong>{n.name}</strong>
                        <span className="mono">{n.ip}:{n.port}</span>
                        <span className="muted">{n.username}</span>
                      </div>
                      <button type="button" className="danger btn-icon" aria-label="Delete" onClick={() => handleDeleteNvr(n.id)}>
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
              <h1>Recordings by date</h1>
              <p className="page-sub">Choose NVR and date. Default loads <strong>all channels</strong> in one request. Narrow with channel filter if needed.</p>
            </div>
            <section className="panel panel-toolbar">
              <div className="toolbar-row">
                <div className="form-group">
                  <label>NVR</label>
                  <select
                    className="select-lg"
                    value={recNvrId === '' ? '' : String(recNvrId)}
                    onChange={(e) => setRecNvrId(e.target.value ? Number(e.target.value) : '')}
                  >
                    {nvrList.length === 0 && <option value="">Add NVRs first</option>}
                    {nvrList.map((n) => (
                      <option key={n.id} value={n.id}>
                        {n.name} — {n.ip}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>Date</label>
                  <div className="input-with-icon">
                    <Calendar size={18} />
                    <input type="date" value={recDate} onChange={(e) => setRecDate(e.target.value)} />
                  </div>
                </div>
                <div className="form-group">
                  <label>Channels</label>
                  <select className="select-lg" value={channelMode} onChange={(e) => setChannelMode(e.target.value as 'all' | 'pick')}>
                    <option value="all">All channels</option>
                    <option value="pick">Select channels…</option>
                  </select>
                </div>
                <div className="form-group form-group-actions">
                  <label className="visually-hidden">Load</label>
                  <button type="button" className="primary" disabled={recNvrId === '' || recLoading} onClick={loadRecordings}>
                    {recLoading ? <Loader2 size={18} className="spin" /> : <Film size={18} />}
                    Load recordings
                  </button>
                </div>
              </div>
              {channelMode === 'pick' && (
                <div className="channel-chips">
                  <span className="chips-label">After first load, device channel count is known. Pick channels:</span>
                  <div className="chips">
                    {channelOptions.map((ch) => (
                      <button
                        key={ch}
                        type="button"
                        className={channelPick.includes(ch) ? 'chip active' : 'chip'}
                        onClick={() => toggleChannel(ch)}
                      >
                        Ch {ch}
                      </button>
                    ))}
                  </div>
                  <p className="form-hint">If you haven’t loaded yet, chips use 0–15. Run once with &quot;All&quot; to refresh count from NVR.</p>
                </div>
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
                  {recData.nvr_channels != null && <> · {recData.nvr_channels} channels on device</>}
                </p>
                {Object.entries(recData.recordings_by_channel || {}).map(([ch, rows]) => {
                  const err = rows && typeof rows === 'object' && 'error' in rows ? (rows as { error: string }).error : null;
                  const list = Array.isArray(rows) ? (rows as RecordingSlot[]) : [];
                  return (
                    <section key={ch} className="channel-block">
                      <h3>Channel {ch}</h3>
                      {err ? (
                        <p className="inline-error">{err}</p>
                      ) : list.length === 0 ? (
                        <p className="empty-hint">No recordings for this day.</p>
                      ) : (
                        <div className="table-wrap">
                          <table className="results-table">
                            <thead>
                              <tr>
                                <th>Start</th>
                                <th>End</th>
                                <th>Size</th>
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
              <h1>Test the model</h1>
              <p className="page-sub">Same pipeline as Solution.py — local video + YOLO. Keep <code>best (1).pt</code> in project root.</p>
            </div>
            <section className="panel">
              <p className="form-hint" style={{ marginBottom: 12 }}>
                <strong>Frame limit:</strong> default <strong>100</strong> for quick preview. <strong>0</strong> = full video.
              </p>
              <div className="form-inline" style={{ flexWrap: 'wrap', gap: 14, alignItems: 'flex-end' }}>
                <div className="form-group" style={{ width: 120 }}>
                  <label>Max frames</label>
                  <input
                    type="number"
                    min={0}
                    value={maxFrames}
                    onChange={(e) => setMaxFrames(Math.max(0, parseInt(e.target.value, 10) || 0))}
                  />
                </div>
                <div className="form-group" style={{ flex: 1, minWidth: 280 }}>
                  <label>Local video path</label>
                  <input
                    value={solutionVideoPath}
                    onChange={(e) => setSolutionVideoPath(e.target.value)}
                    placeholder="D:\path\to\video.mp4"
                  />
                </div>
                <button type="button" className="primary" onClick={handleRunSolutionVideo} disabled={solutionRunning}>
                  {solutionRunning ? <Loader2 size={18} className="spin" /> : <Play size={18} />}
                  {solutionRunning ? 'Running…' : maxFrames > 0 ? `Run (${maxFrames} frames)` : 'Run full'}
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
                      <>Loading model…</>
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
                  <h3 className="results-title">Results</h3>
                  <div className="kpi-grid">
                    <div className="kpi-card">
                      <div className="kpi-label">Total unique blocks</div>
                      <div className="kpi-value">{solutionResult.total_unique_blocks ?? '—'}</div>
                    </div>
                    <div className="kpi-card">
                      <div className="kpi-label">Still on platform</div>
                      <div className="kpi-value">{solutionResult.still_on_platform_end ?? '—'}</div>
                    </div>
                    <div className="kpi-card">
                      <div className="kpi-label">Left platform</div>
                      <div className="kpi-value">{solutionResult.left_platform ?? '—'}</div>
                    </div>
                  </div>
                  <p style={{ fontSize: 13 }}>
                    <strong>Annotated:</strong> <code>{solutionResult.output_video}</code>
                  </p>
                  <details>
                    <summary>Full log</summary>
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
