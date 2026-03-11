"""Recordings API — stub only. To be redesigned."""
from flask import Blueprint, request, jsonify

bp = Blueprint('recordings', __name__, url_prefix='/api/recordings')

@bp.route('/by-date', methods=['GET'])
def list_by_date():
    nvr_id = request.args.get('nvr_id', type=int)
    record_date = request.args.get('date')
    if not nvr_id or not record_date:
        return jsonify({'error': 'nvr_id and date (YYYY-MM-DD) required'}), 400
    return jsonify({
        'nvr_id': nvr_id,
        'nvr_name': '',
        'date': record_date or '',
        'recordings': [],
    })
