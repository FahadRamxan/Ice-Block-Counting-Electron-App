# Ice Factory Block Counter

Desktop-oriented app for counting ice blocks from video using a **YOLO** model. Configure **NVRs** (factory recorders), browse **recordings by date** on camera **channels 1–15**, and **test the model** on a local video file. The UI is **React + Vite**; inference and APIs run in **Python (Flask)**. An **Electron** shell is optional.

---

## Prerequisites

- **Node.js** (LTS recommended) and **npm**
- **Python 3.10+** (3.11+ works well with Ultralytics)

---

## One-time setup

From the repository root (the folder that contains `package.json`):

**Windows (PowerShell)**

```powershell
cd <path-to-repo>

python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
deactivate

npm install
```

**macOS / Linux**

```bash
cd <path-to-repo>

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

npm install
```

### Model weights

Put a YOLO `.pt` file in the **project root** (next to `package.json`). The backend looks for these names in order:

1. `best_9_3_2026.pt`
2. `best (1).pt`

If neither exists, it still defaults to `best (1).pt` for error messages—place at least one of the files above so runs succeed.

---

## How to run

### Option A — Browser (good for everyday dev)

Use **two terminals**, both with cwd = project root.

**Terminal 1 — Flask API (port 5000)**

```powershell
.\venv\Scripts\Activate.ps1
python backend\run_flask.py
```

```bash
source venv/bin/activate
python backend/run_flask.py
```

**Terminal 2 — Vite dev server (port 3000)**

```bash
npm run dev:react
```

Open **http://localhost:3000**, sign in, then use **Home**, **NVRs**, **Recordings**, and **Test model**.

**Health check:** **http://localhost:5000/api/status** should return JSON.

### Option B — Electron desktop window

```powershell
$env:NODE_ENV = "development"
npm run dev
```

This compiles Electron TypeScript once, starts Vite, waits for **http://localhost:3000**, then opens Electron.

**Flask:** In development, Electron tries to start Flask automatically: it prefers `venv\Scripts\python.exe` (Windows) or `venv/bin/python` if present; otherwise it uses `python` / `python3` on your `PATH`. If the UI reports the backend as unreachable, run **Terminal 1** from Option A manually (and ensure nothing else is using port 5000).

---

## npm scripts

| Script | What it does |
|--------|----------------|
| `npm run dev` | `build:electron` → Vite + Electron (dev URL). |
| `npm run dev:react` | Vite only on port 3000. |
| `npm run dev:electron` | Waits for port 3000, then Electron (Flask not started by this script alone). |
| `npm run build` | Production Vite build + Electron `main` compile. |
| `npm run preview` | Serve the built Vite app (after `build:react`). |
| `npm run setup:python-runtime` | **Windows EXE only:** download embeddable Python + `pip install -r requirements.txt` into `python-runtime/`. Run once before `dist:win`. |
| `npm run dist:win` | Production build + **Windows** portable EXE + NSIS installer (see below). Requires `python-runtime/`. |
| `npm run dist` | Same as `dist:win` when run on Windows (uses `electron-builder` defaults for the host OS). |

---

## Build Windows installer / portable EXE

Packaging uses **[electron-builder](https://www.electron.build/)**. It bundles the compiled UI, Electron `main`, the **`backend/`** tree, a **self-contained `python-runtime/`** (embeddable Python + pip-installed deps), and any **`.pt` files in the project root** into `release/`.

**Why not ship `venv/` inside the EXE?** On Windows, a virtualenv records the original Python path in `venv/pyvenv.cfg` (for example `C:\Python313\python.exe`). On another PC that path does not exist, so Flask never starts. **`python-runtime/`** avoids that by using the official **embeddable** layout plus libraries installed next to it.

**Before you pack**

1. Complete **One-time setup** (`npm install`). A normal **`venv/`** is still fine for **browser / dev** (`python backend/run_flask.py`); the EXE does **not** bundle `venv/` anymore.
2. **Create `python-runtime/` once** (large download; includes PyTorch via `requirements.txt`):

   ```powershell
   npm run setup:python-runtime
   ```

3. Put your weights file(s) in the **repo root** so root-level `*.pt` files are copied into the app (see **Model weights** above).

**Build (PowerShell, from repo root)**

```powershell
$env:CSC_IDENTITY_AUTO_DISCOVERY = "false"
npm run dist:win
```

`CSC_IDENTITY_AUTO_DISCOVERY=false` skips Windows code-signing prompts when you do not have a certificate.

**Outputs** (under `release/`)

| Artifact | Description |
|----------|-------------|
| **Portable** | `Ice Factory Block Counter 1.0.0.exe` (or similar)—no installer; double-click to run. |
| **NSIS** | `Ice Factory Block Counter Setup 1.0.0.exe`—installer wizard. |
| **`win-unpacked/`** | Unpacked app folder (useful for testing without generating the portable/installer again). Run `Ice Factory Block Counter.exe` inside it. |

**Size:** The folder is large (Electron + embeddable Python + PyTorch). That is expected.

**Optional quick unpack only** (no portable/installer archives, faster iteration):

```powershell
npm run build
node scripts/assert-python-runtime.cjs
$env:CSC_IDENTITY_AUTO_DISCOVERY = "false"
npx electron-builder --win --dir
```

**Code signing:** For production releases, configure a Windows signing certificate and remove or omit `CSC_IDENTITY_AUTO_DISCOVERY`; see [electron-builder code signing](https://www.electron.build/code-signing).

---

## Dahua NVR recordings (optional)

To **load recordings** from a Dahua NVR on Windows you need the **Dahua NetSDK** wheel, for example:

```powershell
.\venv\Scripts\Activate.ps1
pip install ".\NetSDK-2.0.0.1-py3-none-win_amd64.whl"
```

Without NetSDK you can still use **Test model** with a local video path.

Reference code and notes live under **`Duahua_IceFactory_BlockCounter/`** — start with `QUICKSTART.md` there and `DahuaRecordingViewer.py`.

---

## Features (high level)

| Area | Description |
|------|-------------|
| **NVRs** | Add/remove NVRs (IP, port, user, password). Persisted in SQLite. |
| **Recordings** | NVR + date + channels **1–15** → load list (NetSDK on Windows). **Run model on selection** wires batch intent for NVR workflows. |
| **Test model** | Same idea as `Solution.py`: local video path, optional max frames for a quick test. |
| **Theme / language** | Light/dark; **English** and **Urdu** (header + login). |

Annotated outputs and CSVs go under **`backend/data/outputs/`** (gitignored—do not commit large videos).

---

## Stack

- **React 18 + Vite** — UI (dev: **3000**)
- **Flask** — REST API (default **5000**)
- **SQLite** — `backend/data/ice_factory.db`
- **Ultralytics / YOLO** — `backend/model_runner.py` and `Solution.py`
- **Electron** — optional shell in `src/electron/`

---

## Project layout

```
backend/              Flask app, model runner, SQLite, data/
src/ui/               React application
src/electron/         Electron main + preload (TypeScript → dist-electron/)
Solution.py           Standalone script (env-driven)
Duahua_IceFactory_BlockCounter/   Dahua viewer + NetSDK notes
```

---

## CLI: test without the web UI

With venv active and `MODEL_PATH` / `VIDEO_PATH` set as needed:

```powershell
.\venv\Scripts\Activate.ps1
$env:VIDEO_PATH = "C:\path\to\video.mp4"
python Solution.py
```

(`Solution.py` uses `MODEL_PATH` from the environment or falls back to a default path—set `MODEL_PATH` to your `.pt` if it is not in the default location.)

---

## Troubleshooting

| Issue | What to try |
|-------|-------------|
| Backend not reachable | Run `python backend/run_flask.py` from the project root with the venv active; check port **5000**. |
| Model not found | Put `best_9_3_2026.pt` or `best (1).pt` in the project root. |
| Zero blocks / wrong counts | Classes and training must match your scene; use a short clip and a low **max frames** first. |
| Git rejects a push (large file) | Do not commit `backend/data/outputs/` or huge `.avi` files—they should stay gitignored. |
| `Activate.ps1` blocked | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or activate via `venv\Scripts\activate.bat`. |
