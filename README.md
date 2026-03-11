# Ice Factory Block Counter

Desktop app for counting ice blocks from NVR recordings (anti-theft). Supports **multiple NVRs**, runs the ML model on **all channels** for a selected date, and shows results on a **Super-Admin dashboard**.

## Stack

- **Electron** – desktop shell, spawns Flask
- **React (Vite)** – dashboard UI
- **Flask** – REST API (NVR config, recordings, run-for-date job, results)
- **SQLite** – NVRs and run results (no MongoDB)
- **Python** – model runner (YOLO + slot registry, same logic as `Solution.py`)

## Prerequisites

- **Node.js** 18+
- **Python** 3.10+ with venv
- **YOLO model** – place `best_9_3_2026.pt` or `best (1).pt` in project root
- **Dahua NetSDK** (optional) – for real NVR recording list and download. Without it, you can still add NVRs and use a **test video path** to run the model.

## Setup

1. **Python venv and backend deps**
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1   # Windows
   pip install -r requirements.txt
   ```

2. **Dahua NetSDK (for “Load recordings” and NVR listing)**  
   The app uses the same Dahua SDK as `Duahua_IceFactory_BlockCounter/DahuaRecordingViewer.py`. To see NVR recordings in this app, install the NetSDK wheel into **this project’s venv**:
   - **Get the wheel** — The wheel is not in this repo. Obtain `NetSDK-2.0.0.1-py3-none-win_amd64.whl` from the Dahua SDK package or from `Duahua_IceFactory_BlockCounter/dist/` if you have it. Save it somewhere (e.g. project folder or Downloads).
   - **Install it** — Use the **real path** to the wheel file (replace the path below with yours):
     ```powershell
     .\venv\Scripts\Activate.ps1
     pip install "C:\Users\fahad\Downloads\NetSDK-2.0.0.1-py3-none-win_amd64.whl"
     ```
     **The wheel is not in this repo.** You must download or copy the `.whl` file first; use the path where it actually is (e.g. Downloads). Until the file exists at that path, pip will report "file does not exist". **To run the model without NetSDK**, use **Test video (optional)** in Settings instead.
   - If NetSDK is not installed, “Load recordings from NVR” will show a clear error and you can still use a **test video path** to run the model.

3. **Frontend / Electron**
   ```bash
   npm install
   npm run build:electron
   ```

## Run (development)

**Terminal 1 – Flask**
```bash
cd backend
..\venv\Scripts\python.exe run_flask.py --port 5000
```

**Terminal 2 – Vite + Electron**
```bash
$env:NODE_ENV="development"
npm run dev
```
This starts Vite on http://localhost:3000 and opens Electron loading that URL. Electron will also try to start Flask automatically if it finds `backend/run_flask.py` and `venv`.

**Or run UI only (no Electron):**  
Start Flask as above, then `npm run dev:react` and open http://localhost:3000 in a browser.

## Usage

1. **NVRs** – Add one or more NVRs (name, IP, port, username, password). They are used in a loop for the selected date.
2. **Run for date** – Pick a date and click **Run for date**. The app will:
   - For each NVR, query recordings for **all channels** for that day (no channel selection).
   - For each recording, run the ice-block model (when video is available: real download via Dahua SDK, or a **test video path** for testing).
   - Store counts in SQLite and show progress on the dashboard.
3. **Dashboard** – Summary and results table show counts by NVR, channel, and date.

## Test video (no NVR download)

If you don’t have Dahua SDK or real NVR footage, set **Test video (optional)** to a local `.mp4` path. The run will use that file for every recording slot so you can verify the pipeline and dashboard.

### Test the model from the command line

To verify the model runs and returns a count for a single video:

```powershell
.\venv\Scripts\Activate.ps1
python backend/run_test_video.py "D:\path\to\your\video.mp4"
```

Use the full path to your `.mp4` (e.g. Copy as path from File Explorer; quotes are optional). Output is JSON: `{"total_count": N, "error": null}` or an error. Model files must be in project root: `best_9_3_2026.pt` or `best (1).pt`.

**Check that the backend will find the model** (project root should be the repo root, not `backend`):

```powershell
python backend/check_paths.py
```

If you pulled code changes, **restart the Flask backend** so it uses the updated model path (project root).

**Run the original script with a custom path** (no file edit):

```powershell
$env:VIDEO_PATH = "D:\path\to\video.mp4"
$env:MODEL_PATH = "D:\path\to\best.pt"
python Solution.py
```

### Test the same flow as the frontend (demo script)

With the Flask backend running, you can run the exact same API flow the UI uses:

```powershell
# Terminal 1: start backend
.\venv\Scripts\Activate.ps1
python backend/run_flask.py

# Terminal 2: run demo (optionally with your video path)
node scripts/demo-frontend-run.js "D:\Ice-Block-Counting-Electron-App\2025091165659 PM.mp4"
```

The script: (1) checks backend debug, (2) POSTs run-for-date, (3) polls job progress until done, (4) fetches results. Use this to confirm the backend and model work before testing in the app.

### How to test in the app (frontend)

1. **Start the app:** `npm run dev` (starts Vite + Electron; Electron starts Flask with project root as cwd).
2. **Sign in** and open **Settings**.
3. **Check backend:** Click **Check backend**. You should see **Model exists: Yes** and the project root path.
4. **Run for date:** In **Run model for date**, enter your video path in **Test video (optional)** (e.g. `D:\Ice-Block-Counting-Electron-App\2025091165659 PM.mp4`), pick a date, click **Run for date**.
5. Watch the progress box; when it shows **Completed**, the view switches to **Dashboard** and the new result appears in the table.

If **Check backend** fails, start Flask manually from the project folder (`python backend/run_flask.py`) and try again.

## Data

- **SQLite DB:** `backend/data/ice_factory.db` (NVRs + run results).
- **Model:** Project root `best (1).pt` or `best_9_3_2026.pt`.

## Project layout

- `Solution.py` – original standalone counting script (unchanged).
- `backend/` – Flask app, NVR service, model runner, run-for-date job.
- `src/ui/` – React dashboard (Vite).
- `src/electron/` – Electron main and preload.
- `Duahua_IceFactory_BlockCounter/` – reference Dahua NVR viewer (PyQt5 + NetSDK).
