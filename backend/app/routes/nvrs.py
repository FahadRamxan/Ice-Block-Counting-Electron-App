from flask import Blueprint, request, jsonify
from app.db import get_conn, init_db

bp = Blueprint('nvrs', __name__, url_prefix='/api/nvrs')

@bp.route('', methods=['GET'])
def list_nvrs():
    init_db()
    conn = get_conn()
    try:
        rows = conn.execute(
            'SELECT id, name, ip, port, username, created_at FROM nvrs ORDER BY id'
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()

@bp.route('', methods=['POST'])
def add():
    init_db()
    data = request.get_json() or {}
    name = (data.get('name') or '').strip() or 'NVR'
    ip = (data.get('ip') or '').strip()
    port = int(data.get('port') or 37777)
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    if not ip:
        return jsonify({'error': 'IP required'}), 400
    conn = get_conn()
    try:
        cur = conn.execute(
            'INSERT INTO nvrs (name, ip, port, username, password) VALUES (?,?,?,?,?)',
            (name, ip, port, username, password),
        )
        conn.commit()
        row = conn.execute(
            'SELECT id, name, ip, port, username, created_at FROM nvrs WHERE id = ?',
            (cur.lastrowid,),
        ).fetchone()
        return jsonify(dict(row)), 201
    finally:
        conn.close()

@bp.route('/<int:nvr_id>', methods=['DELETE'])
def delete(nvr_id):
    init_db()
    conn = get_conn()
    try:
        conn.execute('DELETE FROM nvrs WHERE id = ?', (nvr_id,))
        conn.commit()
        return '', 204
    finally:
        conn.close()
