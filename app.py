from flask import Flask, request, redirect, url_for, render_template_string
import os, json, uuid, datetime, calendar, webbrowser

APP_PORT = 5000
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")

app = Flask(__name__)


# --- Helpers ---

def today():
    return datetime.date.today()

def iso(d):
    return d.isoformat() if d else None

def parse_iso(s):
    return datetime.date.fromisoformat(s) if s else None

def load_data():
    if not os.path.exists(DATA_FILE):
        data = default_data()
        save_data(data)
        return data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("settings", {})
    data["settings"].setdefault("corridor_parity", "even")
    data["settings"].setdefault("corridor_task_name", "Sprzatanie korytarza")
    data["settings"].setdefault("quick_count", 2)
    data.setdefault("meta", {})
    data["meta"].setdefault("last_corridor_added", "")
    # Migracja: konwersja week_day (liczba) na week_days (lista)
    for _r in data.get("rooms", []):
        # Migracja: dodaj kolor pokoju jeśli go brak
        _r.setdefault("color", "#f5f5f5")
        for _t in _r.get("tasks", []):
            if "week_day" in _t and _t["week_day"] is not None and "week_days" not in _t:
                # Stara struktura: skonwertuj na nową
                _t["week_days"] = [int(_t["week_day"])]
                del _t["week_day"]
            _t.setdefault("week_days", [])
            # Migracja: freq_type / freq_value / freq_unit
            if "freq_type" not in _t:
                if _t.get("week_days"):
                    _t["freq_type"] = "weekly"
                elif _t.get("frequency"):
                    _t["freq_type"] = "periodic"
                    _t.setdefault("freq_value", int(_t["frequency"]))
                    _t.setdefault("freq_unit", "days")
                else:
                    _t["freq_type"] = "weekly"
            _t.setdefault("freq_value", 1)
            _t.setdefault("freq_unit", "days")
    return data

def default_data():
    return {
        "rooms": [],
        "settings": {
            "corridor_parity": "even",
            "corridor_task_name": "Sprzatanie korytarza",
            "quick_count": 2
        },
        "meta": {"last_corridor_added": ""}
    }

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def find_room(data, room_id):
    for r in data["rooms"]:
        if r["id"] == room_id:
            return r
    return None

def find_task(data, task_id):
    for r in data["rooms"]:
        for t in r.get("tasks", []):
            if t["id"] == task_id:
                return r, t
    return None, None

def ensure_corridor_task(data):
    today_date = today()
    if today_date.weekday() != 5:
        return
    parity = data["settings"].get("corridor_parity", "even")
    is_even = (today_date.month % 2 == 0)
    if is_even != (parity == "even"):
        return
    month_tag = f"{today_date.year}-{today_date.month}"
    if data["meta"].get("last_corridor_added") == month_tag:
        return
    corridor_room = next(
        (r for r in data["rooms"]
         if r.get("id") == "corridor-room" or r.get("name", "").lower() == "korytarz"),
        None
    )
    if not corridor_room:
        corridor_room = {"id": "corridor-room", "name": "Korytarz", "tasks": []}
        data["rooms"].append(corridor_room)
    task_name = data["settings"].get("corridor_task_name", "Sprzatanie korytarza")
    t = {
        "id": str(uuid.uuid4()),
        "name": task_name,
        "freq_type": "periodic",
        "week_days": [],
        "freq_value": 7,
        "freq_unit": "days",
        "frequency": None,
        "priority": 2,
        "one_time": False,
        "last_done": None,
        "created_at": iso(today_date)
    }
    corridor_room.setdefault("tasks", []).append(t)
    data["meta"]["last_corridor_added"] = month_tag
    save_data(data)

# Skrócone i pełne nazwy dni tygodnia (0=Pon … 6=Nd)
WEEK_DAYS_SHORT = ["Pon", "Wt", "\u015ar", "Czw", "Pt", "So", "Nd"]
WEEK_DAYS_FULL  = [
    "Poniedzia\u0142ek", "Wtorek", "\u015aroda",
    "Czwartek", "Pi\u0105tek", "Sobota", "Niedziela"
]
FREQ_UNIT_LABELS = {"days": "dni", "weeks": "tygodnie", "months": "miesi\u0105ce", "years": "lata"}
FREQ_UNIT_SHORT  = {"days": "dni", "weeks": "tyg.", "months": "mies.", "years": "lat"}

def week_days_str(week_day_names, week_days):
    """Konwertuje listę indeksów dni na string"""
    if not week_days:
        return ""
    return ", ".join(week_day_names[i] for i in sorted(week_days) if 0 <= i < len(week_day_names))

def _most_recent_weekday(week_day):
    """Zwraca datę ostatniego wystąpienia danego dnia tygodnia (włącznie z dziś)."""
    today_date = today()
    diff = (today_date.weekday() - week_day) % 7
    return today_date - datetime.timedelta(days=diff)


def compute_next_periodic(last_done, freq_value, freq_unit):
    """Oblicza następny termin wykonania zadania okresowego."""
    if not last_done:
        return today()
    v = max(1, int(freq_value or 1))
    if freq_unit == "days":
        return last_done + datetime.timedelta(days=v)
    elif freq_unit == "weeks":
        return last_done + datetime.timedelta(weeks=v)
    elif freq_unit == "months":
        m_total = last_done.month - 1 + v
        yr = last_done.year + m_total // 12
        mo = m_total % 12 + 1
        d  = min(last_done.day, calendar.monthrange(yr, mo)[1])
        return datetime.date(yr, mo, d)
    elif freq_unit == "years":
        yr = last_done.year + v
        d  = min(last_done.day, calendar.monthrange(yr, last_done.month)[1])
        return datetime.date(yr, last_done.month, d)
    return last_done + datetime.timedelta(days=v)


def freq_label(freq_value, freq_unit):
    v = int(freq_value or 1)
    return f"Co {v} {FREQ_UNIT_SHORT.get(freq_unit, freq_unit)}"


def _compute_due_weekly(t):
    week_days = t.get("week_days", [])
    if not week_days:
        return False, 0, today() + datetime.timedelta(days=7)
    last     = parse_iso(t.get("last_done"))
    created  = parse_iso(t.get("created_at"))
    today_d  = today()
    today_wd = today_d.weekday()
    
    # Sprawdź czy dzisiaj jest jeden z przypisanych dni
    if today_wd in week_days:
        # Zadanie przypada na dziś - czy zostało już zrobione?
        last_occ = today_d
        if created and created > last_occ:
            return False, 0, last_occ + datetime.timedelta(days=7)
        if last is None or last < last_occ:
            return True, (today_d - last_occ).days, last_occ
        return False, 0, last_occ + datetime.timedelta(days=7)
    
    # Dzisiaj nie jest przypisanym dniem - znajdź najbliższy przyszły dzień
    for i in range(1, 8):
        future_date = today_d + datetime.timedelta(days=i)
        if future_date.weekday() in week_days:
            return False, 0, future_date
    
    return False, 0, today_d + datetime.timedelta(days=7)


def compute_due(t):
    if t.get("one_time"):
        return True, 0, today()
    freq_type = t.get("freq_type", "weekly" if t.get("week_days") else "periodic")
    if freq_type == "weekly":
        if t.get("week_days"):
            return _compute_due_weekly(t)
        return False, 0, today() + datetime.timedelta(days=7)
    # periodic
    last = parse_iso(t.get("last_done"))
    if not last:
        return True, 0, today()
    freq_value = t.get("freq_value") or t.get("frequency") or 7
    freq_unit  = t.get("freq_unit", "days")
    next_due   = compute_next_periodic(last, freq_value, freq_unit)
    overdue_days = (today() - next_due).days
    return (next_due <= today()), max(0, overdue_days), next_due


# --- Template ---

BASE = r"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AgatClean</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { background: #f7faf9; }
    .logo-wrap { display:flex; align-items:center; gap:.55rem; }
    .app-name { font-weight:700; font-size:1.2rem; line-height:1.1; }
    .app-sub  { font-size:.78rem; color:#777; }
    .priority-3 { background: #ffd6d6 !important; }
    .priority-2 { background: #fff8d0 !important; }
    .priority-1 { background: #e6f7ee !important; }
    .card { border-radius: 14px; border: 1px solid #e3eae5; }
    .task-card { border-radius: 10px; padding: .8rem 1rem; margin-bottom: .6rem; border: 1px solid #e0e0e0; cursor: grab; display: flex !important; justify-content: space-between !important; align-items: center !important; }
    .task-card:active { cursor: grabbing; }
    .task-card.dragging { opacity: 0.6; box-shadow: 0 5px 15px rgba(0,0,0,0.2); }
    .room-card { transition: all 0.2s ease; }
    .room-card:active { cursor: grabbing; }
    .room-card.dragging { opacity: 0.5; transform: scale(0.95); box-shadow: 0 5px 15px rgba(0,0,0,0.3) !important; }
    .rooms-list.drag-over { background: #e8f4f0 !important; border-color: #1a73e8 !important; }
    .tasks-list { min-height: 50px; position: relative; }
    .tasks-list.drag-over { background: #e8f4f0 !important; border-radius: 8px; border-color: #1a73e8 !important; }
    .overdue-badge { font-size: .8rem; font-weight:600; color:#c0392b; }
    .small-muted { font-size:.82rem; color:#888; }
    .navbar { border-bottom: 1px solid #e8eee9; }
  </style>
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-light bg-white shadow-sm mb-4">
  <div class="container-lg">
    <a class="navbar-brand logo-wrap text-decoration-none text-dark" href="/">
      <svg width="36" height="36" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="64" height="64" rx="12" fill="#1a73e8"/>
        <rect x="14" y="18" width="36" height="7" rx="3" fill="white"/>
        <rect x="14" y="31" width="28" height="7" rx="3" fill="white"/>
        <rect x="14" y="44" width="20" height="7" rx="3" fill="white"/>
      </svg>
      <div>
        <div class="app-name">AgatClean</div>
        <div class="app-sub">Planer sprzatania domu</div>
      </div>
    </a>
    <div class="ms-auto d-flex gap-2 flex-wrap">
      <a class="btn btn-outline-primary btn-sm" href="/manage">Panel</a>
      <a class="btn btn-outline-success btn-sm" href="/schedule">Harmonogram</a>
      <a class="btn btn-outline-info btn-sm" href="/periodic">Okresowe</a>
      <a class="btn btn-outline-warning btn-sm" href="/quick">Malo czasu</a>
      <a class="btn btn-outline-secondary btn-sm" href="/settings">Ustawienia</a>
    </div>
  </div>
</nav>
<div class="container-lg">
__BODY__
</div>
</body>
</html>"""


def render_page(body, **ctx):
    full = BASE.replace("__BODY__", body)
    return render_template_string(full, **ctx)


# --- Routes ---

@app.route("/")
def index():
    data = load_data()
    ensure_corridor_task(data)
    tasks_today = []
    for room in data["rooms"]:
        for t in room.get("tasks", []):
            due, overdue_days, next_due = compute_due(t)
            if due:
                tasks_today.append({
                    "room_id": room["id"],
                    "room_name": room["name"],
                    "room_color": room.get("color", "#f5f5f5"),
                    "task": t,
                    "overdue_days": overdue_days,
                    "next_due": iso(next_due)
                })
    tasks_today.sort(key=lambda x: (-int(x["task"].get("priority", 1)), -x["overdue_days"]))

    body = """
<div class="row g-4">
  <div class="col-lg-8">
    <div class="card p-3 p-md-4">
      <h5 class="mb-3">Zadania na dzis</h5>
      {% if tasks %}
        {% for item in tasks %}
          {% set p = item.task.priority | int %}
          <div class="task-card priority-{{ p }} d-flex justify-content-between align-items-center" style="background-color: {{ item.room_color }}; border: 2px solid {{ item.room_color }}; opacity: 0.95;">
            <div>
              <div style="font-weight:600; font-size:1rem;">
                {{ item.task.name }}
                {% if item.task.one_time %}<span class="badge bg-info text-dark ms-1" style="font-size:.7rem;">Jednorazowe</span>{% endif %}
              </div>
              <div class="small-muted mt-1">
                Pokoj: <strong>{{ item.room_name }}</strong>
                {% if not item.task.one_time %}
                  | {% if item.task.freq_type == 'weekly' %}{{ week_days_str(week_day_names, item.task.week_days) }}{% elif item.task.freq_type == 'periodic' %}Co {{ item.task.freq_value }} {{ freq_unit_labels.get(item.task.freq_unit, '') }}{% endif %}
                  | Ostatnio: {{ item.task.last_done or "-" }}
                {% endif %}
              </div>
            </div>
            <div class="text-end ms-3">
              {% if item.overdue_days > 0 %}
                <div class="overdue-badge mb-1">+{{ item.overdue_days }} dni</div>
              {% endif %}
              <form method="post" action="{{ url_for('mark_done', task_id=item.task.id) }}">
                <button class="btn btn-success btn-sm">Zrobione</button>
              </form>
            </div>
          </div>
        {% endfor %}
      {% else %}
        <div class="text-muted py-3">Brak zadan na dzis!</div>
      {% endif %}
    </div>
  </div>
  <div class="col-lg-4">
    <div class="card p-3">
      <h6 class="mb-3">Pokoje</h6>
      {% if rooms %}
        <ul class="list-group list-group-flush">
          {% for r in rooms %}
            <li class="list-group-item d-flex justify-content-between px-0">
              <span>{{ r.name }}</span>
              <span class="badge bg-secondary rounded-pill">{{ r.tasks | length }}</span>
            </li>
          {% endfor %}
        </ul>
      {% else %}
        <div class="small-muted">Brak pokoi. Dodaj je w <a href="/manage">Panelu</a>.</div>
      {% endif %}
    </div>
  </div>
</div>
"""
    return render_page(body, tasks=tasks_today, rooms=data["rooms"],
                       week_day_names=WEEK_DAYS_SHORT, week_days_str=week_days_str,
                       freq_unit_labels=FREQ_UNIT_LABELS)


@app.route("/done/<task_id>", methods=["POST"])
def mark_done(task_id):
    data = load_data()
    _, task = find_task(data, task_id)
    if task:
        if task.get("one_time"):
            for r in data["rooms"]:
                r["tasks"] = [t for t in r.get("tasks", []) if t["id"] != task_id]
        else:
            task["last_done"] = iso(today())
        save_data(data)
    return redirect(url_for("index"))


@app.route("/manage")
def manage():
    data = load_data()
    body = """
<div class="row g-4">
  <!-- LEWA KOLUMNA: Pokoje + Dodaj zadanie -->
  <div class="col-lg-4">
    <div class="card p-3 p-md-4 mb-4">
      <h5 class="mb-3">Dodaj pokój</h5>
      <form method="post" action="{{ url_for('add_room') }}">
        <div class="mb-2">
          <input name="name" class="form-control" placeholder="Nazwa pokoju" required>
        </div>
        <div class="mb-2">
          <label class="form-label small-muted">Kolor pokoju</label>
          <div class="input-group">
            <input type="color" name="color" class="form-control form-control-color" value="#f5f5f5" title="Wybierz kolor">
            <button class="btn btn-primary" type="submit">Dodaj</button>
          </div>
        </div>
      </form>
    </div>
    <div class="card p-3 p-md-4 mb-4">
      <h5 class="mb-3">Dodaj zadanie</h5>
      {% if rooms %}
      <form method="post" action="{{ url_for('add_task') }}">
        <div class="mb-2">
          <input name="name" class="form-control" placeholder="Nazwa zadania" required>
        </div>
        <div class="mb-2">
          <select name="room_id" class="form-select" required>
            {% for r in rooms %}
              <option value="{{ r.id }}">{{ r.name }}</option>
            {% endfor %}
          </select>
        </div>
        <div class="mb-2 form-check">
          <input class="form-check-input" type="checkbox" name="one_time" value="1" id="oneTimeCheck">
          <label class="form-check-label small-muted" for="oneTimeCheck">Zadanie jednorazowe / na dzis</label>
        </div>
        <div id="freqRow">
          <div class="mb-2">
            <label class="form-label small-muted fw-semibold">Typ częstotliwości</label>
            <div class="btn-group w-100" role="group">
              <input type="radio" class="btn-check" name="freq_type" value="weekly" id="ft_weekly_new" checked>
              <label class="btn btn-outline-secondary btn-sm" for="ft_weekly_new">Dzień tygodnia</label>
              <input type="radio" class="btn-check" name="freq_type" value="periodic" id="ft_periodic_new">
              <label class="btn btn-outline-secondary btn-sm" for="ft_periodic_new">Okresowa</label>
            </div>
          </div>
          <div id="weeklySection_new">
            <div class="mb-2">
              <label class="form-label small-muted">Dni tygodnia</label>
              <div class="d-flex flex-wrap gap-2">
                {% for wd_i, wd_n in week_day_options %}
                <div class="form-check">
                  <input class="form-check-input" type="checkbox" name="week_days" value="{{ wd_i }}" id="wd_{{ wd_i }}">
                  <label class="form-check-label" for="wd_{{ wd_i }}">{{ wd_n }}</label>
                </div>
                {% endfor %}
              </div>
              <div class="small-muted mt-1">Zaznacz dni, w które zadanie powinno być wykonane</div>
            </div>
          </div>
          <div id="periodicSection_new" style="display:none;">
            <div class="mb-2">
              <label class="form-label small-muted">Powtarzaj co</label>
              <div class="input-group">
                <input type="number" name="freq_value" class="form-control" min="1" value="1" placeholder="np. 2">
                <select name="freq_unit" class="form-select">
                  <option value="days">dni</option>
                  <option value="weeks">tygodnie</option>
                  <option value="months">miesiące</option>
                  <option value="years">lata</option>
                </select>
              </div>
            </div>
          </div>
          <div class="mb-2">
            <label class="form-label small-muted">Priorytet</label>
            <select name="priority" class="form-select">
              <option value="3">3 - Wysoki</option>
              <option value="2" selected>2 - Sredni</option>
              <option value="1">1 - Niski</option>
            </select>
          </div>
        </div>
        <button class="btn btn-primary w-100">Dodaj zadanie</button>
      </form>
      {% else %}
        <div class="small-muted">Najpierw dodaj pokój.</div>
      {% endif %}
    </div>
  </div>

  <!-- PRAWA KOLUMNA: Wszystkie zadania -->
  <div class="col-lg-8">
    <div class="card p-3 p-md-4">
      <h5 class="mb-1">Wszystkie zadania</h5>
      <p class="small-muted mb-3">Przeciagnij zadanie do innego pokoju, aby je przeniesc</p>
      {% if rooms %}
        {% for r in rooms %}
        <div class="mb-4" data-room-id="{{ r.id }}">
          <div class="d-flex align-items-center gap-2 mb-2 pb-1" style="border-bottom:2px solid #e3eae5;">
            <span style="font-size:1.1rem;">></span>
            <span class="fw-bold fs-6" style="flex-grow:1;">{{ r.name }}</span>
            <form method="post" action="{{ url_for('update_room_color', room_id=r.id) }}" class="d-flex gap-1 align-items-center m-0">
              <input type="color" name="color" class="form-control form-control-color" value="{{ r.color }}" title="Zmien kolor pokoju" style="width:45px; height:38px; border:none; padding:2px;">
              <button type="submit" class="btn btn-sm btn-outline-secondary" style="padding:4px 6px;">OK</button>
            </form>
            <span class="badge bg-secondary rounded-pill">{{ r.tasks | length }}</span>
          </div>
          <div class="tasks-list" data-room-id="{{ r.id }}"
               {% if not r.tasks %}style="padding:0.75rem 1rem; color:#999; border:1px dashed #ddd; border-radius:8px; background:#fafafa;"{% endif %}>
            {% if r.tasks %}
              {% for t in r.tasks %}
              <div class="task-card priority-{{ t.priority }} d-flex justify-content-between align-items-center"
                   draggable="true" data-task-id="{{ t.id }}" data-room-id="{{ r.id }}" style="background-color: {{ r.color }}; border: 2px solid {{ r.color }}; opacity: 0.95;">
                <div style="flex:1; min-width:0;">
                  <div style="font-weight:600; font-size:1rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                    {{ t.name }}
                    {% if t.one_time %}<span class="badge bg-info text-dark ms-1" style="font-size:.7rem;">Jednorazowe</span>{% endif %}
                  </div>
                  <div class="small-muted mt-1">
                    {% if not t.one_time %}
                      {% if t.freq_type == 'weekly' %}{{ week_days_str(week_day_names, t.week_days) }}{% elif t.freq_type == 'periodic' %}Co {{ t.freq_value }} {{ freq_unit_labels.get(t.freq_unit, '') }}{% endif %}
                      | Ostatnio: {{ t.last_done or "-" }}
                    {% endif %}
                    <span class="badge {% if t.priority==3 %}bg-danger{% elif t.priority==2 %}bg-warning text-dark{% else %}bg-success{% endif %}">
                      P{{ t.priority }}
                    </span>
                  </div>
                </div>
                <div class="ms-3 d-flex gap-1 align-items-center flex-shrink-0">
                  <form method="post" action="{{ url_for('edit_task', task_id=t.id) }}" class="d-flex gap-1 align-items-center m-0">
                    {% if not t.one_time %}
                      {% if t.freq_type == 'periodic' %}
                      <input type="number" name="freq_value" value="{{ t.freq_value or 1 }}" min="1" class="form-control form-control-sm" style="width:55px;" title="Powtarzaj co">
                      <select name="freq_unit" class="form-select form-select-sm" style="width:85px">
                        <option value="days" {% if t.freq_unit == 'days' %}selected{% endif %}>dni</option>
                        <option value="weeks" {% if t.freq_unit == 'weeks' %}selected{% endif %}>tyg.</option>
                        <option value="months" {% if t.freq_unit == 'months' %}selected{% endif %}>mies.</option>
                        <option value="years" {% if t.freq_unit == 'years' %}selected{% endif %}>lat</option>
                      </select>
                      <input type="hidden" name="freq_type" value="periodic">
                      {% else %}
                      <div class="btn-group" role="group" style="flex-wrap: wrap;">
                        {% for wd_i, wd_n in week_day_options %}
                        <input type="checkbox" class="btn-check" name="week_days" value="{{ wd_i }}" id="ed_{{ t.id }}_{{ wd_i }}" {% if wd_i|int in t.week_days %}checked{% endif %}>
                        <label class="btn btn-outline-secondary btn-sm" for="ed_{{ t.id }}_{{ wd_i }}" style="padding:2px 6px; font-size:0.75rem;">{{ wd_n }}</label>
                        {% endfor %}
                      </div>
                      <input type="hidden" name="freq_type" value="weekly">
                      {% endif %}
                    {% endif %}
                    <select name="priority" class="form-select form-select-sm" style="width:63px">
                      <option {% if t.priority==3 %}selected{% endif %} value="3">3</option>
                      <option {% if t.priority==2 %}selected{% endif %} value="2">2</option>
                      <option {% if t.priority==1 %}selected{% endif %} value="1">1</option>
                    </select>
                    <button class="btn btn-sm btn-outline-secondary">Edytuj</button>
                  </form>
                  <form method="post" action="{{ url_for('delete_task', task_id=t.id) }}"
                        onsubmit="return confirm('Usun To Zadanie?')" class="m-0">
                    <button class="btn btn-sm btn-outline-danger">Usun</button>
                  </form>
                </div>
              </div>
              {% endfor %}
            {% else %}
              Brak zadan
            {% endif %}
          </div>
        </div>
        {% endfor %}
      {% else %}
        <div class="small-muted py-3 text-center">Dodaj pokój, aby móc przypisywać zadania.</div>
      {% endif %}
    </div>
  </div>
</div>
<script>
document.addEventListener('DOMContentLoaded', function() {
  // Toggle frequency row on one_time checkbox
  var cb = document.getElementById('oneTimeCheck');
  var freqRow = document.getElementById('freqRow');
  if (cb) {
    cb.addEventListener('change', function() {
      freqRow.style.display = this.checked ? 'none' : '';
    });
  }
  // Toggle weekly / periodic sections
  document.querySelectorAll('input[name="freq_type"]').forEach(function(radio) {
    radio.addEventListener('change', function() {
      var isWeekly = this.value === 'weekly';
      var ws = document.getElementById('weeklySection_new');
      var ps = document.getElementById('periodicSection_new');
      if (ws) ws.style.display = isWeekly ? '' : 'none';
      if (ps) ps.style.display = isWeekly ? 'none' : '';
    });
  });

  // ===== DRAG & DROP TASKS =====
  let draggedTask = null;
  let draggedTaskId = null;
  let draggedTaskCurrentRoom = null;

  const taskCards = document.querySelectorAll('.task-card[draggable="true"]');
  
  taskCards.forEach(card => {
    card.addEventListener('dragstart', function(e) {
      // Only allow drag from the main text area, not from the form
      if (e.target.closest('form')) {
        e.preventDefault();
        return false;
      }
      
      draggedTask = this;
      draggedTaskId = this.getAttribute('data-task-id');
      draggedTaskCurrentRoom = this.getAttribute('data-room-id');
      
      this.classList.add('dragging');
      this.style.opacity = '0.5';
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('taskId', draggedTaskId);
    });

    card.addEventListener('dragend', function(e) {
      this.classList.remove('dragging');
      this.style.opacity = '1';
      draggedTask = null;
      draggedTaskId = null;
      draggedTaskCurrentRoom = null;
      this.draggable = true;
      
      // Reset all drop zones
      document.querySelectorAll('.tasks-list').forEach(list => {
        list.classList.remove('drag-over');
        list.style.borderColor = '';
        list.style.backgroundColor = '';
      });
    });
  });

  // Drop zones for tasks
  const taskLists = document.querySelectorAll('.tasks-list');
  
  taskLists.forEach(list => {
    list.addEventListener('dragover', function(e) {
      if (!draggedTask) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      this.classList.add('drag-over');
      this.style.borderColor = '#1a73e8';
      this.style.backgroundColor = '#e8f0ff';
    });

    list.addEventListener('dragleave', function(e) {
      if (e.target === this) {
        this.classList.remove('drag-over');
        this.style.borderColor = '';
        this.style.backgroundColor = '';
      }
    });

    list.addEventListener('drop', function(e) {
      e.preventDefault();
      e.stopPropagation();
      
      this.classList.remove('drag-over');
      this.style.borderColor = '';
      this.style.backgroundColor = '';
      
      if (draggedTask && draggedTaskId && draggedTaskCurrentRoom) {
        const newRoomId = this.getAttribute('data-room-id');
        
        // Different room = move
        if (draggedTaskCurrentRoom !== newRoomId) {
          const form = document.createElement('form');
          form.method = 'POST';
          form.action = '/move_task/' + draggedTaskId;
          
          const input = document.createElement('input');
          input.type = 'hidden';
          input.name = 'new_room_id';
          input.value = newRoomId;
          
          form.appendChild(input);
          document.body.appendChild(form);
          form.submit();
        }
      }
    });
  });

});
</script>
</script>
"""
    wd_names = WEEK_DAYS_SHORT
    return render_page(body, rooms=data["rooms"],
                       week_day_names=wd_names,
                       week_days_str=week_days_str,
                       week_day_options=list(enumerate(wd_names)),
                       freq_unit_labels=FREQ_UNIT_LABELS)


@app.route("/add_room", methods=["POST"])
def add_room():
    name = (request.form.get("name") or "").strip()
    color = (request.form.get("color") or "#f5f5f5").strip()
    if not name:
        return redirect(url_for("manage"))
    data = load_data()
    data["rooms"].append({"id": str(uuid.uuid4()), "name": name, "color": color, "tasks": []})
    save_data(data)
    return redirect(url_for("manage"))


@app.route("/add_task", methods=["POST"])
def add_task():
    data = load_data()
    name = (request.form.get("name") or "").strip()
    room_id = request.form.get("room_id", "")
    one_time = request.form.get("one_time") == "1"
    freq_type = request.form.get("freq_type", "weekly") if not one_time else "weekly"
    if freq_type not in ("weekly", "periodic"):
        freq_type = "weekly"
    week_days = []
    freq_value = 1
    freq_unit = "days"
    if not one_time:
        if freq_type == "weekly":
            week_days_raw = request.form.getlist("week_days")
            try:
                week_days = sorted(set(max(0, min(6, int(d))) for d in week_days_raw if d))
            except (ValueError, TypeError):
                week_days = []
        elif freq_type == "periodic":
            try:
                freq_value = max(1, int(request.form.get("freq_value") or 1))
            except (ValueError, TypeError):
                freq_value = 1
            freq_unit = request.form.get("freq_unit", "days")
            if freq_unit not in ("days", "weeks", "months", "years"):
                freq_unit = "days"
    try:
        pr = int(request.form.get("priority") or 2)
    except ValueError:
        pr = 2
    pr = max(1, min(3, pr))
    room = find_room(data, room_id)
    if not name or room is None:
        return redirect(url_for("manage"))
    task = {
        "id": str(uuid.uuid4()),
        "name": name,
        "freq_type": freq_type,
        "week_days": week_days,
        "freq_value": freq_value,
        "freq_unit": freq_unit,
        "frequency": None,
        "priority": pr,
        "one_time": one_time,
        "last_done": None,
        "created_at": iso(today())
    }
    room.setdefault("tasks", []).append(task)
    save_data(data)
    return redirect(url_for("manage"))


@app.route("/edit_task/<task_id>", methods=["POST"])
def edit_task(task_id):
    data = load_data()
    _, task = find_task(data, task_id)
    if task:
        try:
            if not task.get("one_time"):
                freq_type = request.form.get("freq_type", task.get("freq_type", "weekly"))
                if freq_type not in ("weekly", "periodic"):
                    freq_type = "weekly"
                task["freq_type"] = freq_type
                if freq_type == "weekly":
                    week_days_raw = request.form.getlist("week_days")
                    try:
                        task["week_days"] = sorted(set(max(0, min(6, int(d))) for d in week_days_raw if d))
                    except (ValueError, TypeError):
                        task["week_days"] = []
                elif freq_type == "periodic":
                    try:
                        task["freq_value"] = max(1, int(request.form.get("freq_value") or 1))
                    except (ValueError, TypeError):
                        task["freq_value"] = 1
                    freq_unit = request.form.get("freq_unit", "days")
                    if freq_unit not in ("days", "weeks", "months", "years"):
                        freq_unit = "days"
                    task["freq_unit"] = freq_unit
                task["frequency"] = None
            task["priority"] = max(1, min(3, int(request.form.get("priority") or task.get("priority", 2))))
            save_data(data)
        except Exception:
            pass
    return redirect(url_for("manage"))


@app.route("/delete_task/<task_id>", methods=["POST"])
def delete_task(task_id):
    data = load_data()
    for r in data["rooms"]:
        r["tasks"] = [t for t in r.get("tasks", []) if t["id"] != task_id]
    save_data(data)
    return redirect(url_for("manage"))


@app.route("/move_task/<task_id>", methods=["POST"])
def move_task(task_id):
    data = load_data()
    new_room_id = request.form.get("new_room_id", "")
    
    # Find the task and current room
    current_room, task = find_task(data, task_id)
    new_room = find_room(data, new_room_id)
    
    # If both found and different rooms, move the task
    if task and new_room and current_room and current_room["id"] != new_room_id:
        current_room["tasks"] = [t for t in current_room.get("tasks", []) if t["id"] != task_id]
        new_room.setdefault("tasks", []).append(task)
        save_data(data)
    
    return redirect(url_for("manage"))


@app.route("/move_room/<room_id>", methods=["POST"])
def move_room(room_id):
    data = load_data()
    new_position = request.form.get("new_position", "")
    
    try:
        new_pos = int(new_position)
    except ValueError:
        return redirect(url_for("manage"))
    
    # Find room index
    room_idx = None
    for i, r in enumerate(data["rooms"]):
        if r["id"] == room_id:
            room_idx = i
            break
    
    if room_idx is not None:
        # Ensure position is valid
        new_pos = max(0, min(new_pos, len(data["rooms"]) - 1))
        if room_idx != new_pos:
            room = data["rooms"].pop(room_idx)
            data["rooms"].insert(new_pos, room)
            save_data(data)
    
    return redirect(url_for("manage"))


@app.route("/update_room_color/<room_id>", methods=["POST"])
def update_room_color(room_id):
    color = (request.form.get("color") or "#f5f5f5").strip()
    data = load_data()
    room = find_room(data, room_id)
    if room:
        room["color"] = color
        save_data(data)
    return redirect(url_for("manage"))


@app.route("/quick")
def quick():
    data = load_data()
    cnt = max(1, int(data["settings"].get("quick_count", 2) or 2))
    tasks = []
    for r in data["rooms"]:
        for t in r.get("tasks", []):
            due, overdue_days, _ = compute_due(t)
            if due:
                tasks.append({"room": r, "task": t, "overdue_days": overdue_days})
    tasks.sort(key=lambda x: (-int(x["task"].get("priority", 1)), -x["overdue_days"]))
    tasks = tasks[:cnt]

    body = """
<div class="card p-3 p-md-4">
  <h5 class="mb-1">Tryb: mam malo czasu</h5>
  <p class="small-muted mb-3">Pokazuje {{ cnt }} najwazniejszych zadan.</p>
  {% if tasks %}
    {% for it in tasks %}
      <div class="task-card priority-{{ it.task.priority }} d-flex justify-content-between align-items-center" style="background-color: {{ it.room.color }}; border: 2px solid {{ it.room.color }}; opacity: 0.95;">
        <div>
          <div style="font-weight:600; font-size:1rem;">{{ it.task.name }}</div>
          <div class="small-muted mt-1">
            Pokoj: <strong>{{ it.room.name }}</strong> | Priorytet {{ it.task.priority }} | Ostatnio: {{ it.task.last_done or "-" }}
          </div>
        </div>
        <div class="text-end ms-3">
          {% if it.overdue_days > 0 %}
            <div class="overdue-badge mb-1">+{{ it.overdue_days }} dni</div>
          {% endif %}
          <form method="post" action="{{ url_for('mark_done', task_id=it.task.id) }}">
            <button class="btn btn-success btn-sm">Zrobione</button>
          </form>
        </div>
      </div>
    {% endfor %}
  {% else %}
    <div class="text-muted py-3">Brak zaległych zadan!</div>
  {% endif %}
</div>
"""
    return render_page(body, tasks=tasks, cnt=cnt)


@app.route("/settings", methods=["GET", "POST"])
def settings():
    data = load_data()
    saved = False
    if request.method == "POST":
        parity = request.form.get("corridor_parity", "even")
        name = (request.form.get("corridor_task_name") or "").strip()
        try:
            quick_count = max(1, int(request.form.get("quick_count") or 2))
        except ValueError:
            quick_count = 2
        if parity in ("even", "odd"):
            data["settings"]["corridor_parity"] = parity
        if name:
            data["settings"]["corridor_task_name"] = name
        data["settings"]["quick_count"] = quick_count
        save_data(data)
        saved = True

    body = """
<div class="row justify-content-center">
  <div class="col-lg-6">
    <div class="card p-3 p-md-4">
      <h5 class="mb-3">Ustawienia</h5>
      {% if saved %}
        <div class="alert alert-success py-2">Zapisano!</div>
      {% endif %}
      <form method="post">
        <div class="mb-3">
          <label class="form-label fw-semibold">Dyzur korytarza w miesiacach</label>
          <select name="corridor_parity" class="form-select">
            <option value="even" {% if s.corridor_parity == "even" %}selected{% endif %}>Parzystych (kwiecien, czerwiec...)</option>
            <option value="odd"  {% if s.corridor_parity == "odd"  %}selected{% endif %}>Nieparzystych (marzec, maj...)</option>
          </select>
          <div class="small-muted mt-1">Zadanie dodaje sie automatycznie w kazda sobote miesiaca dyzurowego.</div>
        </div>
        <div class="mb-3">
          <label class="form-label fw-semibold">Nazwa zadania korytarza</label>
          <input name="corridor_task_name" class="form-control" value="{{ s.corridor_task_name }}">
        </div>
        <div class="mb-3">
          <label class="form-label fw-semibold">Liczba zadan w trybie mam malo czasu</label>
          <input name="quick_count" type="number" min="1" class="form-control" value="{{ s.quick_count }}">
        </div>
        <button class="btn btn-primary w-100">Zapisz ustawienia</button>
      </form>
      <hr>
      <div class="small-muted">Ostatnie dodanie dyzuru: <strong>{{ meta.last_corridor_added or "brak" }}</strong></div>
    </div>
  </div>
</div>
"""
    return render_page(body, s=data["settings"], meta=data.get("meta", {}), saved=saved)


@app.route("/schedule")
def schedule_view():
    data = load_data()
    sched = [[] for _ in range(7)]
    for room in data["rooms"]:
        for t in room.get("tasks", []):
            week_days = t.get("week_days", [])
            # Dodaj zadanie dla każdego przypisanego dnia
            for wd in week_days:
                if 0 <= wd < 7:
                    sched[int(wd)].append({"room_name": room["name"], "room_color": room.get("color", "#f5f5f5"), "task": t})
    for day_list in sched:
        day_list.sort(key=lambda x: -int(x["task"].get("priority", 1) or 1))
    today_wd = today().weekday()

    body = """
<style>
  .sched-grid {
    display: grid;
    grid-template-columns: repeat(7, minmax(130px, 1fr));
    gap: 10px;
    overflow-x: auto;
    padding-bottom: 4px;
  }
  .sched-col { display: flex; flex-direction: column; min-width: 130px; }
  .sched-header {
    text-align: center;
    padding: 10px 6px 8px;
    border-radius: 10px 10px 0 0;
    font-weight: 700;
    font-size: .88rem;
    letter-spacing: .02em;
    border: 2px solid #dee2e6;
    border-bottom: none;
    background: #f1f3f5;
    color: #495057;
  }
  .sched-header.today {
    background: #1a73e8;
    border-color: #1a73e8;
    color: #fff;
  }
  .sched-header .day-short {
    display: block;
    font-size: .72rem;
    font-weight: 500;
    opacity: .75;
    margin-top: 1px;
  }
  .sched-header.today .day-short { opacity: .85; }
  .sched-body {
    flex: 1;
    border: 2px solid #dee2e6;
    border-top: none;
    border-radius: 0 0 10px 10px;
    padding: 8px 7px 10px;
    background: #fff;
    min-height: 80px;
  }
  .sched-body.today { border-color: #1a73e8; background: #f5f9ff; }
  .sched-task {
    border-radius: 8px;
    padding: 8px 9px 7px;
    margin-bottom: 7px;
    border-left: 4px solid transparent;
    background: #fff;
    box-shadow: 0 1px 4px rgba(0,0,0,.08);
  }
  .sched-task:last-child { margin-bottom: 0; }
  .sched-task.p3 { border-left-color: #dc3545; background: #fff5f5; }
  .sched-task.p2 { border-left-color: #ffc107; background: #fffdf0; }
  .sched-task.p1 { border-left-color: #28a745; background: #f3fff6; }
  .sched-task .t-name {
    font-weight: 700;
    font-size: .88rem;
    line-height: 1.35;
    word-break: break-word;
    color: #212529;
  }
  .sched-task .t-room {
    font-size: .74rem;
    color: #6c757d;
    margin-top: 2px;
  }
  .sched-task .t-meta {
    font-size: .72rem;
    color: #888;
    margin-top: 4px;
    display: flex;
    align-items: center;
    gap: 5px;
    flex-wrap: wrap;
  }
  .sched-task .t-done-btn {
    width: 100%;
    margin-top: 7px;
    font-size: .75rem;
    padding: 3px 0;
    border-radius: 6px;
  }
  .sched-empty {
    text-align: center;
    color: #ced4da;
    font-size: 1.4rem;
    padding: 18px 0 14px;
  }
  .sched-count {
    display: inline-block;
    background: #e9ecef;
    color: #6c757d;
    font-size: .68rem;
    font-weight: 600;
    border-radius: 20px;
    padding: 1px 7px;
    margin-top: 3px;
  }
  .sched-header.today .sched-count {
    background: rgba(255,255,255,.25);
    color: #fff;
  }
</style>

<div class="mb-3 d-flex align-items-center gap-3 flex-wrap">
  <h5 class="mb-0">Harmonogram tygodniowy</h5>
  <a href="/manage" class="btn btn-sm btn-primary ms-auto">Dodaj zadanie</a>
</div>

<div class="sched-grid">
  {% for i in range(7) %}
  <div class="sched-col">
    <div class="sched-header {% if i == today_wd %}today{% endif %}">
      {{ day_full[i] }}
      <span class="day-short">{% if i == today_wd %}DZIS{% else %}{{ day_short[i] | upper }}{% endif %}</span>
      <span class="sched-count">{{ sched[i] | length }}</span>
    </div>
    <div class="sched-body {% if i == today_wd %}today{% endif %}">
      {% if sched[i] %}
        {% for item in sched[i] %}
        <div class="sched-task p{{ item.task.priority }}" style="background-color: {{ item.room_color }}; border-left-color: {{ item.room_color }};opacity: 0.95;">
          <div class="t-name">{{ item.task.name }}</div>
          <div class="t-room">Pokoj: {{ item.room_name }}</div>
          <div class="t-meta">
            {% if item.task.priority == 3 %}
              <span style="color:#dc3545; font-weight:600;">Wysoki</span>
            {% elif item.task.priority == 2 %}
              <span style="color:#e09000; font-weight:600;">Sredni</span>
            {% else %}
              <span style="color:#28a745; font-weight:600;">Niski</span>
            {% endif %}
            |
            {% if item.task.last_done %}
              <span>OK: {{ item.task.last_done }}</span>
            {% else %}
              <span style="color:#adb5bd;">jeszcze nie</span>
            {% endif %}
          </div>
          <form method="post" action="{{ url_for('mark_done', task_id=item.task.id) }}">
            <button class="btn btn-outline-success t-done-btn">Zrobione</button>
          </form>
        </div>
        {% endfor %}
      {% else %}
        <div class="sched-empty">Brak</div>
      {% endif %}
    </div>
  </div>
  {% endfor %}
</div>

<p class="small-muted mt-3 mb-0">
  Harmonogram pokazuje tylko zadania tygodniowe (przypisane do dni tygodnia).
  Zadania z własną częstotliwością (co X dni/tygodni/miesięcy) znajdziesz w <a href="/periodic">widoku Okresowe</a>.
</p>
"""
    return render_page(body, sched=sched, today_wd=today_wd,
                       day_full=WEEK_DAYS_FULL, day_short=WEEK_DAYS_SHORT,
                       week_days_str=week_days_str)


@app.route("/periodic")
def periodic_view():
    data = load_data()
    today_d = today()
    periodic_tasks = []
    for room in data["rooms"]:
        for t in room.get("tasks", []):
            if t.get("one_time"):
                continue
            freq_type = t.get("freq_type", "weekly" if t.get("week_days") else "periodic")
            if freq_type != "periodic":
                continue
            last = parse_iso(t.get("last_done"))
            fv = t.get("freq_value") or t.get("frequency") or 7
            fu = t.get("freq_unit", "days")
            next_due = compute_next_periodic(last, fv, fu) if last else today_d
            is_due = next_due <= today_d
            overdue_days = max(0, (today_d - next_due).days)
            days_until = (next_due - today_d).days
            periodic_tasks.append({
                "room_name": room["name"],
                "room_color": room.get("color", "#f5f5f5"),
                "task": t,
                "next_due": iso(next_due),
                "is_due": is_due,
                "overdue_days": overdue_days,
                "days_until": days_until,
                "flabel": freq_label(fv, fu),
            })
    # Przeterminowane na górze, potem wg daty
    periodic_tasks.sort(key=lambda x: (not x["is_due"], x["next_due"]))

    body = """
<div class="mb-3 d-flex align-items-center gap-3 flex-wrap">
  <h5 class="mb-0">Zadania okresowe</h5>
  <span class="small-muted">— obliczane na podstawie daty ostatniego wykonania</span>
  <a href="/manage" class="btn btn-sm btn-primary ms-auto">+ Dodaj zadanie</a>
</div>
{% if tasks %}
<div class="row g-3">
  {% for item in tasks %}
  {% set p = item.task.priority | int %}
  <div class="col-12 col-md-6 col-xl-4">
    <div class="card h-100" style="border-left:4px solid {{ item.room_color }}; border-radius:12px;">
      <div class="card-body py-3">
        <div class="d-flex justify-content-between align-items-start gap-2">
          <div style="flex:1; min-width:0;">
            <div class="fw-bold" style="font-size:1rem; word-break:break-word;">{{ item.task.name }}</div>
            <div class="small-muted">{{ item.room_name }}</div>
            <div class="mt-1 d-flex gap-1 flex-wrap">
              <span class="badge bg-light text-dark border" style="font-size:.78rem;">{{ item.flabel }}</span>
              <span class="badge {% if p==3 %}bg-danger{% elif p==2 %}bg-warning text-dark{% else %}bg-success{% endif %}">P{{ p }}</span>
            </div>
            <div class="mt-2" style="font-size:.85rem;">
              <span class="text-muted">Ostatnio:</span>
              <strong>{{ item.task.last_done or "nigdy" }}</strong>
            </div>
            <div class="mt-1" style="font-size:.85rem;">
              <span class="text-muted">Następny termin:</span>
              {% if item.is_due %}
                {% if item.overdue_days > 0 %}
                  <span class="text-danger fw-bold">{{ item.next_due }} <small>(zaległy o {{ item.overdue_days }} d)</small></span>
                {% else %}
                  <span class="text-warning fw-bold">{{ item.next_due }} <small>(dziś!)</small></span>
                {% endif %}
              {% else %}
                <span class="text-success">{{ item.next_due }} <small>(za {{ item.days_until }} d)</small></span>
              {% endif %}
            </div>
          </div>
          <form method="post" action="{{ url_for('mark_done', task_id=item.task.id) }}" class="flex-shrink-0">
            <button class="btn btn-{% if item.is_due %}success{% else %}outline-success{% endif %} btn-sm">Zrobione</button>
          </form>
        </div>
      </div>
    </div>
  </div>
  {% endfor %}
</div>
{% else %}
<div class="card p-4 text-center">
  <div class="text-muted">
    Brak zadań okresowych.<br>
    Dodaj zadanie w <a href="/manage">Panelu</a> i wybierz typ <strong>Okresowa</strong>.
  </div>
</div>
{% endif %}
"""
    return render_page(body, tasks=periodic_tasks)


# --- Run ---

if __name__ == "__main__":
    load_data()
    url = f"http://127.0.0.1:{APP_PORT}/"
    try:
        webbrowser.open(url)
    except Exception:
        pass
    app.run(host="127.0.0.1", port=APP_PORT, debug=False)
