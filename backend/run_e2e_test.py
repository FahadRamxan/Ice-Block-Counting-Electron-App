"""
End-to-end test: same flow as the app (model_runner with video + model path).
Run from project root:
  python backend/run_e2e_test.py [video_path]
If no video_path, uses VIDEO_PATH from Solution.py default or env VIDEO_PATH.
Prints the same result the backend would produce (total_count or error).
"""
import os
import sys
import json

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_backend = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

def main():
    video_path = (sys.argv[1].strip() if len(sys.argv) > 1 else None) or os.environ.get("VIDEO_PATH")
    if not video_path:
        print(json.dumps({
            "error": "Provide video path: python backend/run_e2e_test.py <video_path>",
            "total_count": 0,
        }, indent=2))
        sys.exit(1)

    video_path = os.path.normpath(video_path.strip().strip('"'))
    if not os.path.isfile(video_path):
        print(json.dumps({
            "error": f"Video file not found: {video_path!r}",
            "total_count": 0,
        }, indent=2))
        sys.exit(1)

    for name in ["best_9_3_2026.pt", "best (1).pt"]:
        model_path = os.path.join(_root, name)
        if os.path.isfile(model_path):
            break
    else:
        model_path = os.path.join(_root, "best (1).pt")
    if not os.path.isfile(model_path):
        print(json.dumps({
            "error": f"Model not found. Place best_9_3_2026.pt or best (1).pt in {_root!r}",
            "total_count": 0,
        }, indent=2))
        sys.exit(1)

    import model_runner
    print("Running model (same as backend)...", file=sys.stderr)
    result = model_runner.run_count(video_path, model_path)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("error") is None else 1)

if __name__ == "__main__":
    main()
