/**
 * db.js – warstwa bazy danych AgatClean
 * Używa SQLite na urządzeniach natywnych (via @capacitor-community/sqlite)
 * i localStorage jako fallback w przeglądarce / trybie dev.
 */

const DB_NAME = 'agatclean';
const DB_VERSION = 1;

let _plugin = null;   // Capacitor SQLite plugin
let _native = false;  // czy działamy natywnie

/* ─── DDL – schemat bazy ─── */
const SCHEMA_SQL = `
  CREATE TABLE IF NOT EXISTS rooms (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    color       TEXT NOT NULL DEFAULT '#e8f0fe',
    position    INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL,
    synced      INTEGER NOT NULL DEFAULT 0
  );
  CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    room_id     TEXT NOT NULL,
    name        TEXT NOT NULL,
    freq_type   TEXT NOT NULL DEFAULT 'weekly',
    week_days   TEXT NOT NULL DEFAULT '[]',
    freq_value  INTEGER NOT NULL DEFAULT 1,
    freq_unit   TEXT NOT NULL DEFAULT 'days',
    last_done   TEXT,
    done_today  INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL,
    synced      INTEGER NOT NULL DEFAULT 0
  );
  CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
  );
`;

/* ─── Inicjalizacja ─── */
export async function initDB() {
  const Cap = window.Capacitor;
  if (Cap && Cap.isNativePlatform()) {
    const plugin = Cap.Plugins?.CapacitorSQLite;
    if (plugin) {
      try {
        // Sprawdź / otwórz połączenie
        const connCheck = await plugin.isConnection({ database: DB_NAME, readonly: false });
        if (!connCheck.result) {
          await plugin.createConnection({
            database: DB_NAME,
            version: DB_VERSION,
            encrypted: false,
            mode: 'no-encryption',
            readonly: false
          });
        }
        const openCheck = await plugin.isDBOpen({ database: DB_NAME });
        if (!openCheck.result) {
          await plugin.open({ database: DB_NAME });
        }
        // Uruchom migracje
        await plugin.execute({ database: DB_NAME, statements: SCHEMA_SQL });
        _plugin = plugin;
        _native = true;
        console.log('[DB] SQLite ready (native)');
      } catch (err) {
        console.warn('[DB] SQLite init failed, using localStorage:', err);
      }
    }
  }
  if (!_native) {
    _initLocalStorage();
    console.log('[DB] localStorage fallback active');
  }
}

function _initLocalStorage() {
  if (!localStorage.getItem('db_rooms'))    localStorage.setItem('db_rooms', '[]');
  if (!localStorage.getItem('db_tasks'))    localStorage.setItem('db_tasks', '[]');
  if (!localStorage.getItem('db_settings')) localStorage.setItem('db_settings', '{}');
}

/* ─── Pomocnicze funkcje niskiego poziomu ─── */
async function _run(sql, values = []) {
  if (_native) {
    return _plugin.run({ database: DB_NAME, statement: sql, values, transaction: false });
  }
}

async function _query(sql, values = []) {
  if (_native) {
    const res = await _plugin.query({ database: DB_NAME, statement: sql, values });
    return res.values || [];
  }
  return [];
}

async function _execute(statements) {
  if (_native) {
    return _plugin.execute({ database: DB_NAME, statements });
  }
}

/* ─── UUID helper ─── */
export function newId() {
  return crypto.randomUUID
    ? crypto.randomUUID()
    : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
        const r = Math.random() * 16 | 0;
        return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
      });
}

function now() { return new Date().toISOString(); }

/* ═══════════════════════════════════════
   Rooms
═══════════════════════════════════════ */

export async function getRooms() {
  if (_native) {
    const rows = await _query('SELECT * FROM rooms ORDER BY position ASC, name ASC');
    return rows.map(r => ({ ...r, tasks: [] }));
  }
  return JSON.parse(localStorage.getItem('db_rooms') || '[]');
}

export async function saveRoom(room) {
  const r = {
    id:         room.id || newId(),
    name:       room.name,
    color:      room.color || '#e8f0fe',
    position:   room.position ?? 0,
    updated_at: now(),
    synced:     0
  };
  if (_native) {
    await _run(
      `INSERT OR REPLACE INTO rooms (id, name, color, position, updated_at, synced)
       VALUES (?,?,?,?,?,?)`,
      [r.id, r.name, r.color, r.position, r.updated_at, 0]
    );
  } else {
    const rooms = await getRooms();
    const idx = rooms.findIndex(x => x.id === r.id);
    if (idx >= 0) rooms[idx] = { ...rooms[idx], ...r };
    else rooms.push(r);
    localStorage.setItem('db_rooms', JSON.stringify(rooms));
  }
  return r;
}

export async function deleteRoom(roomId) {
  if (_native) {
    await _run('DELETE FROM tasks WHERE room_id = ?', [roomId]);
    await _run('DELETE FROM rooms WHERE id = ?', [roomId]);
  } else {
    const rooms = (await getRooms()).filter(r => r.id !== roomId);
    localStorage.setItem('db_rooms', JSON.stringify(rooms));
    const tasks = JSON.parse(localStorage.getItem('db_tasks') || '[]')
      .filter(t => t.room_id !== roomId);
    localStorage.setItem('db_tasks', JSON.stringify(tasks));
  }
}

/* ═══════════════════════════════════════
   Tasks
═══════════════════════════════════════ */

export async function getTasksByRoom(roomId) {
  if (_native) {
    const rows = await _query(
      'SELECT * FROM tasks WHERE room_id = ? ORDER BY name ASC',
      [roomId]
    );
    return rows.map(_parseTask);
  }
  const all = JSON.parse(localStorage.getItem('db_tasks') || '[]');
  return all.filter(t => t.room_id === roomId);
}

export async function getAllTasks() {
  if (_native) {
    const rows = await _query('SELECT * FROM tasks ORDER BY room_id, name');
    return rows.map(_parseTask);
  }
  return JSON.parse(localStorage.getItem('db_tasks') || '[]');
}

function _parseTask(row) {
  return {
    ...row,
    week_days: typeof row.week_days === 'string'
      ? JSON.parse(row.week_days) : (row.week_days || []),
    done_today: row.done_today === 1 || row.done_today === true
  };
}

export async function saveTask(task) {
  const t = {
    id:         task.id || newId(),
    room_id:    task.room_id,
    name:       task.name,
    freq_type:  task.freq_type  || 'weekly',
    week_days:  task.week_days  || [],
    freq_value: task.freq_value || 1,
    freq_unit:  task.freq_unit  || 'days',
    last_done:  task.last_done  || null,
    done_today: task.done_today ? 1 : 0,
    updated_at: now(),
    synced:     task.synced   ?? 0
  };
  if (_native) {
    await _run(
      `INSERT OR REPLACE INTO tasks
       (id, room_id, name, freq_type, week_days, freq_value, freq_unit,
        last_done, done_today, updated_at, synced)
       VALUES (?,?,?,?,?,?,?,?,?,?,?)`,
      [
        t.id, t.room_id, t.name, t.freq_type,
        JSON.stringify(t.week_days), t.freq_value, t.freq_unit,
        t.last_done, t.done_today, t.updated_at, t.synced
      ]
    );
  } else {
    const tasks = JSON.parse(localStorage.getItem('db_tasks') || '[]');
    const idx = tasks.findIndex(x => x.id === t.id);
    if (idx >= 0) tasks[idx] = { ...tasks[idx], ...t };
    else tasks.push(t);
    localStorage.setItem('db_tasks', JSON.stringify(tasks));
  }
  return t;
}

export async function deleteTask(taskId) {
  if (_native) {
    await _run('DELETE FROM tasks WHERE id = ?', [taskId]);
  } else {
    const tasks = JSON.parse(localStorage.getItem('db_tasks') || '[]')
      .filter(t => t.id !== taskId);
    localStorage.setItem('db_tasks', JSON.stringify(tasks));
  }
}

/**
 * Oznacza zadanie jako wykonane (lub nie) dzisiaj.
 * Ustawia synced=0 (pending).
 */
export async function markTaskDone(taskId, done) {
  const todayStr = new Date().toISOString().slice(0, 10);
  if (_native) {
    await _run(
      `UPDATE tasks
       SET done_today=?, last_done=?, updated_at=?, synced=0
       WHERE id=?`,
      [done ? 1 : 0, done ? todayStr : null, now(), taskId]
    );
  } else {
    const tasks = JSON.parse(localStorage.getItem('db_tasks') || '[]');
    const t = tasks.find(x => x.id === taskId);
    if (t) {
      t.done_today = done;
      t.last_done  = done ? todayStr : t.last_done;
      t.updated_at = now();
      t.synced     = 0;
      localStorage.setItem('db_tasks', JSON.stringify(tasks));
    }
  }
}

/* ═══════════════════════════════════════
   Settings
═══════════════════════════════════════ */

export async function getSetting(key, defaultVal = null) {
  if (_native) {
    const rows = await _query('SELECT value FROM settings WHERE key=?', [key]);
    return rows.length ? rows[0].value : defaultVal;
  }
  const s = JSON.parse(localStorage.getItem('db_settings') || '{}');
  return s[key] ?? defaultVal;
}

export async function setSetting(key, value) {
  if (_native) {
    await _run(
      'INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)',
      [key, String(value)]
    );
  } else {
    const s = JSON.parse(localStorage.getItem('db_settings') || '{}');
    s[key] = String(value);
    localStorage.setItem('db_settings', JSON.stringify(s));
  }
}

/* ═══════════════════════════════════════
   Import / Export (do synchronizacji)
═══════════════════════════════════════ */

/**
 * Eksportuje całą lokalną bazę do formatu zgodnego z API backendu.
 */
export async function exportData() {
  const rooms = _native
    ? await _query('SELECT * FROM rooms ORDER BY position, name')
    : await getRooms();

  const tasks = _native
    ? (await _query('SELECT * FROM tasks ORDER BY room_id, name')).map(_parseTask)
    : await getAllTasks();

  const enrichedRooms = rooms.map(r => ({
    id:       r.id,
    name:     r.name,
    color:    r.color,
    position: r.position,
    tasks: tasks
      .filter(t => t.room_id === r.id)
      .map(t => ({
        id:         t.id,
        name:       t.name,
        freq_type:  t.freq_type,
        week_days:  t.week_days,
        freq_value: t.freq_value,
        freq_unit:  t.freq_unit,
        last_done:  t.last_done
      }))
  }));

  // Ustawienia
  const settings = {};
  if (_native) {
    const rows = await _query('SELECT key, value FROM settings');
    rows.forEach(r => { settings[r.key] = r.value; });
  } else {
    const s = JSON.parse(localStorage.getItem('db_settings') || '{}');
    Object.assign(settings, s);
  }

  return {
    rooms: enrichedRooms,
    settings: {
      corridor_parity:    settings.corridor_parity    || 'even',
      corridor_task_name: settings.corridor_task_name || 'Sprzątanie korytarza',
      quick_count:        parseInt(settings.quick_count) || 2,
      ...settings
    },
    meta: { last_corridor_added: settings.last_corridor_added || '' }
  };
}

/**
 * Importuje dane z serwera do lokalnej bazy SQLite.
 * Nadpisuje istniejące dane (REPLACE INTO).
 */
export async function importData(data) {
  if (!data || !Array.isArray(data.rooms)) return;

  if (_native) {
    // Budujemy batch SQL
    let statements = '';
    for (const room of data.rooms) {
      const esc = s => (s || '').replace(/'/g, "''");
      statements += `INSERT OR REPLACE INTO rooms (id, name, color, position, updated_at, synced)
        VALUES ('${esc(room.id)}','${esc(room.name)}','${esc(room.color || '#e8f0fe')}',
        ${room.position || 0},'${now()}',1);\n`;
      for (const task of (room.tasks || [])) {
        const wd = JSON.stringify(task.week_days || []).replace(/'/g, "''");
        statements += `INSERT OR REPLACE INTO tasks
          (id, room_id, name, freq_type, week_days, freq_value, freq_unit,
           last_done, done_today, updated_at, synced)
          VALUES ('${esc(task.id)}','${esc(room.id)}','${esc(task.name)}',
          '${esc(task.freq_type || 'weekly')}','${wd}',
          ${task.freq_value || 1},'${esc(task.freq_unit || 'days')}',
          ${task.last_done ? "'" + task.last_done + "'" : 'NULL'},
          0,'${now()}',1);\n`;
      }
    }
    if (statements) await _execute(statements);

    // Ustawienia
    const s = data.settings || {};
    for (const [k, v] of Object.entries(s)) {
      await _run('INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)', [k, String(v)]);
    }
  } else {
    // localStorage
    const rooms = [];
    const tasks = [];
    for (const room of data.rooms) {
      rooms.push({ id: room.id, name: room.name, color: room.color || '#e8f0fe', position: room.position || 0, updated_at: now(), synced: 1 });
      for (const task of (room.tasks || [])) {
        tasks.push({ ...task, room_id: room.id, done_today: false, updated_at: now(), synced: 1 });
      }
    }
    localStorage.setItem('db_rooms', JSON.stringify(rooms));
    localStorage.setItem('db_tasks', JSON.stringify(tasks));
    if (data.settings) {
      const s = {};
      Object.entries(data.settings).forEach(([k, v]) => { s[k] = String(v); });
      localStorage.setItem('db_settings', JSON.stringify(s));
    }
  }
}

/**
 * Zwraca liczbę rekordów oczekujących na synchronizację.
 */
export async function getPendingCount() {
  if (_native) {
    const r = await _query('SELECT COUNT(*) as c FROM rooms WHERE synced=0');
    const t = await _query('SELECT COUNT(*) as c FROM tasks WHERE synced=0');
    return (r[0]?.c || 0) + (t[0]?.c || 0);
  }
  return 0; // w localStorage nie śledzimy pending
}

/**
 * Oznacza wszystkie rekordy jako zsynchronizowane.
 */
export async function markAllSynced() {
  if (_native) {
    await _execute('UPDATE rooms SET synced=1; UPDATE tasks SET synced=1;');
  }
}

/**
 * Resetuje flagę done_today dla wszystkich zadań (wywołuj o północy).
 */
export async function resetDoneToday() {
  if (_native) {
    await _execute('UPDATE tasks SET done_today=0;');
  } else {
    const tasks = JSON.parse(localStorage.getItem('db_tasks') || '[]');
    tasks.forEach(t => { t.done_today = false; });
    localStorage.setItem('db_tasks', JSON.stringify(tasks));
  }
}
