#!/usr/bin/env node
/**
 * Windows packaged builds expect a self-contained interpreter under ./python-runtime/
 * (venv copies still reference the original PC path in pyvenv.cfg — see README).
 */
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const exe = path.join(root, 'python-runtime', 'python.exe');

if (!fs.existsSync(exe)) {
  console.error(
    [
      'Missing python-runtime\\python.exe — packaged EXE cannot use a copied venv on other PCs.',
      '',
      'Run once (downloads embeddable Python + pip installs requirements; large download):',
      '  powershell -ExecutionPolicy Bypass -File scripts\\setup-embed-python.ps1',
      '',
      'Then run: npm run dist:win',
    ].join('\n'),
  );
  process.exit(1);
}

console.log('OK: python-runtime\\python.exe found');
