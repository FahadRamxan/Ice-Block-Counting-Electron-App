"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const path_1 = __importDefault(require("path"));
const fs_1 = __importDefault(require("fs"));
const child_process_1 = require("child_process");
const net_1 = __importDefault(require("net"));
let mainWindow = null;
let flaskProcess = null;
let flaskLogTail = '';
const isDev = process.env.NODE_ENV === 'development';
const DEFAULT_FLASK_PORT = 5000;
let flaskPort = DEFAULT_FLASK_PORT;
/** Packaged apps put backend + venv in `resources/` (see electron-builder extraResources). */
function resourceRoot() {
    return electron_1.app.isPackaged ? process.resourcesPath : electron_1.app.getAppPath();
}
async function findFreePort(startPort, maxTries = 25) {
    for (let i = 0; i < maxTries; i++) {
        const port = startPort + i;
        // eslint-disable-next-line no-await-in-loop
        const ok = await new Promise((resolve) => {
            const server = net_1.default.createServer();
            server.once('error', () => resolve(false));
            server.once('listening', () => server.close(() => resolve(true)));
            server.listen(port, '127.0.0.1');
        });
        if (ok)
            return port;
    }
    return startPort;
}
function appendFlaskLog(chunk) {
    flaskLogTail += chunk;
    if (flaskLogTail.length > 16000) {
        flaskLogTail = flaskLogTail.slice(-16000);
    }
}
/** True if Windows venv was built against a Python install that is no longer on disk. */
function venvBaseInterpreterMissing(root) {
    if (process.platform !== 'win32')
        return false;
    const cfgPath = path_1.default.join(root, 'venv', 'pyvenv.cfg');
    if (!fs_1.default.existsSync(cfgPath))
        return false;
    try {
        const txt = fs_1.default.readFileSync(cfgPath, 'utf8');
        const m = txt.match(/^\s*executable\s*=\s*(.+)\s*$/im);
        if (!m)
            return false;
        const base = m[1].trim();
        return Boolean(base && !fs_1.default.existsSync(base));
    }
    catch {
        return false;
    }
}
/**
 * Packaged apps must use `python-runtime/` (embeddable Python + deps). A copied `venv/`
 * still points at the build PC path in `pyvenv.cfg` (e.g. C:\\Python313\\python.exe).
 */
function resolvePythonExe(root) {
    const embed = path_1.default.join(root, 'python-runtime', 'python.exe');
    if (electron_1.app.isPackaged) {
        return fs_1.default.existsSync(embed) ? embed : null;
    }
    const venvPython = process.platform === 'win32'
        ? path_1.default.join(root, 'venv', 'Scripts', 'python.exe')
        : path_1.default.join(root, 'venv', 'bin', 'python');
    if (fs_1.default.existsSync(venvPython) && !venvBaseInterpreterMissing(root)) {
        return venvPython;
    }
    if (venvBaseInterpreterMissing(root)) {
        appendFlaskLog('\n[venv] Base Python from pyvenv.cfg is missing. Use python-runtime for portable EXE: npm run setup:python-runtime\n');
    }
    if (fs_1.default.existsSync(embed))
        return embed;
    if (fs_1.default.existsSync(venvPython))
        return venvPython;
    return process.platform === 'win32' ? 'python' : 'python3';
}
/** Start Flask in the background; returns false if backend files are missing. */
function launchFlaskProcess(port) {
    flaskLogTail = '';
    const root = resourceRoot();
    const backendDir = path_1.default.join(root, 'backend');
    const projectRoot = root;
    const flaskScript = path_1.default.join(backendDir, 'run_flask.py');
    if (!fs_1.default.existsSync(flaskScript)) {
        return false;
    }
    const pythonExe = resolvePythonExe(root);
    if (!pythonExe) {
        appendFlaskLog('\nMissing python-runtime\\python.exe. On the build machine run: npm run setup:python-runtime\n');
        return false;
    }
    flaskProcess = (0, child_process_1.spawn)(pythonExe, [flaskScript, '--port', String(port)], {
        cwd: projectRoot,
        env: { ...process.env, FLASK_PORT: String(port), PYTHONPATH: backendDir },
        windowsHide: true,
    });
    flaskProcess.stdout?.on('data', (data) => appendFlaskLog(data.toString()));
    flaskProcess.stderr?.on('data', (data) => appendFlaskLog(data.toString()));
    flaskProcess.on('error', (err) => appendFlaskLog(`\n[spawn error] ${String(err)}\n`));
    return true;
}
async function waitForBackendHttp(port, timeoutMs) {
    const url = `http://127.0.0.1:${port}/api/status`;
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
        try {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), 2500);
            const res = await fetch(url, { signal: controller.signal });
            clearTimeout(timer);
            if (res.ok)
                return true;
        }
        catch {
            // still starting (imports can take a long time on first run)
        }
        await new Promise((r) => setTimeout(r, 400));
    }
    return false;
}
function createWindow() {
    mainWindow = new electron_1.BrowserWindow({
        title: `Ice Factory Block Counter v${electron_1.app.getVersion()}`,
        width: 1280,
        height: 800,
        webPreferences: {
            preload: path_1.default.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
            additionalArguments: [`--flask-port=${flaskPort}`],
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
    flaskPort = await findFreePort(DEFAULT_FLASK_PORT);
    const launched = launchFlaskProcess(flaskPort);
    if (!launched) {
        electron_1.dialog.showErrorBox('Ice Factory Block Counter', 'Could not find the Python backend (backend/run_flask.py). Re-install the application.');
        createWindow();
        return;
    }
    const waitMs = electron_1.app.isPackaged ? 240000 : 90000;
    const ok = await waitForBackendHttp(flaskPort, waitMs);
    if (!ok) {
        electron_1.dialog.showErrorBox('Backend did not start in time', [
            `The app could not reach http://127.0.0.1:${flaskPort}/api/status after waiting.`,
            '',
            'If Windows SmartScreen or antivirus blocked Python, allow this app.',
            '',
            '--- Python log (tail) ---',
            flaskLogTail.slice(-3500) || '(no output captured)',
        ].join('\n'));
    }
    createWindow();
});
electron_1.app.on('window-all-closed', () => {
    if (flaskProcess) {
        flaskProcess.kill();
        flaskProcess = null;
    }
    electron_1.app.quit();
});
