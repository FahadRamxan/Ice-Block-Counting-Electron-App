from flask import Blueprint, request, jsonify
from app.db import get_conn, init_db
from app.nvr_service import get_recordings_all_channels

bp = Blueprint('recordings', __name__, url_prefix='/api/recordings')

@bp.route('/by-date', methods=['POST'])
def by_date():
    """Body: { nvr_id, date, channels: 'all' | [0,1,2] }"""
    data = request.get_json() or {}
    nvr_id = data.get('nvr_id')
    record_date = data.get('date')
    channels = data.get('channels', 'all')
    if not nvr_id or not record_date:
        return jsonify({'error': 'nvr_id and date required'}), 400
    init_db()
    conn = get_conn()
    try:
        row = conn.execute(
            'SELECT id, name, ip, port, username, password FROM nvrs WHERE id = ?',
            (nvr_id,),
        ).fetchone()
        if not row:
            return jsonify({'error': 'NVR not found'}), 404
        nvr = dict(row)
    finally:
        conn.close()
    ch_filter = None
    if channels != 'all' and isinstance(channels, list):
        ch_filter = [int(c) for c in channels if str(c).isdigit() or isinstance(c, int)]
    result = get_recordings_all_channels(
        nvr['ip'], nvr['port'], nvr['username'], nvr['password'],
        record_date, channels_filter=ch_filter,
    )
    if result.get('error') and not result.get('recordings_by_channel'):
        return jsonify({'nvr_id': nvr_id, 'nvr_name': nvr['name'], 'date': record_date, 'error': result['error']}), 200
    return jsonify({
        'nvr_id': nvr_id,
        'nvr_name': nvr['name'],
        'date': record_date,
        'nvr_channels': result.get('nvr_channels'),
        'recordings_by_channel': result.get('recordings_by_channel', {}),
        'error': result.get('error'),
    })
