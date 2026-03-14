"""Normalize video paths (quotes, Unicode spaces)."""
import os

UNICODE_SPACES = "\u00a0\u2007\u202f"

def normalize_video_path(raw):
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    for c in UNICODE_SPACES:
        s = s.replace(c, " ")
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1].strip()
    if not s:
        return None
    return os.path.normpath(s)

def resolve_video_path(path):
    if not path:
        return None
    if os.path.isfile(path):
        return path
    folder = os.path.dirname(path)
    base = os.path.basename(path)
    base_n = base
    for c in UNICODE_SPACES:
        base_n = base_n.replace(c, " ")
    if not os.path.isdir(folder):
        return None
    try:
        for name in os.listdir(folder):
            n = name
            for c in UNICODE_SPACES:
                n = n.replace(c, " ")
            if n == base_n:
                return os.path.join(folder, name)
    except OSError:
        pass
    return None

def is_drive_or_http(s):
    s = (s or "").strip().lower()
    return s.startswith("http://") or s.startswith("https://")
