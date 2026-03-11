import { app, BrowserWindow } from 'electron';
import path from 'path';
import fs from 'fs';
import { spawn, ChildProcess } from 'child_process';

let mainWindow: BrowserWindow | null = null;
let flaskProcess: ChildProcess | null = null;

const isDev = process.env.NODE_ENV === 'development';
const FLASK_PORT = 5000;

function startFlaskBackend(): Promise<void> {
  return new Promise((resolve) => {
    const appPath = app.getAppPath();
    const backendDir = path.join(appPath, 'backend');
    const projectRoot = path.join(backendDir, '..');
    const flaskScript = path.join(backendDir, 'run_flask.py');
    if (!fs.existsSync(flaskScript)) {
      resolve();
      return;
    }
    const venvPython = process.platform === 'win32'
      ? path.join(appPath, 'venv', 'Scripts', 'python.exe')
      : path.join(appPath, 'venv', 'bin', 'python');
    const pythonExe = fs.existsSync(venvPython) ? venvPython : (process.platform === 'win32' ? 'python' : 'python3');
    // Run Flask with cwd = project root so model/video paths (and any relative paths) match CLI
    flaskProcess = spawn(pythonExe, [flaskScript, '--port', String(FLASK_PORT)], {
      cwd: projectRoot,
      env: { ...process.env, FLASK_PORT: String(FLASK_PORT), PYTHONPATH: backendDir },
    });
    flaskProcess.stdout?.on('data', (data) => {
      const msg = data.toString();
      if (msg.includes('Running on') || msg.includes('WARNING')) resolve();
    });
    flaskProcess.stderr?.on('data', (data) => {
      const msg = data.toString();
      if (msg.includes('Running on') || msg.includes('WARNING')) resolve();
    });
    setTimeout(resolve, 3500);
  });
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:3000');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist-react/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(async () => {
  await startFlaskBackend();
  createWindow();
});

app.on('window-all-closed', () => {
  if (flaskProcess) {
    flaskProcess.kill();
    flaskProcess = null;
  }
  app.quit();
});
