"""Runs API — test video (Solution.py pipeline) + stubs for legacy routes."""
import os
import threading
from flask import Blueprint, request, jsonify

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
    except Exception as e:
        _job["error"] = str(e)
        _job["current"] = str(e)
    finally:
        _job["running"] = False


@bp.route('/results', methods=['GET'])
def list_results():
    return jsonify([])

@bp.route('/results/summary', methods=['GET'])
def summary():
    return jsonify([])

@bp.route('/run-for-date', methods=['POST'])
def run_for_date():
    return jsonify({'status': 'started', 'date': (request.get_json() or {}).get('date', ''), 'nvrs': 0})

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
