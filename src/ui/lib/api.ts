const BASE = typeof window !== 'undefined' && (window as unknown as { electron?: { getBaseUrl?: () => string } }).electron?.getBaseUrl?.()
  ? (window as unknown as { electron: { getBaseUrl: () => string } }).electron.getBaseUrl()
  : 'http://localhost:5000';

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error((err as { error?: string }).error || res.statusText);
  }
  // 204 No Content or empty body (e.g. DELETE) — don't parse as JSON
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (!text.trim()) return undefined as T;
  return JSON.parse(text) as T;
}

export const nvrs = {
  list: () => api<{ id: number; name: string; ip: string; port: number; username: string; created_at: string }[]>('/api/nvrs'),
  add: (body: { name: string; ip: string; port: number; username: string; password: string }) =>
    api<{ id: number; name: string; ip: string; port: number; username: string; created_at: string }>('/api/nvrs', { method: 'POST', body: JSON.stringify(body) }),
  delete: (id: number) => api<void>(`/api/nvrs/${id}`, { method: 'DELETE' }),
};

export interface RecordingSlot {
  channel: number;
  start_time: string;
  end_time: string;
  start_ts: string;
  end_ts: string;
  size?: number;
}

export interface RecordingsByDateResponse {
  nvr_id: number;
  nvr_name: string;
  date: string;
  nvr_channels?: number;
  recordings_by_channel: Record<string, RecordingSlot[] | { error?: string }>;
  error?: string | null;
}

export const recordings = {
  byDate: (nvrId: number, date: string, channels: 'all' | number[]) =>
    api<RecordingsByDateResponse>('/api/recordings/by-date', {
      method: 'POST',
      body: JSON.stringify({
        nvr_id: nvrId,
        date,
        channels: channels === 'all' ? 'all' : channels,
      }),
    }),
};

export const runs = {
  results: (params?: { date_from?: string; date_to?: string; nvr_id?: number }) => {
    const sp = new URLSearchParams();
    if (params?.date_from) sp.set('date_from', params.date_from);
    if (params?.date_to) sp.set('date_to', params.date_to);
    if (params?.nvr_id != null) sp.set('nvr_id', String(params.nvr_id));
    const q = sp.toString();
    return api<RunResult[]>(`/api/runs/results${q ? `?${q}` : ''}`);
  },
  summary: (date?: string) =>
    api<SummaryRow[]>(`/api/runs/results/summary${date ? `?date=${date}` : ''}`),
  jobProgress: () =>
    api<{
      running: boolean;
      progress: JobProgressItem[];
      current: string | null;
      error: string | null;
      result?: TestVideoRunResult | null;
    }>('/api/runs/job-progress'),
  runForDate: (body: { date: string; nvr_id?: number; channels?: number[] }) =>
    api<{
      status: string;
      date: string;
      nvr_id?: number;
      channels_1_15: number[];
      message: string;
    }>('/api/runs/run-for-date', { method: 'POST', body: JSON.stringify(body) }),
  testVideo: (videoPath: string, maxFrames?: number | null) =>
    api<{ status: string; video_path: string; max_frames?: number | null }>('/api/runs/test-video', {
      method: 'POST',
      body: JSON.stringify({
        video_path: videoPath.trim(),
        max_frames: maxFrames != null && maxFrames > 0 ? maxFrames : undefined,
      }),
    }),
  debug: () =>
    api<{ project_root: string; default_model_path: string; model_exists: boolean; backend_cwd: string }>('/api/runs/debug'),
  statistics: (params: {
    granularity: 'day' | 'week' | 'month' | 'year';
    days?: number;
    weeks?: number;
    months?: number;
    years?: number;
    to?: string;
  }) => {
    const sp = new URLSearchParams();
    sp.set('granularity', params.granularity);
    if (params.days != null) sp.set('days', String(params.days));
    if (params.weeks != null) sp.set('weeks', String(params.weeks));
    if (params.months != null) sp.set('months', String(params.months));
    if (params.years != null) sp.set('years', String(params.years));
    if (params.to) sp.set('to', params.to);
    return api<{
      granularity: string;
      from: string;
      to: string;
      series: { label: string; total_blocks: number; run_count: number; left_platform: number; still_on_platform: number }[];
      totals: { total_blocks: number; total_runs: number; buckets: number };
    }>(`/api/runs/statistics?${sp.toString()}`);
  },
  seedDemoStats: () => api<{ ok: boolean }>('/api/runs/statistics/seed-demo', { method: 'POST', body: '{}' }),
};

export interface RunResult {
  id: number;
  run_date?: string;
  nvr_id?: number | null;
  nvr_name?: string | null;
  channel?: number | null;
  total_unique_blocks?: number;
  left_platform?: number;
  still_on_platform?: number;
  source?: string;
  created_at: string;
  record_date?: string;
  ice_block_count?: number;
  status?: string;
  video_path?: string | null;
}

export interface SummaryRow {
  nvr_id: number;
  nvr_name: string;
  channel: number;
  record_date: string;
  total_blocks: number;
}

export interface JobProgressItem {
  nvr_id?: number;
  nvr_name?: string;
  channel?: number | null;
  start_time?: string;
  end_time?: string;
  ice_block_count?: number;
  status?: string;
  message?: string;
  error?: string;
  line?: string;
}

export interface TestVideoRunResult {
  error: string | null;
  logs: string[];
  total_unique_blocks?: number;
  still_on_platform_end?: number;
  left_platform?: number;
  output_csv?: string;
  output_video?: string;
  video_width?: number;
  video_height?: number;
  fps?: number;
  frames_processed?: number;
}
