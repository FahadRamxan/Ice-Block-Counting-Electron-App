#!/usr/bin/env node
/**
 * Windows packaged builds expect a self-contained interpreter under ./python-runtime/
 * (venv copies still reference the original PC path in pyvenv.cfg — see README).
 */
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

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

const sitePackages = path.join(root, 'python-runtime', 'Lib', 'site-packages');
if (!fs.existsSync(sitePackages)) {
  console.error('Missing python-runtime\\Lib\\site-packages — re-run: npm run setup:python-runtime');
  process.exit(1);
}

try {
  execFileSync(
    exe,
    ['-s', '-c', 'import flask, flask_cors; import ultralytics'],
    {
      stdio: 'pipe',
      timeout: 180000,
      cwd: root,
      env: { ...process.env, PYTHONNOUSERSITE: '1' },
    },
  );
} catch (e) {
  console.error(
    [
      'python-runtime\\python.exe exists but cannot import Flask / Ultralytics.',
      'Your embed runtime is incomplete. Re-run:',
      '  npm run setup:python-runtime',
      '',
      e && e.stderr ? e.stderr.toString() : '',
      e && e.stdout ? e.stdout.toString() : '',
      e && e.message ? e.message : String(e),
    ].join('\n'),
  );
  process.exit(1);
}

console.log('OK: python-runtime has Flask + Ultralytics');
