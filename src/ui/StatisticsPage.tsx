import { useState, useEffect, useCallback, useMemo } from 'react';
import { Loader2, RefreshCw, BarChart3, Calendar, TrendingUp, Hash, Film } from 'lucide-react';
import { runs, type RunResult, nvrs as nvrsApi } from './lib/api';

type Granularity = 'day' | 'week' | 'month' | 'year';

type Props = {
  t: (k: string, v?: Record<string, string | number>) => string;
  onOpenRecordings: () => void;
};

export default function StatisticsPage({ t, onOpenRecordings }: Props) {
  const [granularity, setGranularity] = useState<Granularity>('day');
  const [nvrId, setNvrId] = useState<number | ''>('');
  const [nvrList, setNvrList] = useState<{ id: number; name: string; ip: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [series, setSeries] = useState<
    { label: string; total_blocks: number; run_count: number }[]
  >([]);
  const [totals, setTotals] = useState({ total_blocks: 0, total_runs: 0, buckets: 0 });
  const [range, setRange] = useState({ from: '', to: '' });
  const [recent, setRecent] = useState<RunResult[]>([]);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  useEffect(() => {
    nvrsApi.list().then(setNvrList).catch(() => setNvrList([]));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const params: Parameters<typeof runs.statistics>[0] = { granularity };
      if (granularity === 'day') params.days = 30;
      if (granularity === 'week') params.weeks = 12;
      if (granularity === 'month') params.months = 12;
      if (granularity === 'year') params.years = 5;
      if (nvrId !== '') params.nvr_id = Number(nvrId);
      const data = await runs.statistics(params);
      setSeries(data.series);
      setTotals(data.totals);
      setRange({ from: data.from, to: data.to });
      const rows = await runs.results(nvrId === '' ? undefined : { nvr_id: Number(nvrId) });
      setRecent(rows.slice(0, 40));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [granularity, nvrId]);

  useEffect(() => {
    load();
  }, [load]);

  const maxBlocks = useMemo(() => Math.max(1, ...series.map((s) => s.total_blocks)), [series]);

  return (
    <div className="page page-statistics">
      <div className="page-head">
        <h1>{t('statsTitle')}</h1>
        <p className="page-sub">{t('statsSub')}</p>
      </div>

      <section className="panel panel-toolbar stats-recordings-panel">
        <p className="form-hint" style={{ marginBottom: 14 }}>{t('statsRecordingsHint')}</p>
        <div className="toolbar-row">
          <div className="form-group">
            <label>{t('labelNvr')}</label>
            <select
              className="select-lg"
              value={nvrId === '' ? '' : String(nvrId)}
              onChange={(e) => setNvrId(e.target.value ? Number(e.target.value) : '')}
            >
              <option value="">{t('statsAllNvrs')}</option>
              {nvrList.map((n) => (
                <option key={n.id} value={n.id}>{n.name} — {n.ip}</option>
              ))}
            </select>
          </div>
          <div className="form-group form-group-actions">
            <button type="button" className="primary" onClick={onOpenRecordings}>
              <Film size={18} /> {t('statsOpenRecordings')}
            </button>
          </div>
        </div>
      </section>

      <div className="stats-toolbar">
        <div className="stats-tabs" role="tablist">
          {(['day', 'week', 'month', 'year'] as const).map((g) => (
            <button
              key={g}
              type="button"
              role="tab"
              aria-selected={granularity === g}
              className={granularity === g ? 'active' : ''}
              onClick={() => setGranularity(g)}
            >
              {t(`statsGran_${g}`)}
            </button>
          ))}
        </div>
        <button type="button" className="stats-refresh" onClick={load} disabled={loading}>
          {loading ? <Loader2 size={18} className="spin" /> : <RefreshCw size={18} />}
          {t('statsRefresh')}
        </button>
      </div>

      {err && (
        <div className="recordings-error" role="alert">
          {err}
        </div>
      )}

      <section className="panel stats-kpis">
        <div className="stats-kpi">
          <TrendingUp className="stats-kpi-icon" size={22} />
          <div className="stats-kpi-val">{totals.total_blocks.toLocaleString()}</div>
          <div className="stats-kpi-label">{t('statsTotalBlocks')}</div>
        </div>
        <div className="stats-kpi">
          <Hash className="stats-kpi-icon" size={22} />
          <div className="stats-kpi-val">{totals.total_runs.toLocaleString()}</div>
          <div className="stats-kpi-label">{t('statsTotalRuns')}</div>
        </div>
        <div className="stats-kpi">
          <Calendar className="stats-kpi-icon" size={22} />
          <div className="stats-kpi-val">{range.from} → {range.to}</div>
          <div className="stats-kpi-label">{t('statsRange')}</div>
        </div>
      </section>

      <section className="panel stats-chart-panel">
        <h2 className="stats-chart-title">
          <BarChart3 size={20} /> {t('statsChartTitle')}
        </h2>
        {loading && !series.length ? (
          <div className="stats-chart-loading">
            <Loader2 className="spin" size={32} />
          </div>
        ) : series.length === 0 ? (
          <p className="empty-hint">{t('statsNoRuns')}</p>
        ) : (
          <div className="stats-chart-wrap">
            <div className="stats-chart-bars">
              {series.map((s, i) => {
                const h = Math.round((s.total_blocks / maxBlocks) * 100);
                const active = hoverIdx === i;
                return (
                  <div
                    key={s.label}
                    className={`stats-bar-col${active ? ' active' : ''}`}
                    onMouseEnter={() => setHoverIdx(i)}
                    onMouseLeave={() => setHoverIdx(null)}
                  >
                    <div className="stats-bar-track">
                      <div
                        className="stats-bar-fill"
                        style={{ height: `${Math.max(4, h)}%` }}
                      />
                    </div>
                    <span className="stats-bar-label" title={s.label}>
                      {granularity === 'day' ? s.label.slice(5) : s.label}
                    </span>
                    {active && (
                      <div className="stats-tooltip">
                        <strong>{s.label}</strong>
                        <span>{t('statsBlocks')}: {s.total_blocks}</span>
                        <span>{t('statsRuns')}: {s.run_count}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </section>

      <section className="panel">
        <h2>{t('statsRecentRuns')}</h2>
        <div className="table-wrap">
          <table className="results-table">
            <thead>
              <tr>
                <th>{t('statsColWhen')}</th>
                <th>{t('statsColNvr')}</th>
                <th>{t('statsColCh')}</th>
                <th>{t('statsColDate')}</th>
                <th>{t('statsColBlocks')}</th>
                <th>{t('statsColSource')}</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((r) => (
                <tr key={r.id}>
                  <td style={{ fontSize: 12 }}>{r.created_at?.slice(0, 19) ?? '—'}</td>
                  <td>{r.nvr_name ?? '—'}</td>
                  <td>{r.channel != null ? r.channel : '—'}</td>
                  <td>{r.run_date ?? '—'}</td>
                  <td className="count-cell">{r.total_unique_blocks ?? r.ice_block_count ?? '—'}</td>
                  <td>{r.source ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {recent.length === 0 && !loading && (
          <p className="empty-hint">{t('statsNoRuns')}</p>
        )}
      </section>
    </div>
  );
}
