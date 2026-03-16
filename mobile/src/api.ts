import { getApiBaseUrl } from './config';

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const base = getApiBaseUrl();
  const res = await fetch(`${base}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers } as HeadersInit,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error((err as { error?: string }).error || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (!text.trim()) return undefined as T;
  return JSON.parse(text) as T;
}

export const nvrs = {
  list: () =>
    api<{ id: number; name: string; ip: string; port: number; username: string; created_at: string }[]>(
      '/api/nvrs'
    ),
  add: (body: { name: string; ip: string; port: number; username: string; password: string }) =>
    api<{ id: number; name: string; ip: string; port: number; username: string; created_at: string }>(
      '/api/nvrs',
      { method: 'POST', body: JSON.stringify(body) }
    ),
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

export interface RunResult {
  id: number;
  nvr_id?: number | null;
  run_date?: string;
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

export const runs = {
  results: (params?: { nvr_id?: number }) => {
    const sp = new URLSearchParams();
    if (params?.nvr_id != null) sp.set('nvr_id', String(params.nvr_id));
    const q = sp.toString();
    return api<RunResult[]>(`/api/runs/results${q ? `?${q}` : ''}`);
  },
  runForDate: (body: { date: string; nvr_id?: number; channels?: number[] }) =>
    api<{
      status: string;
      date: string;
      nvr_id?: number;
      channels_1_15: number[];
      message: string;
    }>('/api/runs/run-for-date', { method: 'POST', body: JSON.stringify(body) }),
  statistics: (params: {
    granularity: 'day' | 'week' | 'month' | 'year';
    days?: number;
    weeks?: number;
    months?: number;
    years?: number;
    nvr_id?: number;
  }) => {
    const sp = new URLSearchParams();
    sp.set('granularity', params.granularity);
    if (params.days != null) sp.set('days', String(params.days));
    if (params.weeks != null) sp.set('weeks', String(params.weeks));
    if (params.months != null) sp.set('months', String(params.months));
    if (params.years != null) sp.set('years', String(params.years));
    if (params.nvr_id != null) sp.set('nvr_id', String(params.nvr_id));
    return api<{
      granularity: string;
      from: string;
      to: string;
      series: { label: string; total_blocks: number; run_count: number }[];
      totals: { total_blocks: number; total_runs: number; buckets: number };
    }>(`/api/runs/statistics?${sp.toString()}`);
  },
};
