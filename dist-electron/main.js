"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const path_1 = __importDefault(require("path"));
const fs_1 = __importDefault(require("fs"));
const child_process_1 = require("child_process");
let mainWindow = null;
let flaskProcess = null;
const isDev = process.env.NODE_ENV === 'development';
const FLASK_PORT = 5000;
function startFlaskBackend() {
    return new Promise((resolve) => {
        const backendDir = path_1.default.join(electron_1.app.getAppPath(), 'backend');
        const flaskScript = path_1.default.join(backendDir, 'run_flask.py');
        if (!fs_1.default.existsSync(flaskScript)) {
            resolve();
            return;
        }
        const appPath = electron_1.app.getAppPath();
        const venvPython = process.platform === 'win32'
            ? path_1.default.join(appPath, 'venv', 'Scripts', 'python.exe')
            : path_1.default.join(appPath, 'venv', 'bin', 'python');
        const pythonExe = fs_1.default.existsSync(venvPython) ? venvPython : (process.platform === 'win32' ? 'python' : 'python3');
        flaskProcess = (0, child_process_1.spawn)(pythonExe, [flaskScript, '--port', String(FLASK_PORT)], {
            cwd: backendDir,
            env: { ...process.env, FLASK_PORT: String(FLASK_PORT) },
        });
        flaskProcess.stdout?.on('data', (data) => {
            const msg = data.toString();
            if (msg.includes('Running on') || msg.includes('WARNING'))
                resolve();
        });
        flaskProcess.stderr?.on('data', (data) => {
            const msg = data.toString();
            if (msg.includes('Running on') || msg.includes('WARNING'))
                resolve();
        });
        setTimeout(resolve, 3500);
    });
}
function createWindow() {
    mainWindow = new electron_1.BrowserWindow({
        width: 1280,
        height: 800,
        webPreferences: {
            preload: path_1.default.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
        },
    });
    if (isDev) {
        mainWindow.loadURL('http://localhost:3000');
        mainWindow.webContents.openDevTools();
    }
    else {
        mainWindow.loadFile(path_1.default.join(__dirname, '../dist-react/index.html'));
    }
    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}
electron_1.app.whenReady().then(async () => {
    await startFlaskBackend();
    createWindow();
});
electron_1.app.on('window-all-closed', () => {
    if (flaskProcess) {
        flaskProcess.kill();
        flaskProcess = null;
    }
    electron_1.app.quit();
});
