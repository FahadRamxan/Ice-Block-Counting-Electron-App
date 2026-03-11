#!/usr/bin/env python3
"""Print project root and default model path as resolved by the backend. Run from project root."""
import os
import sys

# Same resolution as runs.py
_backend_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_backend_dir)

def main():
    print("Project root:", _root)
    for name in ["best_9_3_2026.pt", "best (1).pt"]:
        p = os.path.join(_root, name)
        exists = os.path.isfile(p)
        print(f"  {name}: {'OK' if exists else 'NOT FOUND'}")
    default = os.path.join(_root, "best (1).pt")
    print("Default model path (when no file found):", default)
    if not any(os.path.isfile(os.path.join(_root, n)) for n in ["best_9_3_2026.pt", "best (1).pt"]):
        print("WARNING: Place best_9_3_2026.pt or best (1).pt in project root for run-for-date / test video.")
        sys.exit(1)

if __name__ == "__main__":
    main()
