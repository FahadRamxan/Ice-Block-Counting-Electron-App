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
  recordings: RecordingSlot[];
}

export const recordings = {
  byDate: (nvrId: number, date: string) =>
    api<RecordingsByDateResponse>(`/api/recordings/by-date?nvr_id=${nvrId}&date=${encodeURIComponent(date)}`),
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
  runForDate: (date: string, testVideoPath?: string) =>
    api<{ status: string; date: string; nvrs: number }>('/api/runs/run-for-date', {
      method: 'POST',
      body: JSON.stringify({ date, test_video_path: testVideoPath?.trim() || undefined }),
    }),
  jobProgress: () =>
    api<{ running: boolean; progress: JobProgressItem[]; current: string | null; error: string | null }>('/api/runs/job-progress'),
  debug: () =>
    api<{ project_root: string; default_model_path: string; model_exists: boolean; backend_cwd: string }>('/api/runs/debug'),
};

export interface RunResult {
  id: number;
  nvr_id: number;
  nvr_name: string;
  channel: number;
  record_date: string;
  start_time: string;
  end_time: string;
  ice_block_count: number;
  status: string;
  video_path: string | null;
  created_at: string;
}

export interface SummaryRow {
  nvr_id: number;
  nvr_name: string;
  channel: number;
  record_date: string;
  total_blocks: number;
}

export interface JobProgressItem {
  nvr_id: number;
  nvr_name: string;
  channel: number | null;
  start_time?: string;
  end_time?: string;
  ice_block_count?: number;
  status: string;
  message?: string;
  error?: string;
}
