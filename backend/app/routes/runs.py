"""Runs API — stub only. To be redesigned."""
from flask import Blueprint, request, jsonify

bp = Blueprint('runs', __name__, url_prefix='/api/runs')

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
    return jsonify({
        'running': False,
        'progress': [],
        'current': None,
        'error': None,
    })

@bp.route('/debug', methods=['GET'])
def debug():
    return jsonify({
        'project_root': '',
        'default_model_path': '',
        'model_exists': False,
        'backend_cwd': '',
    })
