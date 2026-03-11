"""Recordings discovery: list recordings by date for all channels (uses Dahua SDK when available)."""
from flask import Blueprint, request, jsonify
from app.db import get_conn, init_db
from app.nvr_service import get_recordings_for_date

bp = Blueprint('recordings', __name__, url_prefix='/api/recordings')

@bp.route('/by-date', methods=['GET'])
def list_by_date():
    nvr_id = request.args.get('nvr_id', type=int)
    record_date = request.args.get('date')  # YYYY-MM-DD
    if not nvr_id or not record_date:
        return jsonify({'error': 'nvr_id and date (YYYY-MM-DD) required'}), 400
    init_db()
    conn = get_conn()
    try:
        nvr = conn.execute('SELECT id, name, ip, port, username, password FROM nvrs WHERE id = ?', (nvr_id,)).fetchone()
        if not nvr:
            return jsonify({'error': 'NVR not found'}), 404
        nvr = dict(nvr)
    finally:
        conn.close()
    recordings = get_recordings_for_date(
        ip=nvr['ip'], port=nvr['port'], username=nvr['username'], password=nvr['password'],
        record_date=record_date
    )
    if isinstance(recordings, dict) and 'error' in recordings:
        return jsonify(recordings), 500
    return jsonify({'nvr_id': nvr_id, 'nvr_name': nvr['name'], 'date': record_date, 'recordings': recordings})
