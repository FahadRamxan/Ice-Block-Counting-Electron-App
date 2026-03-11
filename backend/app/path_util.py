"""Shared path normalization for video paths (Unicode spaces, quotes, resolve actual file)."""
import os

UNICODE_SPACES = "\u00a0\u2007\u202f"  # no-break, figure space, narrow no-break


def normalize_video_path(raw):
    """Strip quotes, normalize Unicode spaces to space, normpath. Return None if empty."""
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    for c in UNICODE_SPACES:
        s = s.replace(c, " ")
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1].strip()
    if not s:
        return None
    s = os.path.normpath(s)
    if os.path.isabs(s):
        return s
    return os.path.abspath(s)


def resolve_video_path(path):
    """
    Return path if file exists. Else look in same folder for a file whose name
    matches when Unicode spaces are normalized (e.g. '9 PM' matches '9\u202fPM').
    """
    if not path:
        return None
    if os.path.isfile(path):
        return path
    folder = os.path.dirname(path)
    base = os.path.basename(path)
    base_normalized = base
    for c in UNICODE_SPACES:
        base_normalized = base_normalized.replace(c, " ")
    if not os.path.isdir(folder):
        return None
    try:
        for name in os.listdir(folder):
            name_normalized = name
            for c in UNICODE_SPACES:
                name_normalized = name_normalized.replace(c, " ")
            if name_normalized == base_normalized:
                return os.path.join(folder, name)
    except OSError:
        pass
    return None
