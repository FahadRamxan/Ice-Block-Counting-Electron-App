"""Run results and run-for-date job API."""
import os
from flask import Blueprint, request, jsonify
from app.db import get_conn, init_db
from app.run_job import start_run_for_date_async, get_job_state
from app.path_util import normalize_video_path, resolve_video_path

bp = Blueprint('runs', __name__, url_prefix='/api/runs')

def _project_root():
    # Same as run_flask.py: backend dir = dirname(run_flask.py), root = dirname(backend)
    # From backend/app/routes/runs.py go up to backend (3 levels), then root = dirname(backend)
    _here = os.path.abspath(__file__)
    _routes = os.path.dirname(_here)
    _app = os.path.dirname(_routes)
    _backend = os.path.dirname(_app)
    return os.path.dirname(_backend)

def _default_model_path():
    root = _project_root()
    for name in ['best_9_3_2026.pt', 'best (1).pt']:
        p = os.path.join(root, name)
        if os.path.isfile(p):
            return p
    return os.path.join(root, 'best (1).pt')

@bp.route('/results', methods=['GET'])
def list_results():
    init_db()
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    nvr_id = request.args.get('nvr_id', type=int)
    conn = get_conn()
    try:
        conditions = []
        params = []
        if date_from:
            conditions.append('record_date >= ?')
            params.append(date_from)
        if date_to:
            conditions.append('record_date <= ?')
            params.append(date_to)
        if nvr_id:
            conditions.append('nvr_id = ?')
            params.append(nvr_id)
        q = 'SELECT * FROM run_results'
        if conditions:
            q += ' WHERE ' + ' AND '.join(conditions)
        q += ' ORDER BY created_at DESC LIMIT 500'
        rows = conn.execute(q, params).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()

@bp.route('/results/summary', methods=['GET'])
def summary():
    init_db()
    date = request.args.get('date')
    conn = get_conn()
    try:
        if date:
            rows = conn.execute(
                'SELECT nvr_id, nvr_name, channel, record_date, SUM(ice_block_count) as total_blocks FROM run_results WHERE record_date = ? GROUP BY nvr_id, nvr_name, channel, record_date',
                (date,)
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT nvr_id, nvr_name, channel, record_date, SUM(ice_block_count) as total_blocks FROM run_results GROUP BY nvr_id, nvr_name, channel, record_date ORDER BY record_date DESC LIMIT 100'
            ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()



@bp.route('/run-for-date', methods=['POST'])
def run_for_date():
    data = request.get_json() or {}
    record_date = data.get('date')
    nvr_ids = data.get('nvr_ids')
    raw_path = data.get('test_video_path') or os.environ.get('TEST_VIDEO_PATH')
    test_video_path = normalize_video_path(raw_path)
    if test_video_path:
        test_video_path = resolve_video_path(test_video_path)  # match filename with Unicode space (e.g. \u202f)
    if not record_date:
        return jsonify({'error': 'date (YYYY-MM-DD) required'}), 400
    init_db()
    conn = get_conn()
    try:
        if nvr_ids:
            placeholders = ','.join('?' * len(nvr_ids))
            rows = conn.execute(
                f'SELECT id, name, ip, port, username, password FROM nvrs WHERE id IN ({placeholders})',
                nvr_ids,
            ).fetchall()
        else:
            rows = conn.execute('SELECT id, name, ip, port, username, password FROM nvrs').fetchall()
        nvr_list = [dict(r) for r in rows]
    finally:
        conn.close()
    # When user provided a test video path, validate it so we can return a clear error
    if raw_path and (normalize_video_path(raw_path)) and not test_video_path:
        return jsonify({
            'error': f'Test video file not found. Check that the path is correct and the file exists.',
        }), 400
    # Allow test-video-only run when no NVRs: use a dummy NVR so the job runs once on the video
    if not nvr_list and test_video_path:
        nvr_list = [{"id": 0, "name": "Test video", "ip": "", "port": 37777, "username": "", "password": ""}]
    if not nvr_list:
        return jsonify({'error': 'No NVRs configured. Add an NVR or provide a test video path to run on a single file.'}), 400
    model_path = data.get('model_path') or _default_model_path()
    start_run_for_date_async(nvr_list, record_date, model_path, test_video_path=test_video_path)
    return jsonify({'status': 'started', 'date': record_date, 'nvrs': len(nvr_list)})

@bp.route('/job-progress', methods=['GET'])
def job_progress():
    return jsonify(get_job_state())


@bp.route('/debug', methods=['GET'])
def debug():
    """Return project root and model path so frontend/CLI can verify backend sees the right paths."""
    root = _project_root()
    model_path = _default_model_path()
    return jsonify({
        'project_root': root,
        'default_model_path': model_path,
        'model_exists': os.path.isfile(model_path),
        'backend_cwd': os.getcwd(),
    })
