/**
 * API client. Adds the access token, refreshes it once when it expires, retries a read once while
 * the database wakes up, and turns every failure into an ApiError with a readable message.
 *
 * Trade-off: tokens live in localStorage so a refresh keeps you signed in. Access tokens last only
 * 15 minutes and refresh tokens rotate on every use, which limits the damage if one leaks.
 */
const BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '');
const STORAGE_KEY = 'throughline.session';

export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function readStoredSession() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || null;
  } catch {
    return null;
  }
}

let session = readStoredSession();
const listeners = new Set();

export const auth = {
  get: () => session,
  set(next) {
    session = next;
    try {
      if (next) localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      else localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* storage unavailable: the session still works until the tab closes */
    }
    listeners.forEach((listener) => listener(next));
  },
  subscribe(listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function send(method, path, body, token) {
  let response;
  try {
    response = await fetch(`${BASE_URL}/api/${path}`, {
      method,
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, 'NETWORK', "Can't reach the server. Check your connection and try again.");
  }
  if (response.status === 204) return null;
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!response.ok) {
    const error = data?.error || {};
    const unavailable = [502, 503, 504].includes(response.status);
    throw new ApiError(
      response.status,
      error.code || 'HTTP_ERROR',
      error.message || (unavailable
        ? 'The server is waking up after being idle. Try again in a few seconds.'
        : `The server returned an error (${response.status}).`),
      error.details,
    );
  }
  return data;
}

let refreshing = null;
function refreshSession() {
  if (!refreshing) {
    refreshing = send('POST', 'auth/refresh', { refresh_token: session?.refresh_token })
      .then((next) => {
        auth.set(next);
        return next;
      })
      .catch((error) => {
        auth.set(null);
        throw error;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

export async function request(method, path, body) {
  try {
    return await send(method, path, body, session?.access_token);
  } catch (error) {
    if (error.status === 401 && error.code === 'TOKEN_EXPIRED' && session?.refresh_token) {
      await refreshSession();
      return send(method, path, body, session?.access_token);
    }
    if (error.status === 401 && session && path !== 'auth/login') auth.set(null);
    // The serverless database pauses when idle and takes up to ~30 seconds to wake. A 503 means nothing
    // was saved, so any request can be retried. A 504 (gateway timeout) might have saved, so only reads retry.
    const retryable = (e) => e.status === 503 || (method === 'GET' && (e.status === 502 || e.status === 504));
    if (retryable(error)) {
      for (let attempt = 1; attempt <= 3; attempt += 1) {
        await wait(3000 * attempt);
        try {
          return await send(method, path, body, session?.access_token);
        } catch (retryError) {
          if (!retryable(retryError)) throw retryError;
        }
      }
    }
    throw error;
  }
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body ?? {}),
  put: (path, body) => request('PUT', path, body),
  delete: (path, body) => request('DELETE', path, body),
};