"""
Run-for-date job: for each NVR, each channel, get recordings, run model, save results.
Uses optional video download (Dahua SDK); if not available, uses TEST_VIDEO_PATH for testing.
"""
import os
import sys
import json
import threading

_backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_root = os.path.dirname(_backend)
for p in (_backend, _root):
    if p not in sys.path:
        sys.path.insert(0, p)

# In-process progress store
_job_state = {"running": False, "progress": [], "current": None, "error": None}

def get_job_state():
    return dict(_job_state)

def clear_job_state():
    _job_state["running"] = False
    _job_state["progress"] = []
    _job_state["current"] = None
    _job_state["error"] = None

def run_for_date(nvr_list, record_date, model_path, test_video_path=None):
    """
    nvr_list: list of dicts with id, name, ip, port, username, password
    record_date: YYYY-MM-DD
    model_path: path to .pt model
    test_video_path: if set, use this video for every recording (when download not available)
    """
    from app.db import get_conn, init_db
    from app.nvr_service import get_recordings_for_date

    init_db()
    _job_state["running"] = True
    _job_state["progress"] = []
    _job_state["current"] = "Starting..."
    _job_state["error"] = None

    try:
        if not os.path.isfile(model_path):
            _job_state["error"] = f"Model not found: {model_path}"
            _job_state["current"] = _job_state["error"]
            _job_state["running"] = False
            return
        # Import model_runner from backend (parent of app)
        import model_runner
        run_count_fn = model_runner.run_count
    except Exception as e:
        _job_state["error"] = str(e)
        _job_state["current"] = f"Error: {e}"
        _job_state["running"] = False
        return

    # Normalize and resolve path (Unicode spaces, quotes; resolve filename with \u202f etc.)
    from app.path_util import normalize_video_path, resolve_video_path
    _norm_path = normalize_video_path(test_video_path)
    if _norm_path:
        _norm_path = resolve_video_path(_norm_path)
    if test_video_path and (normalize_video_path(test_video_path)) and not _norm_path:
        _job_state["error"] = "Test video file not found. Check path and that the file exists."
        _job_state["current"] = _job_state["error"]
        _job_state["running"] = False
        return
    video_to_use = _norm_path if _norm_path and os.path.isfile(_norm_path) else None
    total_done = 0
    total_items = 0
    conn = get_conn()
    try:
        nvrs = nvr_list
        for nvr in nvrs:
            nvr_id = nvr["id"]
            nvr_name = nvr.get("name", f"NVR {nvr_id}")
            # Test-video-only: dummy NVR has no ip; skip SDK and use one slot with test video
            if not (nvr.get("ip") or "").strip() and video_to_use:
                _job_state["current"] = f"{nvr_name}: preparing to run on test video..."
                recordings = []
            else:
                _job_state["current"] = f"NVR {nvr_name}: fetching recordings..."
                recordings = get_recordings_for_date(
                    ip=nvr["ip"], port=nvr["port"], username=nvr["username"], password=nvr["password"],
                    record_date=record_date,
                )
            if isinstance(recordings, dict) and "error" in recordings:
                _job_state["progress"].append({
                    "nvr_id": nvr_id, "nvr_name": nvr_name, "channel": None,
                    "status": "error", "message": recordings["error"],
                })
                continue
            if not recordings and not video_to_use:
                _job_state["progress"].append({
                    "nvr_id": nvr_id, "nvr_name": nvr_name, "channel": None,
                    "status": "skipped", "message": "No recordings",
                })
                continue
            if not recordings and video_to_use:
                recordings = [{"channel": 0, "start_ts": f"{record_date} 00:00:00", "end_ts": f"{record_date} 23:59:59"}]
            for rec in recordings:
                total_items += 1
                channel = rec.get("channel", 0)
                start_ts = rec.get("start_ts", "")
                end_ts = rec.get("end_ts", "")
                _job_state["current"] = f"{nvr_name} Ch{channel} — running model on video..."
                video_path = video_to_use  # TODO: real download from NVR by time range
                if not video_path:
                    _job_state["progress"].append({
                        "nvr_id": nvr_id, "nvr_name": nvr_name, "channel": channel,
                        "start_time": start_ts, "end_time": end_ts,
                        "status": "skipped", "message": "No video (install Dahua SDK for download)",
                    })
                    continue
                _job_state["current"] = f"{nvr_name} Ch{channel} — running YOLO on video (may take 1–2 min)..."
                result = run_count_fn(video_path, model_path)
                total_count = result.get("total_count", 0)
                err = result.get("error")
                status = "completed" if not err else "error"
                # Save every run (including test-video nvr_id=0) so results show in Dashboard
                try:
                    conn.execute(
                        """INSERT INTO run_results (nvr_id, nvr_name, channel, record_date, start_time, end_time, ice_block_count, status, video_path)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        (nvr_id, nvr_name, channel, record_date, start_ts, end_ts, total_count, status, video_path),
                    )
                    conn.commit()
                except Exception as db_err:
                    # If FK blocks nvr_id=0, at least progress list still shows the count
                    pass
                total_done += 1
                _job_state["progress"].append({
                    "nvr_id": nvr_id, "nvr_name": nvr_name, "channel": channel,
                    "start_time": start_ts, "end_time": end_ts,
                    "ice_block_count": total_count, "status": status, "error": err,
                })
    except Exception as e:
        _job_state["error"] = str(e)
        _job_state["current"] = f"Error: {e}"
    finally:
        conn.close()
        _job_state["running"] = False
        _job_state["current"] = _job_state.get("error") or f"Done. Processed {total_done} recordings."


def start_run_for_date_async(nvr_list, record_date, model_path, test_video_path=None):
    t = threading.Thread(
        target=run_for_date,
        args=(nvr_list, record_date, model_path),
        kwargs={"test_video_path": test_video_path or None},
    )
    t.daemon = True
    t.start()
