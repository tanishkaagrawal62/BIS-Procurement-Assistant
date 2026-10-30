const API_BASE = import.meta.env.VITE_API_BASE || '/api';
const TOKEN_KEY = 'bis-assist-session-token';

export function hasSession() {
  return Boolean(sessionStorage.getItem(TOKEN_KEY) || localStorage.getItem(TOKEN_KEY));
}

export function saveSession(token, remember = false) {
  clearSession();
  (remember ? localStorage : sessionStorage).setItem(TOKEN_KEY, token);
}

export function clearSession() {
  sessionStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(TOKEN_KEY);
}

export async function apiRequest(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = sessionStorage.getItem(TOKEN_KEY) || localStorage.getItem(TOKEN_KEY);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch {
    throw new Error('The BIS Assist API is not reachable. Start the backend server and try again.');
  }
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const data = await response.json();
      message = data.detail || message;
    } catch {
      // Keep the useful HTTP status when the server did not return JSON.
    }
    if (response.status === 401) clearSession();
    throw new Error(message);
  }
  if (response.status === 204) return null;
  const contentType = response.headers.get('content-type') || '';
  return contentType.includes('application/pdf') ? response.blob() : response.json();
}

export { TOKEN_KEY };
