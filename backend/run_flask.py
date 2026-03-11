#!/usr/bin/env python3
"""Run Flask app for Ice Factory Block Counter backend."""
import argparse
import sys
import os

# Ensure backend and project root are on path when run from backend/ or project root
_backend_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_backend_dir)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()
    from app import create_app
    app = create_app()
    app.run(host='127.0.0.1', port=args.port, debug=False, use_reloader=False)

if __name__ == '__main__':
    main()
