# Solution.py — how it runs & app parity

## Prerequisites (same for CLI `Solution.py` and app “Run model on test video”)

| Requirement | Notes |
|-------------|--------|
| **Python 3.10+** | Project venv recommended |
| **opencv-python, numpy, pandas, ultralytics** | `pip install -r requirements.txt` |
| **YOLO weights** | `best (1).pt` or `best_9_3_2026.pt` in **project root** (`D:\Ice-Block-Counting-Electron-App\`) |
| **Video file** | Readable by OpenCV (e.g. `.mp4`). **Local path only** — not Google Drive URLs (download first) |
| **GPU** | Optional; CPU works but slower |

Env overrides for `Solution.py` only:

- `VIDEO_PATH` — input video  
- `MODEL_PATH` — `.pt` file  

## What Solution.py outputs (all shown in the app after a run)

1. **Header (logs)**  
   - `Video : WxH @ fps`  
   - `Range : start_s → end_s`  
   - Dup / Re-ID / Memory lines  

2. **Per ~1s of video (logs)**  
   - `t=…s | on:… | TOTAL:… | active:… mem:… | tracks:…`  

3. **Summary (UI KPIs + logs)**  
   - **Total unique blocks on platform** → `total_unique_blocks`  
   - **Still on platform at end** → `still_on_platform_end`  
   - **Left platform** → `left_platform`  

4. **Files written** (paths on server; shown in UI)  
   - **Annotated video** — same role as `ice_block_total_count.avi` (timestamped under `backend/data/outputs/`)  
   - **Event CSV** — same role as `ice_block_events.csv` (per-frame track log)  

5. **Full log** — expandable block in the app = every printed line above.

## App: test video

1. Start backend: `python backend/run_flask.py`  
2. Open app → **Settings** → **Run model on test video (Solution.py)**  
3. Paste **local path**, click **Run on this video**  
4. Wait (long videos = minutes) → see counts, paths, full log.

Drive / HTTP: not supported; error explains to download and use local path.
