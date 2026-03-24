/**
 * api.js – warstwa komunikacji z backendem Flask
 * https://agatclean.onrender.com
 */

export const API_BASE = 'https://agatclean.onrender.com';

/* ─── Sprawdzenie połączenia ─── */
export async function isOnline() {
  try {
    if (window.Capacitor?.isNativePlatform()) {
      const net = window.Capacitor.Plugins?.Network;
      if (net) {
        const status = await net.getStatus();
        return status.connected;
      }
    }
    return navigator.onLine;
  } catch {
    return navigator.onLine;
  }
}

/* ─── Bazowy fetch z obsługą błędów ─── */
async function _fetch(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    ...options,
    credentials: 'include',          // przesyłaj ciasteczka sesji Flask
    headers: {
      'Content-Type': 'application/json',
      'Accept':       'application/json',
      ...(options.headers || {})
    }
  });
  if (response.status === 401 || response.status === 403) {
    throw new ApiError(response.status, 'Unauthorized');
  }
  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new ApiError(response.status, body || response.statusText);
  }
  return response.json();
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

/* ─── Endpointy ─── */

/** Pobiera wszystkie dane użytkownika z serwera. */
export async function fetchData() {
  return _fetch('/api/data');
}

/**
 * Wysyła cały stan lokalny do serwera.
 * @param {Object} data – obiekt { rooms, settings, meta }
 */
export async function pushData(data) {
  return _fetch('/api/data', {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

/**
 * Próba logowania przez API.
 * Zwraca true jeśli serwer odpowie 200 na GET /api/data (sesja aktywna).
 */
export async function checkSession() {
  try {
    await _fetch('/api/data');
    return true;
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return false;
    if (err instanceof ApiError && err.status === 403) return false;
    throw err; // inny błąd (np. sieć)
  }
}

/**
 * Logowanie przez formularz HTML (Flask session-based).
 * Wysyła POST z application/x-www-form-urlencoded aby zmatchować Flask CSRF.
 */
export async function loginWithForm(email, password) {
  const body = new URLSearchParams({ email, password });
  const res = await fetch(`${API_BASE}/login`, {
    method:      'POST',
    credentials: 'include',
    headers:     { 'Content-Type': 'application/x-www-form-urlencoded' },
    body:        body.toString()
  });
  // Flask przekieruje po udanym logowaniu; sprawdzamy URL odpowiedzi
  if (!res.ok && res.status !== 302) {
    throw new ApiError(res.status, 'Login failed');
  }
  // Weryfikacja sesji
  return checkSession();
}

/** Wylogowanie */
export async function logout() {
  try {
    await fetch(`${API_BASE}/logout`, {
      method:      'POST',
      credentials: 'include'
    });
  } catch { /* ignoruj błędy sieciowe */ }
}
