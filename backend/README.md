# Backend (stub)

The backend has been **stripped to a minimal stub**. All previous functionality (NVR DB, recordings/NVR service, run job, model runner, path utils) has been removed.

## Current state

- **Flask app** in `app/` with CORS.
- **Stub routes** only — same URLs as before, but they return empty/safe responses so the frontend still loads:
  - `GET/POST/DELETE /api/nvrs` → empty list, stub add, 204 delete
  - `GET /api/recordings/by-date` → empty recordings
  - `GET /api/runs/results`, `GET /api/runs/results/summary` → `[]`
  - `POST /api/runs/run-for-date` → `{ status: 'started' }`
  - `GET /api/runs/job-progress` → `{ running: false, progress: [], current: null, error: null }`
  - `GET /api/runs/debug` → stub object

## Run

From project root:

```powershell
.\venv\Scripts\Activate.ps1
python backend/run_flask.py
```

The frontend is unchanged and will work against these stubs. Backend will be **redesigned step by step** as you specify.
