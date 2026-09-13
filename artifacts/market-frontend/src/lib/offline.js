/**
 * Offline-First helper for ميني ماركت الفنية.
 *
 * Provides:
 *  - Service Worker registration
 *  - Online/Offline status detection
 *  - Sync queue for mutations made while offline (IndexedDB-backed)
 *  - Auto-retry on reconnect
 */

const DB_NAME = 'mmf-offline-db';
const DB_VERSION = 2;
const QUEUE_STORE = 'sync_queue';
const RESPONSE_STORE = 'api_responses';

/** Open IndexedDB (lazy) */
function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(QUEUE_STORE)) {
        db.createObjectStore(QUEUE_STORE, { keyPath: 'id', autoIncrement: true });
      }
      if (!db.objectStoreNames.contains(RESPONSE_STORE)) {
        db.createObjectStore(RESPONSE_STORE, { keyPath: 'key' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function requestKey(url, params) {
  const query = params
    ? Object.entries(params)
      .filter(([, value]) => value !== undefined && value !== null)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
      .join('&')
    : '';
  return query ? `${url}${url.includes('?') ? '&' : '?'}${query}` : url;
}

function apiUrl(config) {
  const base = config?.baseURL || '';
  return requestKey(`${base}${config?.url || ''}`, config?.params);
}

/** Cache a successful API GET response for offline reads. */
export async function cacheApiResponse(config, data) {
  try {
    const db = await openDB();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(RESPONSE_STORE, 'readwrite');
      tx.objectStore(RESPONSE_STORE).put({
        key: apiUrl(config),
        data,
        ts: Date.now(),
      });
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
  } catch { /* offline cache is best effort */ }
}

/** Return the last successful API response for an offline GET. */
export async function getCachedApiResponse(config) {
  try {
    const db = await openDB();
    return await new Promise((resolve, reject) => {
      const req = db.transaction(RESPONSE_STORE, 'readonly')
        .objectStore(RESPONSE_STORE)
        .get(apiUrl(config));
      req.onsuccess = () => resolve(req.result?.data);
      req.onerror = () => reject(req.error);
    });
  } catch {
    return undefined;
  }
}

/** Add a queued mutation (for offline sync later) */
export async function enqueueRequest({ url, method, body, headers }) {
  try {
    const db = await openDB();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(QUEUE_STORE, 'readwrite');
      const store = tx.objectStore(QUEUE_STORE);
      const item = {
        url, method, body, headers,
        ts: Date.now(),
        retries: 0,
      };
      const req = store.add(item);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  } catch (e) {
    console.warn('enqueueRequest failed:', e);
  }
}

/** List queued mutations */
export async function listQueue() {
  try {
    const db = await openDB();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(QUEUE_STORE, 'readonly');
      const req = tx.objectStore(QUEUE_STORE).getAll();
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  } catch { return []; }
}

/** Drop a queue entry by id */
export async function removeFromQueue(id) {
  try {
    const db = await openDB();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(QUEUE_STORE, 'readwrite');
      const req = tx.objectStore(QUEUE_STORE).delete(id);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  } catch { /* ignore */ }
}

/** Replay queued mutations sequentially. Returns counts. */
export async function flushQueue() {
  const items = await listQueue();
  let success = 0, failed = 0;
  for (const item of items) {
    try {
      const res = await fetch(item.url, {
        method: item.method,
        headers: {
          'Content-Type': 'application/json',
          ...(item.headers || {}),
          ...(typeof localStorage !== 'undefined' && localStorage.getItem('mm_token')
            ? { Authorization: `Bearer ${localStorage.getItem('mm_token')}` }
            : {}),
        },
        body: item.body,
      });
      if (res.ok) {
        await removeFromQueue(item.id);
        success += 1;
      } else {
        failed += 1;
        // Drop on permanent failure (4xx)
        if (res.status >= 400 && res.status < 500) {
          await removeFromQueue(item.id);
        }
      }
    } catch {
      failed += 1;
      // Keep in queue for next round (network still down)
    }
  }
  return { success, failed };
}

/** Listen to online/offline events */
let onlineListeners = [];
export function onConnectivityChange(cb) {
  onlineListeners.push(cb);
  return () => { onlineListeners = onlineListeners.filter((c) => c !== cb); };
}

function _emit() {
  onlineListeners.forEach((cb) => {
    try { cb(navigator.onLine); } catch { /* ignore */ }
  });
}

if (typeof window !== 'undefined') {
  window.addEventListener('online', async () => {
    _emit();
    const { success, failed } = await flushQueue();
    if (success > 0) {
      console.info(`[offline] ✅ مزامنة ${success} عملية محلية. فشل: ${failed}`);
      // Show toast if available
      try {
        const evt = new CustomEvent('offline-sync', { detail: { success, failed } });
        window.dispatchEvent(evt);
      } catch { /* ignore */ }
    }
  });
  window.addEventListener('offline', () => _emit());
}

/** Register service worker (call once on app boot) */
export function registerServiceWorker() {
  if (typeof window === 'undefined' || !('serviceWorker' in navigator)) return;
  window.addEventListener('load', () => {
    const base = import.meta.env.BASE_URL || '/';
    navigator.serviceWorker.register(`${base}sw.js`, { scope: base })
      .then((reg) => console.info('[sw] registered:', reg.scope))
      .catch((err) => console.warn('[sw] registration failed:', err));
  });
}

export function isOnline() {
  return typeof navigator !== 'undefined' ? navigator.onLine : true;
}
