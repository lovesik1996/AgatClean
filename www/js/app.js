/**
 * app.js – główna logika aplikacji AgatClean
 * Zarządza stanem, routingiem ekranów, CRUD i UI.
 */

import {
  initDB, getRooms, saveRoom, deleteRoom,
  getTasksByRoom, getAllTasks, saveTask, deleteTask,
  markTaskDone, getSetting, setSetting,
  getPendingCount, exportData, newId
} from './db.js';

import {
  isOnline, checkSession, loginWithForm, logout as apiLogout, ApiError
} from './api.js';

import {
  syncNow, startAutoSync, onSyncStatus, getSyncStatus,
  getLastSync, formatLastSync, SyncStatus
} from './sync.js';

/* ═══════════════════════════════════════
   Stan aplikacji
═══════════════════════════════════════ */
const App = {
  rooms:        [],
  tasks:        [],      // wszystkie zadania (płaska lista)
  currentTab:   'home',
  expandedRooms: new Set(),
  quickCount:   2,
  quickTasks:   [],
  pendingCount: 0,
  online:       false,
  editRoomId:   null,    // null = nowy pokój
  editTaskId:   null,    // null = nowe zadanie
  editTaskRoom: null     // room_id dla nowego zadania
};

/* ═══════════════════════════════════════
   Stałe
═══════════════════════════════════════ */
const DAYS_PL  = ['Pon', 'Wt', 'Śr', 'Czw', 'Pt', 'Sob', 'Nd'];
const COLORS   = ['#e8f0fe','#fce8e6','#e6f4ea','#fef7e0','#f3e8fd','#e8f5e9','#fff8e1'];

const $ = id => document.getElementById(id);

/* ═══════════════════════════════════════
   Inicjalizacja
═══════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', async () => {
  await initDB();

  // Sprawdź czy mamy danych offline
  const rooms = await getRooms();
  App.rooms = rooms;
  App.tasks = await getAllTasks();
  App.quickCount = parseInt(await getSetting('quick_count', '2'));

  // Auto-sync (po starcie próbuje synchronizować)
  onSyncStatus(handleSyncStatus);
  startAutoSync(60_000);

  // Monitor sieci
  setInterval(async () => {
    const prev = App.online;
    App.online = await isOnline();
    if (prev !== App.online) updateOnlineBadge();
  }, 5000);
  App.online = await isOnline();

  // Reset done_today o północy
  scheduleMidnightReset();

  // Ukryj splash i pokaż app
  hideSplash();
  showTab('home');
});

/* ─── Ukrywanie splash ─── */
function hideSplash() {
  const splash = $('splash');
  if (splash) splash.remove();
  const shell = $('app-shell');
  if (shell) shell.classList.remove('hidden');
}

/* ─── Routing tabów ─── */
function showTab(tab) {
  App.currentTab = tab;

  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  const screen = $(`screen-${tab}`);
  if (screen) screen.classList.add('active');

  const navItem = document.querySelector(`.nav-item[data-tab="${tab}"]`);
  if (navItem) navItem.classList.add('active');

  if (tab === 'home')     renderHome();
  if (tab === 'rooms')    renderRooms();
  if (tab === 'quick')    renderQuick();
  if (tab === 'settings') renderSettings();
}

/* ─── Globalny listener nawigacji ─── */
window._nav = tab => showTab(tab);

/* ═══════════════════════════════════════
   Odświeżanie danych
═══════════════════════════════════════ */
async function refreshData() {
  App.rooms = await getRooms();
  App.tasks = await getAllTasks();
  App.pendingCount = await getPendingCount();
  updateOnlineBadge();
  renderCurrentTab();
}

function renderCurrentTab() {
  if (App.currentTab === 'home')     renderHome();
  if (App.currentTab === 'rooms')    renderRooms();
  if (App.currentTab === 'quick')    renderQuick();
  if (App.currentTab === 'settings') renderSettings();
}

/* ═══════════════════════════════════════
   Sync status handler
═══════════════════════════════════════ */
function handleSyncStatus(status, detail) {
  const dot = $('sync-dot');
  if (!dot) return;

  dot.classList.remove('offline', 'syncing');
  if (status === SyncStatus.IN_PROGRESS) dot.classList.add('syncing');
  if (status === SyncStatus.OFFLINE      || !App.online) dot.classList.add('offline');

  if (status === SyncStatus.SUCCESS) {
    showToast('Dane zsynchronizowane ✓', 'success');
    refreshData();
  }
  if (status === SyncStatus.ERROR && detail?.needsLogin) {
    showToast('Wymagane logowanie na serwerze', 'error');
  }
  renderSettings();  // odśwież info sync w ustawieniach
}

function updateOnlineBadge() {
  const dot = $('sync-dot');
  if (!dot) return;
  if (App.online) {
    dot.classList.remove('offline');
  } else {
    dot.classList.add('offline');
    dot.classList.remove('syncing');
  }

  const offBanner = $('offline-banner');
  if (offBanner) {
    offBanner.classList.toggle('show', !App.online);
  }

  // Badge oczekujących zmian
  const badge = $('nav-badge-home');
  if (badge) {
    badge.textContent = App.pendingCount > 0 ? App.pendingCount : '';
    badge.classList.toggle('show', App.pendingCount > 0);
  }
}

/* ═══════════════════════════════════════
   Logika dat / zadań
═══════════════════════════════════════ */
function todayWeekday() {
  // Python weekday: 0=Mon ... 6=Sun
  return (new Date().getDay() + 6) % 7;
}

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function isDueToday(task) {
  if (task.done_today) return false;  // już zrobione dziś
  const wd = Array.isArray(task.week_days)
    ? task.week_days
    : JSON.parse(task.week_days || '[]');

  if (task.freq_type === 'weekly') {
    return wd.includes(todayWeekday());
  }
  if (task.freq_type === 'periodic') {
    if (!task.last_done) return true;
    const diff = Math.floor((Date.now() - new Date(task.last_done).getTime()) / 86400000);
    const days = task.freq_unit === 'weeks' ? task.freq_value * 7 : task.freq_value;
    return diff >= days;
  }
  return false;
}

function isOverdue(task) {
  if (task.done_today) return false;
  if (task.last_done === todayStr()) return false;  // zrobione dziś

  const wd = Array.isArray(task.week_days)
    ? task.week_days
    : JSON.parse(task.week_days || '[]');
  const today = todayWeekday();

  if (task.freq_type === 'weekly') {
    // Zaległe = był planowany w poprzednim tygodniu lub wcześniej dziś i nie zrobiony
    if (!task.last_done) {
      return wd.some(d => d < today);
    }
    const last = new Date(task.last_done);
    const daysSinceDone = Math.floor((Date.now() - last.getTime()) / 86400000);
    return wd.some(d => d <= today) && daysSinceDone >= 7;
  }
  if (task.freq_type === 'periodic') {
    if (!task.last_done) return false;
    const diff  = Math.floor((Date.now() - new Date(task.last_done).getTime()) / 86400000);
    const days  = task.freq_unit === 'weeks' ? task.freq_value * 7 : task.freq_value;
    return diff > days * 1.5;
  }
  return false;
}

function freqLabel(task) {
  const wd = Array.isArray(task.week_days)
    ? task.week_days
    : JSON.parse(task.week_days || '[]');
  if (task.freq_type === 'weekly') {
    if (wd.length === 0) return 'Bez dnia';
    return wd.map(d => DAYS_PL[d]).join(', ');
  }
  return `Co ${task.freq_value} ${task.freq_unit === 'weeks' ? 'tydz.' : 'dni'}`;
}

/* ═══════════════════════════════════════
   EKRAN: HOME
═══════════════════════════════════════ */
function renderHome() {
  const today = new Date();
  const dateEl = $('home-date');
  if (dateEl) {
    dateEl.textContent = today.toLocaleDateString('pl-PL', {
      weekday: 'long', day: 'numeric', month: 'long'
    });
  }

  const dueTasks  = App.tasks.filter(isDueToday);
  const overdueTasks = App.tasks.filter(isOverdue);
  const doneTasks = App.tasks.filter(t => t.last_done === todayStr() || t.done_today);

  // Statystyki
  $('stat-total')   && ($('stat-total').textContent   = App.tasks.length);
  $('stat-done')    && ($('stat-done').textContent    = doneTasks.length);
  $('stat-overdue') && ($('stat-overdue').textContent = overdueTasks.length);

  // Lista zadań na dziś
  renderTaskList('home-tasks-list', dueTasks, true);

  // Zaległe
  renderTaskList('home-overdue-list', overdueTasks, false);

  const overdueSection = $('home-overdue-section');
  if (overdueSection) {
    overdueSection.style.display = overdueTasks.length > 0 ? '' : 'none';
  }
}

function renderTaskList(containerId, tasks, showRoomName) {
  const el = $(containerId);
  if (!el) return;

  if (tasks.length === 0) {
    el.innerHTML = `
      <div class="empty-state" style="padding:1.5rem">
        <svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
        <p>Wszystko gotowe!</p>
      </div>`;
    return;
  }

  el.innerHTML = tasks.map(task => {
    const room = App.rooms.find(r => r.id === task.room_id);
    const done = task.done_today || task.last_done === todayStr();
    const cls  = done ? 'done' : (isOverdue(task) ? 'overdue' : '');
    return `
      <div class="task-item ${cls}" onclick="window._toggleTask('${task.id}', ${!done})">
        <div class="task-check"></div>
        <div class="task-info">
          <div class="task-name">${esc(task.name)}</div>
          ${showRoomName && room ? `<div class="task-freq">${esc(room.name)}</div>` : ''}
          <div class="task-freq">${freqLabel(task)}</div>
        </div>
      </div>`;
  }).join('');
}

/* ═══════════════════════════════════════
   EKRAN: ROOMS
═══════════════════════════════════════ */
function renderRooms() {
  const el = $('rooms-list');
  if (!el) return;

  if (App.rooms.length === 0) {
    el.innerHTML = `
      <div class="empty-state">
        <svg viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>
        <h3>Brak pokoi</h3>
        <p>Dodaj pierwszy pokój, aby zacząć planować sprzątanie.</p>
      </div>`;
    return;
  }

  el.innerHTML = App.rooms.map(room => {
    const roomTasks = App.tasks.filter(t => t.room_id === room.id);
    const done  = roomTasks.filter(t => t.done_today || t.last_done === todayStr()).length;
    const exp   = App.expandedRooms.has(room.id);
    const tasksHtml = roomTasks.map(task => {
      const isDone = task.done_today || task.last_done === todayStr();
      const over   = isOverdue(task);
      return `
        <div class="task-item ${isDone ? 'done' : (over ? 'overdue' : '')}"
             onclick="window._toggleTask('${task.id}', ${!isDone})">
          <div class="task-check"></div>
          <div class="task-info">
            <div class="task-name">${esc(task.name)}</div>
            <div class="task-freq">${freqLabel(task)}${over ? ' · <span class="text-danger">Zaległe</span>' : ''}</div>
          </div>
          <div class="task-actions">
            <button class="task-action-btn" title="Edytuj"
                    onclick="event.stopPropagation();window._editTask('${task.id}')">
              ${iconEdit()}
            </button>
            <button class="task-action-btn delete" title="Usuń"
                    onclick="event.stopPropagation();window._deleteTask('${task.id}')">
              ${iconTrash()}
            </button>
          </div>
        </div>`;
    }).join('');

    return `
      <div class="card ${exp ? 'expanded' : ''}" id="room-${room.id}">
        <div class="card-header" onclick="window._toggleRoom('${room.id}')">
          <div class="room-color-dot" style="background:${room.color}"></div>
          <div style="flex:1">
            <div class="card-title">${esc(room.name)}</div>
            <div class="card-subtitle">${roomTasks.length} zadań · ${done} zrobione</div>
          </div>
          <svg class="card-chevron" viewBox="0 0 24 24">
            <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"/>
          </svg>
        </div>
        <div class="card-body">
          ${tasksHtml}
          <div class="card-divider"></div>
          <div class="add-task-row" onclick="window._openAddTask('${room.id}')">
            ${iconAdd()} Dodaj zadanie
          </div>
          <div class="room-action-row">
            <button class="room-action-btn" onclick="window._editRoom('${room.id}')">
              ${iconEdit()} Edytuj pokój
            </button>
            <button class="room-action-btn danger" onclick="window._deleteRoom('${room.id}')">
              ${iconTrash()} Usuń pokój
            </button>
          </div>
        </div>
      </div>`;
  }).join('');
}

/* ═══════════════════════════════════════
   EKRAN: QUICK
═══════════════════════════════════════ */
function getRandomTasks(count) {
  const pool = App.tasks.filter(t => !t.done_today && t.last_done !== todayStr());
  const shuffled = [...pool].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, count);
}

function renderQuick() {
  if (App.quickTasks.length === 0) {
    App.quickTasks = getRandomTasks(App.quickCount);
  }

  $('quick-count-num') && ($('quick-count-num').textContent = App.quickCount);

  const el = $('quick-tasks-list');
  if (!el) return;

  if (App.quickTasks.length === 0) {
    el.innerHTML = `
      <div class="empty-state">
        <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
        <h3>Brak zadań</h3>
        <p>Wszystko zrobione! Świetna robota 🎉</p>
      </div>`;
    return;
  }

  el.innerHTML = App.quickTasks.map(task => {
    const room = App.rooms.find(r => r.id === task.room_id);
    const done = task.done_today || task.last_done === todayStr();
    return `
      <div class="quick-task-item ${done ? 'done' : ''}"
           onclick="window._toggleTask('${task.id}', ${!done}, true)">
        <div class="task-check"></div>
        <div class="task-info">
          <div class="task-name">${esc(task.name)}</div>
          <div class="quick-task-room">${room ? esc(room.name) : ''} · ${freqLabel(task)}</div>
        </div>
      </div>`;
  }).join('');
}

/* ═══════════════════════════════════════
   EKRAN: SETTINGS
═══════════════════════════════════════ */
async function renderSettings() {
  const status  = getSyncStatus();
  const lastSyn = getLastSync();
  const pending = App.pendingCount;

  const syncEl = $('settings-sync-value');
  if (syncEl) {
    if (status === SyncStatus.IN_PROGRESS) {
      syncEl.textContent = 'Synchronizacja...';
    } else if (!App.online) {
      syncEl.textContent = 'Offline – brak internetu';
    } else {
      syncEl.textContent = formatLastSync(lastSyn);
    }
  }

  const pendEl = $('settings-pending-value');
  if (pendEl) pendEl.textContent = pending > 0 ? `${pending} zmian oczekuje` : 'Wszystko zsynchronizowane';

  const qc = $('settings-quick-count');
  if (qc) qc.textContent = App.quickCount;
}

/* ═══════════════════════════════════════
   Akcje na zadaniach
═══════════════════════════════════════ */
window._toggleTask = async (taskId, done, isQuick = false) => {
  await markTaskDone(taskId, done);

  // Aktualizuj w pamięci
  const t = App.tasks.find(x => x.id === taskId);
  if (t) {
    t.done_today = done;
    t.last_done  = done ? todayStr() : t.last_done;
  }

  // Aktualizacja quick tasks
  if (isQuick) {
    const qt = App.quickTasks.find(x => x.id === taskId);
    if (qt) { qt.done_today = done; }
    renderQuick();
    renderHome();
    return;
  }

  renderCurrentTab();
  if (App.currentTab !== 'home') renderHome();
};

window._toggleRoom = (roomId) => {
  if (App.expandedRooms.has(roomId)) {
    App.expandedRooms.delete(roomId);
  } else {
    App.expandedRooms.add(roomId);
  }
  renderRooms();
};

/* ═══════════════════════════════════════
   Modalne – Pokój
═══════════════════════════════════════ */
window._openAddRoom = () => {
  App.editRoomId = null;
  showRoomModal(null);
};

window._editRoom = (roomId) => {
  App.editRoomId = roomId;
  const room = App.rooms.find(r => r.id === roomId);
  showRoomModal(room);
};

window._deleteRoom = async (roomId) => {
  if (!confirm('Usunąć pokój i wszystkie jego zadania?')) return;
  await deleteRoom(roomId);
  await refreshData();
  showToast('Pokój usunięty');
};

function showRoomModal(room) {
  const title = room ? 'Edytuj pokój' : 'Nowy pokój';
  const name  = room?.name || '';
  const color = room?.color || COLORS[0];

  const colorsHtml = COLORS.map(c => `
    <div class="color-dot-picker ${c === color ? 'selected' : ''}"
         style="background:${c}"
         onclick="window._pickColor('${c}', this)">
    </div>`).join('');

  setModalContent(`
    <div class="modal-drag"></div>
    <div class="modal-header">
      <span class="modal-title">${title}</span>
      <button class="modal-close" onclick="closeModal()">${iconClose()}</button>
    </div>
    <div class="modal-body">
      <div class="form-group">
        <label>Nazwa pokoju</label>
        <input id="room-name-input" class="form-control" type="text"
               placeholder="np. Kuchnia" value="${esc(name)}" autofocus>
      </div>
      <div class="form-group">
        <label>Kolor</label>
        <div class="color-picker" id="color-picker">${colorsHtml}</div>
        <input type="hidden" id="room-color-input" value="${color}">
      </div>
    </div>
    <div class="modal-actions">
      <button class="btn btn-secondary" onclick="closeModal()">Anuluj</button>
      <button class="btn btn-primary" onclick="window._saveRoom()">Zapisz</button>
    </div>
  `);
  openModal();
}

window._pickColor = (color, el) => {
  document.querySelectorAll('#color-picker .color-dot-picker').forEach(d => d.classList.remove('selected'));
  el.classList.add('selected');
  $('room-color-input').value = color;
};

window._saveRoom = async () => {
  const name  = $('room-name-input')?.value.trim();
  const color = $('room-color-input')?.value || COLORS[0];
  if (!name) { $('room-name-input').classList.add('error'); return; }

  const existing = App.editRoomId ? App.rooms.find(r => r.id === App.editRoomId) : null;
  await saveRoom({
    id:       existing?.id   || newId(),
    name,
    color,
    position: existing?.position ?? App.rooms.length
  });
  closeModal();
  await refreshData();
  showToast(App.editRoomId ? 'Pokój zaktualizowany' : 'Pokój dodany', 'success');
  if (App.editRoomId) App.expandedRooms.add(App.editRoomId);
};

/* ═══════════════════════════════════════
   Modalne – Zadanie
═══════════════════════════════════════ */
window._openAddTask = (roomId) => {
  App.editTaskId   = null;
  App.editTaskRoom = roomId;
  showTaskModal(null, roomId);
};

window._editTask = (taskId) => {
  App.editTaskId = taskId;
  const task = App.tasks.find(t => t.id === taskId);
  showTaskModal(task, task?.room_id);
};

window._deleteTask = async (taskId) => {
  if (!confirm('Usunąć to zadanie?')) return;
  await deleteTask(taskId);
  await refreshData();
  showToast('Zadanie usunięte');
};

function showTaskModal(task, roomId) {
  const title    = task ? 'Edytuj zadanie' : 'Nowe zadanie';
  const name     = task?.name || '';
  const freqType = task?.freq_type || 'weekly';
  const wd       = Array.isArray(task?.week_days) ? task.week_days : JSON.parse(task?.week_days || '[]');
  const fv       = task?.freq_value || 1;
  const fu       = task?.freq_unit  || 'days';

  const daysHtml = DAYS_PL.map((d, i) => `
    <label class="day-toggle">
      <input type="checkbox" name="wd" value="${i}" ${wd.includes(i) ? 'checked' : ''}>
      <span class="day-label">${d}</span>
    </label>`).join('');

  setModalContent(`
    <div class="modal-drag"></div>
    <div class="modal-header">
      <span class="modal-title">${title}</span>
      <button class="modal-close" onclick="closeModal()">${iconClose()}</button>
    </div>
    <div class="modal-body">
      <div class="form-group">
        <label>Nazwa zadania</label>
        <input id="task-name-input" class="form-control" type="text"
               placeholder="np. Mycie podłogi" value="${esc(name)}" autofocus>
      </div>
      <div class="form-group">
        <label>Częstotliwość</label>
        <select id="task-freq-type" class="form-control" onchange="window._onFreqChange()">
          <option value="weekly"   ${freqType==='weekly'   ? 'selected':''}>Tygodniowo (wybrane dni)</option>
          <option value="periodic" ${freqType==='periodic' ? 'selected':''}>Okresowo (co N dni)</option>
        </select>
      </div>
      <div id="freq-weekly-group" class="form-group" ${freqType!=='weekly' ? 'style="display:none"' : ''}>
        <label>Dni tygodnia</label>
        <div class="checkbox-grid">${daysHtml}</div>
      </div>
      <div id="freq-periodic-group" class="form-group" ${freqType!=='periodic' ? 'style="display:none"' : ''}>
        <label>Powtarzaj co</label>
        <div style="display:flex;gap:.75rem;align-items:center">
          <input id="task-freq-value" class="form-control" type="number"
                 min="1" max="365" value="${fv}" style="width:80px">
          <select id="task-freq-unit" class="form-control">
            <option value="days"  ${fu==='days'  ? 'selected':''}>dni</option>
            <option value="weeks" ${fu==='weeks' ? 'selected':''}>tydz.</option>
          </select>
        </div>
      </div>
    </div>
    <div class="modal-actions">
      <button class="btn btn-secondary" onclick="closeModal()">Anuluj</button>
      <button class="btn btn-primary" onclick="window._saveTask('${roomId}')">Zapisz</button>
    </div>
  `);
  openModal();
}

window._onFreqChange = () => {
  const t = $('task-freq-type')?.value;
  $('freq-weekly-group')  && ($('freq-weekly-group').style.display   = t === 'weekly'   ? '' : 'none');
  $('freq-periodic-group') && ($('freq-periodic-group').style.display = t === 'periodic' ? '' : 'none');
};

window._saveTask = async (roomId) => {
  const name = $('task-name-input')?.value.trim();
  if (!name) { $('task-name-input').classList.add('error'); return; }

  const freqType = $('task-freq-type').value;
  const wd = freqType === 'weekly'
    ? [...document.querySelectorAll('input[name="wd"]:checked')].map(el => parseInt(el.value))
    : [];
  const fv  = freqType === 'periodic' ? parseInt($('task-freq-value').value) || 1 : 1;
  const fu  = freqType === 'periodic' ? $('task-freq-unit').value : 'days';

  const existing = App.editTaskId ? App.tasks.find(t => t.id === App.editTaskId) : null;

  await saveTask({
    id:         existing?.id || newId(),
    room_id:    roomId,
    name,
    freq_type:  freqType,
    week_days:  wd,
    freq_value: fv,
    freq_unit:  fu,
    last_done:  existing?.last_done  || null,
    done_today: existing?.done_today || false
  });

  closeModal();
  App.expandedRooms.add(roomId);
  await refreshData();
  showToast(App.editTaskId ? 'Zadanie zaktualizowane' : 'Zadanie dodane', 'success');
};

/* ═══════════════════════════════════════
   Quick controls
═══════════════════════════════════════ */
window._quickRefresh = () => {
  App.quickTasks = getRandomTasks(App.quickCount);
  renderQuick();
};

window._quickCountChange = async (delta) => {
  App.quickCount = Math.max(1, Math.min(20, App.quickCount + delta));
  await setSetting('quick_count', App.quickCount);
  App.quickTasks = getRandomTasks(App.quickCount);
  renderQuick();
};

/* ═══════════════════════════════════════
   Settings akcje
═══════════════════════════════════════ */
window._manualSync = async () => {
  const btn = $('btn-sync');
  if (btn) btn.disabled = true;
  const result = await syncNow();
  if (btn) btn.disabled = false;
  if (result.status === SyncStatus.OFFLINE) showToast('Brak internetu – zmiany zapisane lokalnie', 'error');
  if (result.status === SyncStatus.ERROR)   showToast(result.error || 'Błąd synchronizacji', 'error');
};

window._logout = async () => {
  if (!confirm('Wylogować się?')) return;
  await apiLogout();
  showToast('Wylogowano');
};

/* ═══════════════════════════════════════
   Modal helper
═══════════════════════════════════════ */
function setModalContent(html) {
  const sheet = document.querySelector('#modal-overlay .modal-sheet');
  if (sheet) sheet.innerHTML = html;
}

function openModal() {
  const overlay = $('modal-overlay');
  if (overlay) {
    overlay.classList.remove('hidden');
    requestAnimationFrame(() => overlay.classList.add('open'));
  }
}

window.closeModal = () => {
  const overlay = $('modal-overlay');
  if (overlay) {
    overlay.classList.remove('open');
    setTimeout(() => overlay.classList.add('hidden'), 300);
  }
};

/* Zamknij modal kliknięciem w tło */
document.addEventListener('click', e => {
  if (e.target.id === 'modal-overlay') window.closeModal();
});

/* ═══════════════════════════════════════
   Toast
═══════════════════════════════════════ */
let _toastTimer = null;
function showToast(msg, type = '') {
  const t = $('toast');
  if (!t) return;
  t.textContent = msg;
  t.className   = `toast ${type}`;
  requestAnimationFrame(() => t.classList.add('show'));
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => t.classList.remove('show'), 2800);
}

/* ═══════════════════════════════════════
   Midnight reset
═══════════════════════════════════════ */
function scheduleMidnightReset() {
  const now  = new Date();
  const midnight = new Date(now);
  midnight.setHours(24, 0, 5, 0);
  const ms = midnight.getTime() - now.getTime();
  setTimeout(async () => {
    const { resetDoneToday } = await import('./db.js');
    await resetDoneToday();
    await refreshData();
    scheduleMidnightReset();
  }, ms);
}

/* ═══════════════════════════════════════
   SVG ikony
═══════════════════════════════════════ */
function iconEdit()  { return `<svg viewBox="0 0 24 24"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>`; }
function iconTrash() { return `<svg viewBox="0 0 24 24"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>`; }
function iconAdd()   { return `<svg viewBox="0 0 24 24"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>`; }
function iconClose() { return `<svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>`; }

/* Escape HTML */
function esc(str) {
  return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
