const { contextBridge } = require('electron');

// The per-process local-service token is exposed only in renderer memory.
// It is never written to localStorage, SQLite, or the DOM.
contextBridge.exposeInMainWorld('mmfLocal', {
  localAuthToken: process.env.MMF_LOCAL_AUTH_TOKEN || null,
});
