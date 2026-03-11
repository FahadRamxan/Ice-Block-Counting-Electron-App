"""NVR config CRUD API."""
from flask import Blueprint, request, jsonify
from app.db import get_conn, init_db

bp = Blueprint('nvrs', __name__, url_prefix='/api/nvrs')

@bp.route('', methods=['GET'])
def list_nvrs():
    init_db()
    conn = get_conn()
    try:
        rows = conn.execute('SELECT id, name, ip, port, username, created_at FROM nvrs ORDER BY id').fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()

@bp.route('', methods=['POST'])
def add_nvr():
    init_db()
    data = request.get_json() or {}
    name = data.get('name', '').strip() or 'Unnamed NVR'
    ip = (data.get('ip') or '').strip()
    port = int(data.get('port') or 37777)
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    if not ip:
        return jsonify({'error': 'IP is required'}), 400
    conn = get_conn()
    try:
        cur = conn.execute(
            'INSERT INTO nvrs (name, ip, port, username, password) VALUES (?,?,?,?,?)',
            (name, ip, port, username, password)
        )
        conn.commit()
        row = conn.execute('SELECT id, name, ip, port, username, created_at FROM nvrs WHERE id = ?', (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201
    finally:
        conn.close()

@bp.route('/<int:nvr_id>', methods=['DELETE'])
def delete_nvr(nvr_id):
    init_db()
    conn = get_conn()
    try:
        conn.execute('DELETE FROM nvrs WHERE id = ?', (nvr_id,))
        conn.commit()
        return '', 204
    finally:
        conn.close()

@bp.route('/<int:nvr_id>', methods=['PATCH'])
def update_nvr(nvr_id):
    init_db()
    data = request.get_json() or {}
    conn = get_conn()
    try:
        row = conn.execute('SELECT id FROM nvrs WHERE id = ?', (nvr_id,)).fetchone()
        if not row:
            return jsonify({'error': 'NVR not found'}), 404
        updates = []
        params = []
        for key in ('name', 'ip', 'port', 'username', 'password'):
            if key in data:
                if key == 'port':
                    params.append(int(data[key]))
                else:
                    params.append((data[key] or '').strip())
                updates.append(f'{key}=?')
        if not updates:
            row = conn.execute('SELECT id, name, ip, port, username, created_at FROM nvrs WHERE id = ?', (nvr_id,)).fetchone()
            return jsonify(dict(row))
        params.append(nvr_id)
        conn.execute(f"UPDATE nvrs SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        row = conn.execute('SELECT id, name, ip, port, username, created_at FROM nvrs WHERE id = ?', (nvr_id,)).fetchone()
        return jsonify(dict(row))
    finally:
        conn.close()
