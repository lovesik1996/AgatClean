/**
 * sync.js – mechanizm synchronizacji offline-first
 *
 * Logika:
 * 1. Jeśli brak internetu → wszystko idzie do SQLite (synced=0)
 * 2. Gdy internet wróci (lub co 60s) → wyślij lokalny stan na serwer,
 *    pobierz najnowsze dane i zaktualizuj SQLite.
 */

import { exportData, importData, getPendingCount, markAllSynced } from './db.js';
import { isOnline, fetchData, pushData, ApiError } from './api.js';

/* ─── Stan synchronizacji ─── */
const _state = {
  running:   false,
  lastSync:  null,       // Date | null
  lastError: null,       // string | null
  listeners: []
};

/** Wyniki statusu synchronizacji */
export const SyncStatus = Object.freeze({
  IDLE:       'idle',
  IN_PROGRESS:'in_progress',
  SUCCESS:    'success',
  OFFLINE:    'offline',
  ERROR:      'error'
});

let _currentStatus = SyncStatus.IDLE;

function _emit(status, detail = {}) {
  _currentStatus = status;
  _state.listeners.forEach(fn => fn(status, detail));
  document.dispatchEvent(new CustomEvent('sync-status', { detail: { status, ...detail } }));
}

export function onSyncStatus(fn) {
  _state.listeners.push(fn);
  return () => { _state.listeners = _state.listeners.filter(l => l !== fn); };
}

export function getSyncStatus() { return _currentStatus; }
export function getLastSync()   { return _state.lastSync; }
export function getLastError()  { return _state.lastError; }

/* ─── Główna funkcja synchronizacji ─── */
export async function syncNow() {
  if (_state.running) return { status: SyncStatus.IN_PROGRESS };

  const online = await isOnline();
  if (!online) {
    _emit(SyncStatus.OFFLINE);
    return { status: SyncStatus.OFFLINE };
  }

  _state.running = true;
  _emit(SyncStatus.IN_PROGRESS);

  try {
    /* 1. Eksportuj lokalne dane */
    const local = await exportData();

    /* 2. Wyślij na serwer */
    await pushData(local);

    /* 3. Pobierz aktualne dane z serwera */
    const server = await fetchData();

    /* 4. Zaimportuj do SQLite (nadpisuje lokalne) */
    await importData(server);

    /* 5. Oznacz jako zsynchronizowane */
    await markAllSynced();

    _state.lastSync  = new Date();
    _state.lastError = null;
    _emit(SyncStatus.SUCCESS, { timestamp: _state.lastSync });
    return { status: SyncStatus.SUCCESS, timestamp: _state.lastSync };
  } catch (err) {
    const msg = err instanceof ApiError
      ? (err.status === 401 ? 'Wymagane logowanie' : `Błąd serwera (${err.status})`)
      : (err.message || 'Nieznany błąd');

    _state.lastError = msg;
    _emit(SyncStatus.ERROR, { error: msg, needsLogin: err instanceof ApiError && err.status === 401 });
    console.warn('[Sync] Failed:', err);
    return { status: SyncStatus.ERROR, error: msg };
  } finally {
    _state.running = false;
  }
}

/* ─── Auto-synchronizacja ─── */
let _networkListener = null;
let _intervalId      = null;

export function startAutoSync(intervalMs = 60_000) {
  /* Nasłuchuj na zmiany sieci (Capacitor Network plugin) */
  const Cap = window.Capacitor;
  if (Cap?.isNativePlatform()) {
    const net = Cap.Plugins?.Network;
    if (net) {
      net.addListener('networkStatusChange', status => {
        if (status.connected) {
          console.log('[Sync] Network restored – initiating sync');
          syncNow();
        } else {
          _emit(SyncStatus.OFFLINE);
        }
      });
    }
  }

  /* Fallback: zdarzenia przeglądarki */
  window.addEventListener('online',  () => syncNow());
  window.addEventListener('offline', () => _emit(SyncStatus.OFFLINE));

  /* Sync co N sekund gdy aktywny */
  _intervalId = setInterval(syncNow, intervalMs);

  /* Pierwsza próba synchronizacji po starcie */
  setTimeout(syncNow, 2000);
}

export function stopAutoSync() {
  if (_intervalId)      clearInterval(_intervalId);
  if (_networkListener) _networkListener();
}

/* ─── Formatowanie czasu ostatniej synchronizacji ─── */
export function formatLastSync(date) {
  if (!date) return 'Nie synchronizowano';
  const diff = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diff < 60)   return 'Przed chwilą';
  if (diff < 3600) return `${Math.floor(diff / 60)} min temu`;
  return date.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });
}
