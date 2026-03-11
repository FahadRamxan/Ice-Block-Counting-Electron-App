import { contextBridge } from 'electron';

contextBridge.exposeInMainWorld('electron', {
  getBaseUrl: () => 'http://localhost:5000',
});
