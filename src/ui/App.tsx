import { useState, useEffect, useCallback } from 'react';
import {
  Server,
  Plus,
  Trash2,
  Play,
  RefreshCw,
  LayoutDashboard,
  ListChecks,
  Shield,
  Loader2,
  CheckCircle2,
  XCircle,
  MinusCircle,
  Settings,
  Blocks,
  Activity,
  Calendar,
  Video,
  Menu,
  User,
  Film,
} from 'lucide-react';
import { api, nvrs, runs, recordings, type RunResult, type SummaryRow, type JobProgressItem, type RecordingsByDateResponse } from './lib/api';
import AuthPage from './AuthPage';
import './index.css';

const AUTH_STORAGE_KEY = 'awan_ice_user';

type Nvr = { id: number; name: string; ip: string; port: number; username: string; created_at: string };
type Tab = 'dashboard' | 'settings';

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
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [tab, setTab] = useState<Tab>('dashboard');
  const [nvrsList, setNvrsList] = useState<Nvr[]>([]);
  const [results, setResults] = useState<RunResult[]>([]);
  const [summary, setSummary] = useState<SummaryRow[]>([]);
  const [job, setJob] = useState<{
    running: boolean;
    progress: JobProgressItem[];
    current: string | null;
    error: string | null;
  }>({ running: false, progress: [], current: null, error: null });
  const [status, setStatus] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [addForm, setAddForm] = useState({
    name: 'New NVR',
    ip: '192.168.1.100',
    port: 37777,
    username: 'admin',
    password: '',
  });
  const [runDate, setRunDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [testVideoPath, setTestVideoPath] = useState('');
  const [loadRecordingsNvrId, setLoadRecordingsNvrId] = useState<number | ''>('');
  const [loadRecordingsDate, setLoadRecordingsDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [loadRecordingsLoading, setLoadRecordingsLoading] = useState(false);
  const [loadRecordingsResult, setLoadRecordingsResult] = useState<RecordingsByDateResponse | null>(null);
  const [loadRecordingsError, setLoadRecordingsError] = useState<string | null>(null);
  const [runStartTime, setRunStartTime] = useState<number | null>(null);
  const [runEndTime, setRunEndTime] = useState<number | null>(null);
  const [backendDebug, setBackendDebug] = useState<{
    project_root: string;
    default_model_path: string;
    model_exists: boolean;
    backend_cwd: string;
  } | null>(null);
  const [backendDebugLoading, setBackendDebugLoading] = useState(false);
  const [backendDebugError, setBackendDebugError] = useState<string | null>(null);

  const loadNvrs = useCallback(async () => {
    try {
      const list = await nvrs.list();
      setNvrsList(list);
    } catch (e) {
      setStatus('Failed to load NVRs: ' + (e as Error).message);
    }
  }, []);

  const loadResults = useCallback(async () => {
    try {
      const [res, sum] = await Promise.all([runs.results(), runs.summary()]);
      setResults(res);
      setSummary(sum);
    } catch (e) {
      setStatus('Failed to load results: ' + (e as Error).message);
    }
  }, []);

  const loadJobProgress = useCallback(async () => {
    try {
      const j = await runs.jobProgress();
      setJob(j);
    } catch (_) {}
  }, []);

  useEffect(() => {
    let mounted = true;
    api<{ status: string }>('/api/status')
      .then(() => mounted && setStatus(''))
      .catch(() => mounted && setStatus('Backend not reachable'));
    Promise.all([loadNvrs(), loadResults()]).finally(() => mounted && setLoading(false));
    return () => { mounted = false; };
  }, [loadNvrs, loadResults]);

  useEffect(() => {
    if (!job.running) return;
    const poll = async () => {
      await loadJobProgress();
      await loadResults();
    };
    poll();
    const t = setInterval(poll, 2000);
    return () => clearInterval(t);
  }, [job.running, loadJobProgress, loadResults]);

  const handleAddNvr = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus('');
    try {
      await nvrs.add({ ...addForm, password: addForm.password || 'admin' });
      setAddForm((f) => ({
        ...f,
        name: 'New NVR',
        ip: '192.168.1.100',
        port: 37777,
        username: 'admin',
        password: '',
      }));
      loadNvrs();
    } catch (e) {
      setStatus('Add NVR failed: ' + (e as Error).message);
    }
  };

  const handleDeleteNvr = async (id: number) => {
    setStatus('');
    try {
      await nvrs.delete(id);
      loadNvrs();
    } catch (e) {
      setStatus('Delete failed: ' + (e as Error).message);
    }
  };

  const handleRunForDate = async () => {
    setStatus('');
    setJob({ running: true, progress: [], current: null, error: null });
    setRunStartTime(Date.now());
    setRunEndTime(null);
    try {
      await runs.runForDate(runDate, testVideoPath || undefined);
      const poll = async (): Promise<boolean> => {
        try {
          const j = await runs.jobProgress();
          setJob(j);
          if (!j.running) setRunEndTime(Date.now());
          return j.running;
        } catch (_) {
          return true;
        }
      };
      if (!(await poll())) {
        await loadResults();
        setTab('dashboard');
        return;
      }
      const interval = setInterval(async () => {
        const stillRunning = await poll();
        if (!stillRunning) {
          clearInterval(interval);
          await loadResults();
          setTab('dashboard');
        }
      }, 800);
    } catch (e) {
      setStatus('Start run failed: ' + (e as Error).message);
      setJob((j) => ({ ...j, running: false, error: (e as Error).message }));
      setRunStartTime(null);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadResults();
    setRefreshing(false);
  };

  const handleLoadRecordings = async () => {
    if (loadRecordingsNvrId === '' || !loadRecordingsDate) return;
    setLoadRecordingsLoading(true);
    setLoadRecordingsError(null);
    setLoadRecordingsResult(null);
    try {
      const data = await recordings.byDate(loadRecordingsNvrId, loadRecordingsDate);
      setLoadRecordingsResult(data);
    } catch (e) {
      setLoadRecordingsError((e as Error).message);
    } finally {
      setLoadRecordingsLoading(false);
    }
  };

  const handleCheckBackend = async () => {
    setBackendDebugLoading(true);
    setBackendDebugError(null);
    setBackendDebug(null);
    try {
      const data = await runs.debug();
      setBackendDebug(data);
    } catch (e) {
      setBackendDebugError((e as Error).message);
    } finally {
      setBackendDebugLoading(false);
    }
  };

  const statusBadge = (s: string) => {
    const c = s === 'completed' ? 'completed' : s === 'error' ? 'error' : 'skipped';
    const Icon = s === 'completed' ? CheckCircle2 : s === 'error' ? XCircle : MinusCircle;
    return (
      <span className={`status-badge ${c}`}>
        <Icon size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />
        {s}
      </span>
    );
  };

  // KPI derivations
  const totalBlocks = results.reduce((acc, r) => acc + (r.ice_block_count || 0), 0);
  const totalRuns = results.length;
  const completedRuns = results.filter((r) => r.status === 'completed').length;
  const today = new Date().toISOString().slice(0, 10);
  const runsToday = results.filter((r) => r.record_date === today).length;
  const blocksToday = results.filter((r) => r.record_date === today).reduce((acc, r) => acc + (r.ice_block_count || 0), 0);

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

  if (!user) {
    return <AuthPage onLogin={handleLogin} />;
  }

  if (loading) {
    return (
      <div className="app">
        <div className="header">
          <h1>Ice Factory Block Counter</h1>
          <p className="role"><Shield size={14} /> Super-Admin</p>
        </div>
        <main className="main" style={{ padding: 24, alignItems: 'center', justifyContent: 'center', minHeight: 280 }}>
          <section className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 56 }}>
            <Loader2 size={44} className="spin" style={{ marginBottom: 16 }} />
            <p style={{ color: 'var(--text-muted)', margin: 0 }}>Loading dashboard…</p>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className={`app ${sidebarOpen ? '' : 'sidebar-collapsed'}`}>
      <header className="header">
        <div className="header-inner">
          <button
            type="button"
            className="sidebar-toggle"
            onClick={() => setSidebarOpen((o) => !o)}
            title={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
            aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
          >
            <Menu size={22} />
          </button>
          <div className="header-brand">
            <div className="header-title-row">
              <Blocks size={28} className="header-icon" aria-hidden />
              <h1>Ice Factory Block Counter</h1>
            </div>
            <div className="header-meta">
            <p className="role"><Shield size={14} /> Super-Admin</p>
            <button type="button" className="logout-btn" onClick={handleLogout} title="Log out">
              Log out
            </button>
          </div>
        </div>
          <div className="header-ice">
            <Blocks size={32} className="header-ice-icon" aria-hidden />
            <span className="header-ice-label">Ice blocks</span>
          </div>
          <div className="header-user" title={`Signed in as ${user.name}`}>
            <User size={18} className="header-user-icon" aria-hidden />
            <span>{user.name}</span>
          </div>
        </div>
        {status && <p className="status-msg">{status}</p>}
      </header>

      <div className="app-layout">
        <aside className="sidebar">
          <nav>
            <ul className="sidebar-nav">
              <li>
                <a
                  href="#dashboard"
                  className={tab === 'dashboard' ? 'active' : ''}
                  onClick={(e) => { e.preventDefault(); setTab('dashboard'); }}
                >
                  <LayoutDashboard size={20} /> Dashboard
                </a>
              </li>
              <li>
                <a
                  href="#settings"
                  className={tab === 'settings' ? 'active' : ''}
                  onClick={(e) => { e.preventDefault(); setTab('settings'); }}
                >
                  <Settings size={20} /> Settings
                </a>
              </li>
            </ul>
          </nav>
        </aside>

        <div className="content-area">
          {tab === 'dashboard' && (
            <>
              <section className="dashboard-welcome">
                <h2 className="dashboard-welcome-title">Welcome back, {user.name}</h2>
                <p className="dashboard-welcome-sub">Here’s your ice block counting overview.</p>
              </section>
              {job.running && (
              <div className="live-banner">
                <Activity size={18} className="spin" />
                <span>Processing all channels — stats updating in real time</span>
              </div>
            )}
              <div className="kpi-grid">
                <div className="kpi-card">
                  <div className="kpi-icon green">
                    <Blocks size={22} />
                  </div>
                  <div className="kpi-label">Total blocks counted</div>
                  <div className="kpi-value success">{totalBlocks.toLocaleString()}</div>
                  <div className="kpi-sub">All time</div>
                </div>
                <div className="kpi-card">
                  <div className="kpi-icon">
                    <Activity size={22} />
                  </div>
                  <div className="kpi-label">Total runs</div>
                  <div className="kpi-value accent">{totalRuns}</div>
                  <div className="kpi-sub">{completedRuns} completed</div>
                </div>
                <div className="kpi-card">
                  <div className="kpi-icon purple">
                    <Server size={22} />
                  </div>
                  <div className="kpi-label">NVRs configured</div>
                  <div className="kpi-value">{nvrsList.length}</div>
                  <div className="kpi-sub">Endpoints</div>
                </div>
                <div className="kpi-card">
                  <div className="kpi-icon orange">
                    <Calendar size={22} />
                  </div>
                  <div className="kpi-label">Today</div>
                  <div className="kpi-value">{runsToday} runs</div>
                  <div className="kpi-sub">{blocksToday} blocks</div>
                </div>
              </div>

              <section className="card">
                <h2><LayoutDashboard size={20} /> Summary by NVR & channel</h2>
                {summary.length > 0 ? (
                  <div className="summary-grid">
                    {summary.slice(0, 20).map((s, i) => (
                      <div key={i} className="summary-item">
                        <span className="nvr-name">{s.nvr_name}</span> Ch{s.channel}{' '}
                        <span className="date">{s.record_date}</span>
                        <span className="total-blocks">{s.total_blocks} blocks</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="empty-state">No summary yet. Run the model from Settings to see counts.</div>
                )}
              </section>

              <section className="card card--results">
                <h2><ListChecks size={20} /> Results</h2>
                <div className="card-actions">
                  <button type="button" onClick={handleRefresh} disabled={refreshing}>
                    {refreshing ? <Loader2 size={16} className="spin" /> : <RefreshCw size={16} />}
                    Refresh
                  </button>
                </div>
                {results.length > 0 ? (
                  <div className="table-wrap">
                    <table className="results-table">
                      <thead>
                        <tr>
                          <th>NVR</th>
                          <th>Channel</th>
                          <th>Date</th>
                          <th>Time range</th>
                          <th>Count</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {results.map((r) => (
                          <tr key={r.id}>
                            <td>{r.nvr_name}</td>
                            <td>{r.channel}</td>
                            <td>{r.record_date}</td>
                            <td>{r.start_time} – {r.end_time}</td>
                            <td className="count-cell">{r.ice_block_count}</td>
                            <td>{statusBadge(r.status)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="empty-state">No results yet. Run the model from Settings.</div>
                )}
              </section>
            </>
          )}

          {tab === 'settings' && (
            <>
              <section className="card">
                <h2><Server size={20} /> NVRs</h2>
                <ul className="nvr-list">
                  {nvrsList.map((n) => (
                    <li key={n.id}>
                      <Server size={18} style={{ flexShrink: 0, opacity: 0.7 }} />
                      <span>{n.name}</span>
                      <span className="muted">{n.ip}:{n.port}</span>
                      <span className="nvr-badge">
                        <button type="button" className="btn-sm danger icon-only" onClick={() => handleDeleteNvr(n.id)} title="Remove NVR">
                          <Trash2 size={16} />
                        </button>
                      </span>
                    </li>
                  ))}
                </ul>
                {nvrsList.length === 0 && <div className="empty-state">No NVRs yet. Add one below.</div>}
                <form onSubmit={handleAddNvr} className="form-inline" style={{ marginTop: 16 }}>
                  <input value={addForm.name} onChange={(e) => setAddForm((f) => ({ ...f, name: e.target.value }))} placeholder="Name" />
                  <input value={addForm.ip} onChange={(e) => setAddForm((f) => ({ ...f, ip: e.target.value }))} placeholder="IP" />
                  <input type="number" value={addForm.port} onChange={(e) => setAddForm((f) => ({ ...f, port: +e.target.value }))} placeholder="Port" />
                  <input value={addForm.username} onChange={(e) => setAddForm((f) => ({ ...f, username: e.target.value }))} placeholder="User" />
                  <input type="password" value={addForm.password} onChange={(e) => setAddForm((f) => ({ ...f, password: e.target.value }))} placeholder="Password" />
                  <button type="submit"><Plus size={16} /> Add NVR</button>
                </form>
              </section>

              <section className="card">
                <h2><Activity size={20} /> Backend check</h2>
                <p className="run-description">
                  Verify the backend can see the project folder and model file. If &quot;Model exists&quot; is No, put <code>best_9_3_2026.pt</code> or <code>best (1).pt</code> in the project root. If the check fails, start Flask manually: <code>python backend/run_flask.py</code> from the project folder.
                </p>
                <button
                  type="button"
                  className="primary"
                  onClick={handleCheckBackend}
                  disabled={backendDebugLoading}
                >
                  {backendDebugLoading ? <Loader2 size={18} className="spin" /> : <RefreshCw size={18} />}
                  {backendDebugLoading ? 'Checking…' : 'Check backend'}
                </button>
                {backendDebugError && (
                  <div className="recordings-error" role="alert" style={{ marginTop: 12 }}>
                    <XCircle size={18} style={{ flexShrink: 0 }} />
                    <span>Backend not reachable: {backendDebugError}</span>
                  </div>
                )}
                {backendDebug && (
                  <div className="backend-debug" style={{ marginTop: 12, fontSize: 13, fontFamily: 'monospace' }}>
                    <p style={{ margin: '4px 0' }}><strong>Project root:</strong> {backendDebug.project_root}</p>
                    <p style={{ margin: '4px 0' }}><strong>Model path:</strong> {backendDebug.default_model_path}</p>
                    <p style={{ margin: '4px 0' }}>
                      <strong>Model exists:</strong>{' '}
                      <span style={{ color: backendDebug.model_exists ? 'var(--success)' : 'var(--danger)' }}>
                        {backendDebug.model_exists ? 'Yes' : 'No'}
                      </span>
                    </p>
                  </div>
                )}
              </section>

              <section className="card">
                <h2><Film size={20} /> Load recordings from NVR</h2>
                <p className="run-description">
                  Test if videos are loaded from the NVR using its stored IP, port, username, and password. Pick an NVR and date, then click <strong>Load recordings</strong> to see the list (or an error if login fails or Dahua NetSDK is not available).
                </p>
                <div className="form-inline" style={{ flexWrap: 'wrap', gap: 14, alignItems: 'flex-end' }}>
                  <div className="form-group">
                    <label>NVR</label>
                    <select
                      value={loadRecordingsNvrId === '' ? '' : loadRecordingsNvrId}
                      onChange={(e) => setLoadRecordingsNvrId(e.target.value === '' ? '' : Number(e.target.value))}
                      className="recordings-nvr-select"
                    >
                      <option value="">Select NVR</option>
                      {nvrsList.map((n) => (
                        <option key={n.id} value={n.id}>{n.name} ({n.ip}:{n.port})</option>
                      ))}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Date</label>
                    <input type="date" value={loadRecordingsDate} onChange={(e) => setLoadRecordingsDate(e.target.value)} />
                  </div>
                  <div className="form-group" style={{ alignSelf: 'flex-end' }}>
                    <button
                      type="button"
                      className="primary"
                      onClick={handleLoadRecordings}
                      disabled={loadRecordingsLoading || loadRecordingsNvrId === ''}
                    >
                      {loadRecordingsLoading ? <Loader2 size={18} className="spin" /> : <Film size={18} />}
                      {loadRecordingsLoading ? 'Loading…' : 'Load recordings'}
                    </button>
                  </div>
                </div>
                {loadRecordingsError && (
                  <div className="recordings-error" role="alert">
                    <XCircle size={18} style={{ flexShrink: 0 }} />
                    <span>{loadRecordingsError}</span>
                  </div>
                )}
                {loadRecordingsResult && (
                  <div className="recordings-result">
                    <p className="recordings-result-head">
                      <CheckCircle2 size={18} style={{ color: 'var(--success)' }} />
                      <strong>{loadRecordingsResult.nvr_name}</strong> — {loadRecordingsResult.date}: {loadRecordingsResult.recordings.length} recording(s)
                    </p>
                    {loadRecordingsResult.recordings.length > 0 ? (
                      <ul className="recordings-list">
                        {loadRecordingsResult.recordings.map((rec, i) => (
                          <li key={i}>
                            Ch {rec.channel} · {rec.start_time} – {rec.end_time}
                            {rec.size != null && rec.size > 0 && <span className="muted"> · {Math.round(rec.size / 1024)} KB</span>}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="recordings-empty">No recordings for this date (or SDK returned none).</p>
                    )}
                  </div>
                )}
              </section>

              <section className="card">
                <h2><Play size={20} /> Run model for date</h2>
                {status && status.includes('Start run failed') && (
                  <div className="recordings-error" role="alert" style={{ marginBottom: 12 }}>
                    <XCircle size={18} style={{ flexShrink: 0 }} />
                    <span>{status}</span>
                  </div>
                )}
                <p className="run-description">
                  Runs on <strong>all cameras (channels)</strong> for the selected date. Each NVR’s recordings are processed one by one; dashboard stats update in real time.
                  To run the model on <strong>a single video file</strong> you added: enter its <strong>full path</strong> in <strong>Test video</strong> below (e.g. <code>C:\Videos\ice_test.mp4</code>), pick a date, and click <strong>Run for date</strong>. The app will use that video for each slot (or once if you have no NVRs).
                </p>
                <div className="form-inline" style={{ flexWrap: 'wrap', gap: 14 }}>
                  <div className="form-group">
                    <label>Date</label>
                    <input type="date" value={runDate} onChange={(e) => setRunDate(e.target.value)} />
                  </div>
                  <div className="form-group" style={{ minWidth: 260 }}>
                    <label><Video size={14} style={{ verticalAlign: 'middle', marginRight: 4 }} /> Test video (optional)</label>
                    <input value={testVideoPath} onChange={(e) => setTestVideoPath(e.target.value)} placeholder="Full path, e.g. D:\\Folder\\video.mp4" />
                    <span className="form-hint">Use the full path from File Explorer (right‑click file → Copy as path).</span>
                  </div>
                  <div className="form-group" style={{ alignSelf: 'flex-end' }}>
                    <button type="button" className="primary" onClick={handleRunForDate} disabled={job.running}>
                      {job.running ? <Loader2 size={18} className="spin" /> : <Play size={18} />}
                      {job.running ? 'Running…' : 'Run for date'}
                    </button>
                  </div>
                </div>
                {(job.running || job.progress.length > 0) && (
                  <div className="progress-box">
                    <div className="progress-box-header">
                      {job.running ? (
                        <>
                          <div className="progress-bar-wrap">
                            <div className="progress-bar progress-bar-indeterminate" />
                          </div>
                          <div className="current-line">
                            <div className="spinner" />
                            <span>{job.current || 'Starting…'}</span>
                            {runStartTime != null && (
                              <span className="progress-elapsed">
                                · {Math.round((Date.now() - runStartTime) / 1000)}s
                              </span>
                            )}
                          </div>
                        </>
                      ) : (
                        <div className="progress-completed">
                          {job.error ? (
                            <XCircle size={20} style={{ color: 'var(--danger)', flexShrink: 0 }} />
                          ) : (
                            <CheckCircle2 size={20} style={{ color: 'var(--success)', flexShrink: 0 }} />
                          )}
                          <span>{job.error ? 'Failed' : 'Completed'}</span>
                          {runStartTime != null && runEndTime != null && !job.error && (
                            <span className="progress-elapsed">
                              (took {Math.round((runEndTime - runStartTime) / 1000)}s)
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                    {job.error && (
                      <p className="progress-error-msg" role="alert">
                        {job.error}
                      </p>
                    )}
                    {!job.running && job.progress.length > 0 && (
                      <button
                        type="button"
                        className="progress-view-results"
                        onClick={() => setTab('dashboard')}
                      >
                        View results on Dashboard
                      </button>
                    )}
                    <ul className="progress-list">
                      {job.progress.slice(-15).reverse().map((p, i) => (
                        <li key={i} className={`status-${p.status === 'completed' ? 'completed' : p.status === 'error' ? 'error' : 'skipped'}`}>
                          {p.nvr_name} Ch{p.channel ?? '?'} · {p.status}
                          {p.ice_block_count != null && <strong style={{ marginLeft: 6, color: 'var(--success)' }}>→ {p.ice_block_count} blocks</strong>}
                          {p.message && ` · ${p.message}`}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
