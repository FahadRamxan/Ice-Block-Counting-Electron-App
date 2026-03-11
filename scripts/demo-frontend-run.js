#!/usr/bin/env node
/**
 * Demo: same flow as the frontend when you click "Run for date" with a test video.
 * Usage (from project root):
 *   node scripts/demo-frontend-run.js [video_path]
 *   VIDEO_PATH="D:\path\to\video.mp4" node scripts/demo-frontend-run.js
 *
 * Requires: Flask backend running (npm run dev or python backend/run_flask.py).
 */

const BASE = process.env.API_BASE || 'http://localhost:5000';

async function api(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  if (res.status === 204) return undefined;
  const text = await res.text();
  if (!text.trim()) return undefined;
  return JSON.parse(text);
}

async function main() {
  const videoPath = process.env.VIDEO_PATH || process.argv[2];
  const date = new Date().toISOString().slice(0, 10);

  console.log('1. Checking backend (GET /api/runs/debug)...');
  let debug;
  try {
    debug = await api('/api/runs/debug');
    console.log('   Project root:', debug.project_root);
    console.log('   Model path: ', debug.default_model_path);
    console.log('   Model exists:', debug.model_exists ? 'Yes' : 'No');
  } catch (e) {
    console.error('   Backend not reachable:', e.message);
    console.error('   Start Flask: python backend/run_flask.py');
    process.exit(1);
  }
  if (!debug.model_exists) {
    console.warn('   WARNING: Model file not found. Put best (1).pt or best_9_3_2026.pt in project root.');
  }

  console.log('\n2. Starting run (POST /api/runs/run-for-date)...');
  console.log('   Date:', date, '| Test video:', videoPath || '(none)');
  let start;
  try {
    start = await api('/api/runs/run-for-date', {
      method: 'POST',
      body: JSON.stringify({ date, test_video_path: videoPath || undefined }),
    });
    console.log('   Response:', start);
  } catch (e) {
    console.error('   Failed:', e.message);
    process.exit(1);
  }

  console.log('\n3. Polling job progress (GET /api/runs/job-progress)...');
  let job;
  do {
    await new Promise((r) => setTimeout(r, 1000));
    job = await api('/api/runs/job-progress');
    const msg = job.running ? (job.current || 'Running...') : (job.error ? 'Failed: ' + job.error : 'Done.');
    console.log('   ', msg);
  } while (job.running);

  if (job.error) console.log('\n   Job error:', job.error);
  if (job.progress && job.progress.length) {
    console.log('   Progress items:', job.progress.length);
    job.progress.forEach((p, i) => {
      const detail = p.message || p.error || (p.ice_block_count != null ? 'count: ' + p.ice_block_count : '');
      console.log('   ', i + 1, p.nvr_name, 'Ch' + (p.channel ?? '?'), '|', p.status, detail ? '| ' + detail : '');
    });
  }

  console.log('\n4. Fetching results (GET /api/runs/results)...');
  const results = await api('/api/runs/results');
  const latest = results.slice(0, 5);
  console.log('   Latest', latest.length, 'result(s):');
  latest.forEach((r) => {
    console.log('   -', r.nvr_name, 'Ch' + r.channel, '|', r.record_date, '| count:', r.ice_block_count, '|', r.status);
  });

  console.log('\nDone. This is the same flow the frontend uses when you click "Run for date".');
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
