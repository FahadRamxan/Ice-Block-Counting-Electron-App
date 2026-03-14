from flask import Flask
from flask_cors import CORS
from app.db import init_db, seed_demo_statistics_if_empty
from app.routes import nvrs_bp, recordings_bp, runs_bp

def create_app():
    app = Flask(__name__)
    CORS(app)
    init_db()
    seed_demo_statistics_if_empty()
    @app.route('/api/status')
    def status():
        return {'status': 'ok', 'app': 'ice-factory-block-counter'}
    app.register_blueprint(nvrs_bp)
    app.register_blueprint(recordings_bp)
    app.register_blueprint(runs_bp)
    return app
