// Renderer-only session state. Access tokens are intentionally memory-only.
let accessToken = null;
let currentUser = null;

export function getAccessToken() {
  return accessToken;
}

export function setSession(token, user) {
  accessToken = token || null;
  currentUser = user || null;
}

export function getSessionUser() {
  return currentUser;
}

export function clearSession() {
  accessToken = null;
  currentUser = null;
}

export function hasSession() {
  return Boolean(accessToken);
}
