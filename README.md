# Ice Factory Block Counter

Count ice blocks from video using a YOLO model. Configure **NVRs** (factory recorders), list **recordings by date** on selected **camera channels (1–15)**, and **test the model** on any local video file.

---

## Quick run (easiest)

**1. One-time setup**

```powershell
cd D:\Ice-Block-Counting-Electron-App

python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

npm install
```

Put your weights in the **project root**, e.g. `best (1).pt` (or `best_9_3_2026.pt`).

**2. Every time you use the app — two terminals**

| Terminal | Command |
|----------|---------|
| **A** | `.\venv\Scripts\Activate.ps1` then `python backend\run_flask.py` |
| **B** | `npm run dev:react` |

Open **http://localhost:3000** in your browser → sign in → use **Home**, **NVRs**, **Recordings**, **Test model**.

Backend check: **http://localhost:5000/api/status** should return JSON.

---

## Optional: Electron window

```powershell
$env:NODE_ENV="development"
npm run dev
```

Builds Electron once, starts Vite, opens a desktop window. Flask may auto-start if `venv` + `backend\run_flask.py` are present; if the UI says the backend is unreachable, run **Terminal A** above.

---

## Optional: NVR recordings (Dahua)

To **load recordings** from a real NVR you need the **Dahua NetSDK** wheel for Windows:

```powershell
.\venv\Scripts\Activate.ps1
pip install "path\to\NetSDK-2.0.0.1-py3-none-win_amd64.whl"
```

Without NetSDK you can still use **Test model** with a local `.mp4` path.  
Reference viewer: `Duahua_IceFactory_BlockCounter\DahuaRecordingViewer.py` (see `QUICKSTART.md` there).

---

## What’s in the app

| Area | What it does |
|------|----------------|
| **NVRs** | Add/remove NVRs (IP, port, user, password). Stored in SQLite. |
| **Recordings** | Pick NVR + date + **channels 1–15** (multi-select) → **Load recordings** (needs NetSDK). **Run model on selection** registers intent for future NVR download + batch runs. |
| **Test model** | Run the same pipeline as `Solution.py` on a **local video path**; optional frame limit (e.g. 100) for a quick test. |
| **Theme / language** | Light & dark mode; **English** and **Urdu** (header + login). |

Outputs (annotated video, CSV) go under `backend\data\outputs\` — that folder is **gitignored** (do not commit large `.avi` files).

---

## Stack

- **React (Vite)** — UI on port **3000**
- **Flask** — API on port **5000**
- **SQLite** — `backend\data\ice_factory.db` (NVR list)
- **Python** — `backend\model_runner.py` (Ultralytics / YOLO)
- **Electron** (optional) — desktop shell

---

## Troubleshooting

| Problem | Try |
|--------|-----|
| Backend not reachable | Run `python backend\run_flask.py` from project root with venv active. |
| Model not found | Place `best (1).pt` in the **repo root** (same folder as `package.json`). |
| 0 blocks counted | Model/classes must match your scene (platform vs ice); try a short clip with **max frames** first. |
| Git push rejected (large file) | Don’t commit `backend\data\outputs\` or `.avi` — already in `.gitignore`. |

---

## Project layout

```
backend/           Flask API, model runner, SQLite
src/ui/            React app (App, Auth, i18n, themes)
src/electron/      Electron main (optional)
Solution.py        Original standalone script
Duahua_IceFactory_BlockCounter/   Dahua PyQt viewer + NetSDK notes
```

---

## CLI: test model without UI

Use the original script (model + video in env vars):

```powershell
.\venv\Scripts\Activate.ps1
$env:VIDEO_PATH = "D:\path\to\video.mp4"
python Solution.py
```

Or always use **Test model** in the browser once Flask is running.
