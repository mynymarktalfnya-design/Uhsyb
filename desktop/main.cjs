const { app, BrowserWindow, dialog } = require('electron');
const { spawn } = require('node:child_process');
const { existsSync, readFileSync } = require('node:fs');
const path = require('node:path');
const http = require('node:http');

const APP_URL = process.env.MMF_DESKTOP_URL || 'http://127.0.0.1:5173/login';
const children = [];

function loadProductionEnv() {
  const file = process.env.MMF_ENV_FILE || (process.platform === 'win32'
    ? path.join(process.env.ProgramData || 'C:\\ProgramData', 'MMF', 'config', 'production.env')
    : path.join(require('node:os').homedir(), '.mmf', 'production.env'));
  if (!existsSync(file)) return;
  for (const line of readFileSync(file, 'utf8').split(/\r?\n/)) {
    const match = line.match(/^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*$/);
    if (match && !process.env[match[1]]) process.env[match[1]] = match[2];
  }
}

function resource(...parts) {
  return app.isPackaged ? path.join(process.resourcesPath, ...parts) : path.join(__dirname, '..', ...parts);
}

function startHidden(name, executable, args = [], extraEnv = {}) {
  const file = resource('runtime', executable);
  if (!existsSync(file)) return false;
  const child = spawn(file, args, { windowsHide: true, stdio: 'ignore', detached: false, env: { ...process.env, ...extraEnv } });
  child.on('error', (error) => console.error(`[${name}] ${error.message}`));
  children.push(child);
  return true;
}

function waitFor(url, timeoutMs = 30000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const check = () => {
      const request = http.get(url, (response) => {
        response.resume();
        if (response.statusCode && response.statusCode < 500) return resolve();
        retry();
      });
      request.on('error', retry);
      request.setTimeout(1000, () => { request.destroy(); retry(); });
    };
    const retry = () => {
      if (Date.now() - started > timeoutMs) return reject(new Error(`Timed out waiting for ${url}`));
      setTimeout(check, 250);
    };
    check();
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1440, height: 900, minWidth: 1024, minHeight: 700,
    title: 'ميني ماركت الفنية',
    autoHideMenuBar: true,
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  win.loadURL(APP_URL);
  return win;
}

async function boot() {
  loadProductionEnv();
  if (!app.requestSingleInstanceLock()) return app.quit();
  app.on('second-instance', () => { const win = BrowserWindow.getAllWindows()[0]; if (win) { if (win.isMinimized()) win.restore(); win.focus(); } });
  // Runtime binaries are produced by packaging/windows/build-runtime.ps1; no terminal is shown.
  startHidden('backend', 'mmf-backend.exe');
  startHidden('offline', 'mmf-local-service.exe');
  startHidden('frontend', 'mmf-production-host.exe', [], { MMF_STATIC_ROOT: resource('frontend') });
  try { await waitFor('http://127.0.0.1:5173/'); } catch (error) { dialog.showErrorBox('تعذر تشغيل ميني ماركت الفنية', error.message); return app.quit(); }
  createWindow();
}

app.whenReady().then(boot);
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('before-quit', () => children.forEach((child) => { try { child.kill(); } catch {} }));
