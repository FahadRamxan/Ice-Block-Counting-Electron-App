r"""
Test the ice-block model on a single video file.
Run from project root:
  python backend/run_test_video.py "D:\path\to\video.mp4"
  python backend/run_test_video.py "D:\path\to\video.mp4" "D:\path\to\best.pt"
Or with env vars:
  $env:TEST_VIDEO='D:\path\to\video.mp4'; $env:MODEL_PATH='D:\path\to\best.pt'; python backend/run_test_video.py
By default the script looks for best_9_3_2026.pt or best (1).pt in the project root.
"""
import os
import sys
import json

# Project root = parent of backend
_backend = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_backend)
if _root not in sys.path:
    sys.path.insert(0, _root)

# Unicode space chars that can appear in filenames (e.g. from Explorer "Copy as path")
_UNICODE_SPACES = "\u00a0\u2007\u202f"  # no-break, figure space, narrow no-break

def normalize_path(raw):
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    for c in _UNICODE_SPACES:
        s = s.replace(c, " ")
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1].strip()
    if not s:
        return None
    return os.path.normpath(s)

def _path_candidates(path):
    """Return path and alternates to try (e.g. forward slashes) so PowerShell \\ doesn't break."""
    out = [path]
    if "\\" in path:
        out.append(os.path.normpath(path.replace("\\", "/")))
    return out

def _find_file_with_unicode_spaces(path):
    """If path not found, look in same folder for a file that matches when Unicode spaces are normalized."""
    folder = os.path.dirname(path)
    base = os.path.basename(path)
    base_normalized = base
    for c in _UNICODE_SPACES:
        base_normalized = base_normalized.replace(c, " ")
    if not os.path.isdir(folder):
        return None
    try:
        for name in os.listdir(folder):
            name_normalized = name
            for c in _UNICODE_SPACES:
                name_normalized = name_normalized.replace(c, " ")
            if name_normalized == base_normalized:
                return os.path.join(folder, name)
    except OSError:
        pass
    return None

def main():
    video_path = os.environ.get("TEST_VIDEO") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if not video_path:
        print(json.dumps({"error": "Usage: python backend/run_test_video.py <video_path>", "total_count": 0}))
        sys.exit(1)

    video_path = normalize_path(video_path)
    resolved = None
    for candidate in _path_candidates(video_path):
        if os.path.isfile(candidate):
            resolved = candidate
            break
    if resolved is None:
        resolved = _find_file_with_unicode_spaces(video_path)
    if resolved is None:
        folder = os.path.dirname(video_path)
        mp4_in_folder = []
        if os.path.isdir(folder):
            try:
                mp4_in_folder = [f for f in os.listdir(folder) if f.lower().endswith((".mp4", ".avi", ".mkv"))][:20]
            except OSError:
                pass
        print(json.dumps({
            "error": f"Video file not found: {video_path!r}",
            "total_count": 0,
            "folder_checked": folder,
            "video_files_in_folder": mp4_in_folder if mp4_in_folder else "(none or not readable)",
            "hint": "Check the filename (e.g. space in '9 PM'). Use exact path from Explorer (Copy as path).",
        }))
        sys.exit(1)
    video_path = resolved

    # Model: optional env MODEL_PATH or second argument; else project root
    model_path = os.environ.get("MODEL_PATH") or (sys.argv[2] if len(sys.argv) > 2 else None)
    if model_path:
        model_path = normalize_path(model_path)
    if not model_path or not os.path.isfile(model_path):
        for name in ["best_9_3_2026.pt", "best (1).pt"]:
            p = os.path.join(_root, name)
            if os.path.isfile(p):
                model_path = p
                break
        else:
            model_path = os.path.join(_root, "best (1).pt")
    if not os.path.isfile(model_path):
        used_example = "path" in (model_path or "").lower() and "your" in (model_path or "").lower()
        print(json.dumps({
            "error": "Model not found. Use the real path to your .pt file (where best (1).pt or best_9_3_2026.pt is on your PC)." + (" You passed an example path; replace it with your actual file path." if used_example else ""),
            "total_count": 0,
            "model_path_tried": model_path,
            "project_root": _root,
            "hint": "Find your .pt in File Explorer, copy path, then: python backend/run_test_video.py '<video>' '<paste path here>'",
        }))
        sys.exit(1)

    sys.path.insert(0, _backend)
    import model_runner
    print("Running model on video (this may take 1-2 min)...", file=sys.stderr)
    result = model_runner.run_count(video_path, model_path)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
