"""NVR API — stub only. To be redesigned."""
from flask import Blueprint, request, jsonify

bp = Blueprint('nvrs', __name__, url_prefix='/api/nvrs')

@bp.route('', methods=['GET'])
def list_nvrs():
    return jsonify([])

@bp.route('', methods=['POST'])
def add_nvr():
    data = request.get_json() or {}
    return jsonify({
        'id': 0,
        'name': (data.get('name') or '').strip() or 'Unnamed NVR',
        'ip': (data.get('ip') or '').strip() or '0.0.0.0',
        'port': int(data.get('port') or 37777),
        'username': (data.get('username') or '').strip(),
        'created_at': '',
    }), 201

@bp.route('/<int:nvr_id>', methods=['DELETE'])
def delete_nvr(nvr_id):
    return '', 204

@bp.route('/<int:nvr_id>', methods=['PATCH'])
def update_nvr(nvr_id):
    return jsonify({'error': 'Not implemented'}), 501
