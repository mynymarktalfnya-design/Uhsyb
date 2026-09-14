/**
 * Offline-first transport.
 *
 * Preferred path: the persistent local Windows/Linux service on localhost.
 * Fallback path: IndexedDB when the local service is not installed.
 * Both paths keep operations until the server confirms a 2xx response.
 */

const DB_NAME = 'mmf-offline-db';
const DB_VERSION = 2;
const QUEUE_STORE = 'sync_queue';
const LOCAL_SERVICE_URL = process.env.REACT_APP_LOCAL_SERVICE_URL || 'http://127.0.0.1:8765';

function operationId() {
  return typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(QUEUE_STORE)) db.createObjectStore(QUEUE_STORE, { keyPath: 'id', autoIncrement: true });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function localServiceAvailable() {
  try {
    const res = await fetch(`${LOCAL_SERVICE_URL}/health`, { method: 'GET', signal: AbortSignal.timeout(800) });
    return res.ok;
  } catch { return false; }
}

/** Queue a mutation in the persistent local service, then fall back to IndexedDB. */
export async function enqueueRequest({ url, method, body, headers, operation_id }) {
  const item = { operation_id: operation_id || operationId(), url, method, body, headers: { ...(headers || {}) } };
  item.headers['X-Operation-ID'] = item.operation_id;
  try {
    if (await localServiceAvailable()) {
      const response = await fetch(`${LOCAL_SERVICE_URL}/queue`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(item),
      });
      if (response.ok) return { ...(await response.json()), local_service: true };
    }
  } catch (error) { console.warn('[offline] local service unavailable; using IndexedDB', error); }
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(QUEUE_STORE, 'readwrite');
    const req = tx.objectStore(QUEUE_STORE).add({ ...item, ts: Date.now(), state: 'pending', retries: 0 });
    req.onsuccess = () => resolve({ id: req.result, operation_id: item.operation_id, local_service: false });
    req.onerror = () => reject(req.error);
  });
}

export async function listQueue() {
  try {
    if (await localServiceAvailable()) {
      const response = await fetch(`${LOCAL_SERVICE_URL}/queue`, { signal: AbortSignal.timeout(1200) });
      if (response.ok) return (await response.json()).operations || [];
    }
  } catch {}
  try {
    const db = await openDB();
    return await new Promise((resolve, reject) => {
      const req = db.transaction(QUEUE_STORE, 'readonly').objectStore(QUEUE_STORE).getAll();
      req.onsuccess = () => resolve(req.result); req.onerror = () => reject(req.error);
    });
  } catch { return []; }
}

export async function removeFromQueue(id) {
  try {
    const db = await openDB();
    return await new Promise((resolve, reject) => {
      const req = db.transaction(QUEUE_STORE, 'readwrite').objectStore(QUEUE_STORE).delete(id);
      req.onsuccess = () => resolve(); req.onerror = () => reject(req.error);
    });
  } catch { return undefined; }
}

/** Replay browser fallback queue; local-service queues are synced by their own process. */
export async function flushQueue() {
  if (await localServiceAvailable()) {
    try {
      const response = await fetch(`${LOCAL_SERVICE_URL}/sync`, { method: 'POST', signal: AbortSignal.timeout(30000) });
      if (response.ok) {
        const rows = (await response.json()).operations || [];
        return { success: rows.filter(x => x.state === 'synced').length, failed: rows.filter(x => x.state === 'failed').length, source: 'local-service' };
      }
    } catch {}
  }
  const items = await (async () => {
    try { const db = await openDB(); return await new Promise((resolve, reject) => { const req = db.transaction(QUEUE_STORE, 'readonly').objectStore(QUEUE_STORE).getAll(); req.onsuccess = () => resolve(req.result); req.onerror = () => reject(req.error); }); } catch { return []; }
  })();
  let success = 0, failed = 0;
  for (const item of items) {
    try {
      const headers = { ...(item.headers || {}), 'Content-Type': 'application/json' };
      const token = typeof localStorage !== 'undefined' ? localStorage.getItem('mm_token') : null;
      if (token) headers.Authorization = `Bearer ${token}`;
      const res = await fetch(item.url, { method: item.method, headers, body: typeof item.body === 'string' ? item.body : JSON.stringify(item.body) });
      if (res.ok) { await removeFromQueue(item.id); success += 1; }
      else { failed += 1; /* retain 4xx too: manual retry/inspection must not lose data */ }
    } catch { failed += 1; }
  }
  return { success, failed, source: 'indexeddb' };
}

let onlineListeners = [];
export function onConnectivityChange(cb) { onlineListeners.push(cb); return () => { onlineListeners = onlineListeners.filter(x => x !== cb); }; }
function emit() { onlineListeners.forEach(cb => { try { cb(navigator.onLine); } catch {} }); }

if (typeof window !== 'undefined') {
  window.addEventListener('online', async () => { emit(); const result = await flushQueue(); if (result.success || result.failed) window.dispatchEvent(new CustomEvent('offline-sync', { detail: result })); });
  window.addEventListener('offline', emit);
}

export function registerServiceWorker() {
  if (typeof window === 'undefined' || !('serviceWorker' in navigator)) return;
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(err => console.warn('[sw] registration failed:', err)));
}
export function isOnline() { return typeof navigator !== 'undefined' ? navigator.onLine : true; }
export { LOCAL_SERVICE_URL };
