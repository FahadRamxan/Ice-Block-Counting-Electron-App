"""Runs API — test video (Solution.py pipeline) + statistics."""
import os
import threading
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from app.db import insert_run_event, get_conn, init_db, seed_demo_statistics_if_empty

bp = Blueprint('runs', __name__, url_prefix='/api/runs')

def _project_root():
    _here = os.path.abspath(__file__)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_here))))

def _default_model_path():
    root = _project_root()
    for name in ["best_9_3_2026.pt", "best (1).pt"]:
        p = os.path.join(root, name)
        if os.path.isfile(p):
            return p
    return os.path.join(root, "best (1).pt")

_job = {
    "running": False,
    "current": None,
    "error": None,
    "progress": [],
    "result": None,
    "frames_done": 0,
    "frames_total": 0,
    "seconds_into_video": 0.0,
}

def _run_test_video_thread(video_path: str, model_path: str, max_frames: int | None = None):
    global _job
    _job["running"] = True
    _job["error"] = None
    _job["result"] = None
    _job["current"] = "Loading model / video..."
    _job["progress"] = []
    _job["frames_done"] = 0
    _job["frames_total"] = 0
    _job["seconds_into_video"] = 0.0
    try:
        _backend = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if _backend not in __import__("sys").path:
            __import__("sys").path.insert(0, _backend)
        import model_runner

        def _cb(done, total, t_sec):
            _job["frames_done"] = done
            _job["frames_total"] = total
            _job["seconds_into_video"] = round(t_sec, 1)
            pct = 100.0 * done / total if total else 0
            _job["current"] = f"Processing frame {done}/{total} ({pct:.1f}%) — video time ~{t_sec:.0f}s"

        out = model_runner.run_solution_style(
            video_path, model_path, progress_callback=_cb, max_frames=max_frames
        )
        if out.get("error"):
            _job["error"] = out["error"]
            _job["current"] = out["error"]
        else:
            _job["result"] = out
            _job["current"] = "Done."
            for line in out.get("logs", [])[-50:]:
                _job["progress"].append({"line": line})
            try:
                init_db()
                insert_run_event(
                    datetime.utcnow().date().isoformat(),
                    int(out.get("total_unique_blocks") or 0),
                    int(out.get("left_platform") or 0),
                    int(out.get("still_on_platform_end") or out.get("still_on_platform") or 0),
                    source="test_video",
                )
            except Exception:
                pass
    except Exception as e:
        _job["error"] = str(e)
        _job["current"] = str(e)
    finally:
        _job["running"] = False


def _statistics_series(granularity: str, date_from: str, date_to: str, nvr_id=None):
    init_db()
    conn = get_conn()
    try:
        if nvr_id is not None:
            rows = conn.execute(
                '''SELECT run_date, total_unique_blocks, left_platform, still_on_platform
                   FROM run_events WHERE run_date >= ? AND run_date <= ? AND nvr_id = ?
                   ORDER BY run_date''',
                (date_from, date_to, int(nvr_id)),
            ).fetchall()
        else:
            rows = conn.execute(
                '''SELECT run_date, total_unique_blocks, left_platform, still_on_platform
                   FROM run_events WHERE run_date >= ? AND run_date <= ? ORDER BY run_date''',
                (date_from, date_to),
            ).fetchall()
    finally:
        conn.close()
    from collections import defaultdict
    buckets = defaultdict(lambda: {"blocks": 0, "runs": 0, "left": 0, "still": 0})

    def week_key(d: str):
        dt = datetime.strptime(d, "%Y-%m-%d")
        y, w, _ = dt.isocalendar()
        return f"{y}-W{w:02d}"

    for r in rows:
        d = r["run_date"]
        if granularity == "day":
            k = d
        elif granularity == "week":
            k = week_key(d)
        elif granularity == "month":
            k = d[:7]
        else:
            k = d[:4]
        buckets[k]["blocks"] += int(r["total_unique_blocks"] or 0)
        buckets[k]["runs"] += 1
        buckets[k]["left"] += int(r["left_platform"] or 0)
        buckets[k]["still"] += int(r["still_on_platform"] or 0)

    keys = sorted(buckets.keys())
    return [
        {
            "label": k,
            "total_blocks": buckets[k]["blocks"],
            "run_count": buckets[k]["runs"],
            "left_platform": buckets[k]["left"],
            "still_on_platform": buckets[k]["still"],
        }
        for k in keys
    ]


@bp.route('/statistics', methods=['GET'])
def statistics():
    """granularity=day|week|month|year; optional from=YYYY-MM-DD, to=YYYY-MM-DD"""
    g = (request.args.get("granularity") or "day").lower()
    if g not in ("day", "week", "month", "year"):
        g = "day"
    to_s = request.args.get("to") or datetime.utcnow().date().isoformat()
    to_dt = datetime.strptime(to_s[:10], "%Y-%m-%d")
    if g == "day":
        n = int(request.args.get("days") or 30)
        from_dt = to_dt - timedelta(days=max(1, n) - 1)
    elif g == "week":
        n = int(request.args.get("weeks") or 12)
        from_dt = to_dt - timedelta(weeks=max(1, n))
    elif g == "month":
        n = int(request.args.get("months") or 12)
        from_dt = to_dt - timedelta(days=31 * max(1, n))
    else:
        n = int(request.args.get("years") or 5)
        from_dt = datetime(to_dt.year - max(1, n) + 1, 1, 1)
    from_s = from_dt.date().isoformat()
    nvr_id = request.args.get("nvr_id", type=int)
    series = _statistics_series(g, from_s, to_s, nvr_id)
    totals = {
        "total_blocks": sum(p["total_blocks"] for p in series),
        "total_runs": sum(p["run_count"] for p in series),
        "buckets": len(series),
    }
    return jsonify({
        "granularity": g,
        "from": from_s,
        "to": to_s,
        "series": series,
        "totals": totals,
    })


@bp.route('/statistics/seed-demo', methods=['POST'])
def statistics_seed_demo():
    seed_demo_statistics_if_empty()
    return jsonify({"ok": True})


@bp.route('/results', methods=['GET'])
def list_results():
    init_db()
    nvr_id = request.args.get("nvr_id", type=int)
    conn = get_conn()
    try:
        if nvr_id is not None:
            rows = conn.execute(
                '''SELECT id, nvr_id, run_date, nvr_name, channel, total_unique_blocks, left_platform,
                          still_on_platform, source, created_at FROM run_events
                   WHERE nvr_id = ? ORDER BY created_at DESC LIMIT 200''',
                (nvr_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                '''SELECT id, nvr_id, run_date, nvr_name, channel, total_unique_blocks, left_platform,
                          still_on_platform, source, created_at FROM run_events
                   ORDER BY created_at DESC LIMIT 200'''
            ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()

@bp.route('/results/summary', methods=['GET'])
def summary():
    return jsonify([])

@bp.route('/run-for-date', methods=['POST'])
def run_for_date():
    """Body: date, nvr_id?, channels?: [1..15] — one run_event per channel for Statistics."""
    data = request.get_json() or {}
    ch = data.get('channels')
    out_ch = []
    if isinstance(ch, list):
        for x in ch:
            try:
                n = int(x)
                if 1 <= n <= 15:
                    out_ch.append(n)
            except (TypeError, ValueError):
                pass
        out_ch = sorted(set(out_ch))
    if not out_ch:
        out_ch = list(range(1, 16))
    run_date = (data.get('date') or '')[:10]
    if len(run_date) < 10:
        run_date = datetime.utcnow().date().isoformat()
    nvr_id = data.get('nvr_id')
    nvr_name = None
    try:
        nid = int(nvr_id) if nvr_id is not None else None
    except (TypeError, ValueError):
        nid = None
    if nid is not None:
        init_db()
        conn = get_conn()
        try:
            row = conn.execute('SELECT name FROM nvrs WHERE id = ?', (nid,)).fetchone()
            if row:
                nvr_name = row['name']
        finally:
            conn.close()
    for c in out_ch:
        try:
            insert_run_event(
                run_date, 0, 0, 0,
                nvr_id=nid, nvr_name=nvr_name, channel=c,
                source='nvr_recording',
            )
        except Exception:
            pass
    return jsonify({
        'status': 'accepted',
        'date': run_date,
        'nvr_id': nid,
        'channels_1_15': out_ch,
        'message': 'Recorded per channel for Statistics. Wire Dahua + model for real block counts.',
    })

@bp.route('/job-progress', methods=['GET'])
def job_progress():
    total = _job.get("frames_total") or 0
    done = _job.get("frames_done") or 0
    return jsonify({
        'running': _job['running'],
        'progress': _job['progress'],
        'current': _job['current'],
        'error': _job['error'],
        'result': _job['result'] if not _job['running'] else None,
        'frames_done': done,
        'frames_total': total,
        'frames_left': max(0, total - done) if _job['running'] else 0,
        'percent': round(100.0 * done / total, 1) if total and _job['running'] else (100.0 if not _job['running'] and _job.get('result') else 0),
        'seconds_into_video': _job.get('seconds_into_video', 0),
    })

@bp.route('/test-video', methods=['POST'])
def test_video():
    """Run Solution.py-style pipeline on a local video path."""
    from app.path_util import normalize_video_path, resolve_video_path, is_drive_or_http
    data = request.get_json() or {}
    raw = (data.get('video_path') or '').strip()
    if not raw:
        return jsonify({'error': 'video_path required (local file path)'}), 400
    if is_drive_or_http(raw):
        return jsonify({
            'error': 'Google Drive / HTTP links are not supported. Download the file, then use the full local path (e.g. D:\\Videos\\file.mp4).',
        }), 400
    path = normalize_video_path(raw)
    if path:
        path = resolve_video_path(path) or path
    if not path or not os.path.isfile(path):
        return jsonify({'error': f'Video file not found: {raw!r}'}), 400
    if _job['running']:
        return jsonify({'error': 'A run is already in progress'}), 409
    model_path = data.get('model_path') or _default_model_path()
    if not os.path.isfile(model_path):
        return jsonify({'error': f'Model not found at {model_path!r}. Place best (1).pt in project root.'}), 400
    max_frames = data.get('max_frames')
    if max_frames is not None:
        try:
            max_frames = int(max_frames)
            if max_frames < 1:
                max_frames = None
        except (TypeError, ValueError):
            max_frames = None
    t = threading.Thread(
        target=_run_test_video_thread,
        args=(path, model_path),
        kwargs={'max_frames': max_frames},
        daemon=True,
    )
    t.start()
    return jsonify({'status': 'started', 'video_path': path, 'max_frames': max_frames})

@bp.route('/debug', methods=['GET'])
def debug():
    root = _project_root()
    mp = _default_model_path()
    return jsonify({
        'project_root': root,
        'default_model_path': mp,
        'model_exists': os.path.isfile(mp),
        'backend_cwd': os.getcwd(),
    })
