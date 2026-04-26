import { contextBridge } from 'electron';

function getFlaskPortFromArgs(): number | null {
  const arg = process.argv.find((a) => a.startsWith('--flask-port='));
  if (!arg) return null;
  const raw = arg.split('=', 2)[1];
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : null;
}

contextBridge.exposeInMainWorld('electron', {
  getBaseUrl: () => {
    const port = getFlaskPortFromArgs() ?? 5000;
    return `http://127.0.0.1:${port}`;
  },
});
