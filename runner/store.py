import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PLATFORMS = {"instagram": "www.instagram.com", "tiktok": "www.tiktok.com", "facebook": "www.facebook.com"}
PLATFORM_ORDER = ("instagram", "tiktok", "facebook")
PLATFORM_ACTIONS = {
    "instagram": {"unfollow"},
    "tiktok": {"unfollow"},
    "facebook": {"unfollow", "unfriend"},
}
SCHEDULE_KINDS = {"once", "daily", "interval"}
SCHEDULE_MODES = {"simulate", "inspect", "live"}


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_action(platform, action="unfollow"):
    """Valida que la acción solicitada esté permitida para la red social indicada."""
    if platform not in PLATFORMS:
        raise ValueError("Plataforma no válida.")
    normalized = "unfollow" if action is None else str(action).strip().lower()
    if normalized not in PLATFORM_ACTIONS[platform]:
        raise ValueError(f"La acción «{normalized}» no está disponible para {platform}.")
    return normalized


def validate_account(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", value.strip().lstrip("@")):
        raise ValueError("Escribe un identificador de cuenta válido, sin espacios.")
    return value.strip().lstrip("@").lower()


def validate_schedule_config(payload):
    """Valida y normaliza la configuración de programación automática multi-red."""
    if not isinstance(payload, dict):
        raise ValueError("La programación debe ser un objeto JSON.")
    enabled = payload.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError("El estado activo de la programación debe ser verdadero o falso.")
    kind = str(payload.get("kind", "daily")).strip().lower()
    if kind not in SCHEDULE_KINDS:
        raise ValueError("Tipo de programación no válido. Usa una vez, diario o intervalo.")
    mode = str(payload.get("mode", "live")).strip().lower()
    if mode not in SCHEDULE_MODES:
        raise ValueError("Modo de ejecución programada no válido.")

    run_at = str(payload.get("runAt", "") or "").strip()
    if run_at:
        try:
            parsed_run_at = datetime.fromisoformat(run_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("La fecha y hora programada no tiene un formato ISO válido.") from exc
        if parsed_run_at.tzinfo is None:
            parsed_run_at = parsed_run_at.astimezone()
        run_at = parsed_run_at.astimezone(timezone.utc).isoformat()
    elif kind == "once" and enabled:
        raise ValueError("Elige la fecha y hora exacta para la ejecución programada.")

    daily_time = str(payload.get("dailyTime", "22:00") or "22:00").strip()
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", daily_time):
        raise ValueError("La hora diaria debe tener formato HH:MM (24 horas).")

    raw_weekdays = payload.get("weekdays", [0, 1, 2, 3, 4, 5, 6])
    if not isinstance(raw_weekdays, list) or not raw_weekdays:
        raise ValueError("Selecciona al menos un día de la semana.")
    weekdays = []
    for day in raw_weekdays:
        if type(day) is not int or not 0 <= day <= 6:
            raise ValueError("Los días de la semana deben ser enteros entre 0 (lunes) y 6 (domingo).")
        if day not in weekdays:
            weekdays.append(day)
    weekdays.sort()

    interval_hours = payload.get("intervalHours", 24)
    if type(interval_hours) is not int or not 1 <= interval_hours <= 168:
        raise ValueError("El intervalo en horas debe ser un entero entre 1 y 168.")

    all_networks = payload.get("allNetworks", True)
    if not isinstance(all_networks, bool):
        raise ValueError("La opción de todas las redes debe ser verdadera o falsa.")

    raw_platforms = payload.get("platforms", list(PLATFORM_ORDER))
    if not isinstance(raw_platforms, list):
        raise ValueError("Las redes seleccionadas deben ser una lista.")
    platforms = []
    for item in raw_platforms:
        name = str(item).strip().lower()
        if name not in PLATFORMS:
            raise ValueError(f"Red no válida en la programación: {name}.")
        if name not in platforms:
            platforms.append(name)
    if not all_networks and not platforms:
        raise ValueError("Selecciona al menos una red social o activa todas las redes.")

    for label, key, default, low, high in [
        ("Límite por sesión", "limit", 20, 1, 500),
        ("Límite diario", "dailyLimit", 30, 1, 1000),
        ("Espera entre perfiles", "interval", 45, 5, 3600),
        ("Pausa entre redes", "networkPause", 30, 5, 600),
    ]:
        value = payload.get(key, default)
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{label}: escribe un entero entre {low} y {high}.")

    headless = payload.get("headless", True)
    if not isinstance(headless, bool):
        raise ValueError("El modo en segundo plano debe ser verdadero o falso.")
    windows_task = payload.get("windowsTask", False)
    if not isinstance(windows_task, bool):
        raise ValueError("La opción de tarea de Windows debe ser verdadera o falsa.")

    return {
        "enabled": enabled,
        "kind": kind,
        "mode": mode,
        "runAt": run_at,
        "dailyTime": daily_time,
        "weekdays": weekdays,
        "intervalHours": interval_hours,
        "allNetworks": all_networks,
        "platforms": platforms or list(PLATFORM_ORDER),
        "limit": payload.get("limit", 20),
        "dailyLimit": payload.get("dailyLimit", 30),
        "interval": payload.get("interval", 45),
        "networkPause": payload.get("networkPause", 30),
        "headless": headless,
        "windowsTask": windows_task,
    }


def validate_target(target, platform):
    if not isinstance(target, dict):
        raise ValueError("Cada cuenta debe ser un objeto.")
    username = validate_account(target.get("username"))
    url = target.get("profileUrl", "")
    if not isinstance(url, str):
        raise ValueError("La URL del perfil debe ser texto.")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {PLATFORMS[platform], PLATFORMS[platform].removeprefix("www.")} or parsed.username or parsed.password or parsed.port:
        raise ValueError("La URL debe pertenecer a la plataforma seleccionada y usar HTTPS.")
    segments = [s for s in parsed.path.split("/") if s]
    if platform == "facebook" and parsed.path == "/profile.php":
        if parse_qs(parsed.query) != {"id": [username]} or not username.isdigit():
            raise ValueError("El identificador de Facebook no coincide con la URL.")
        canonical = f"https://{PLATFORMS[platform]}/profile.php?id={username}"
    else:
        if len(segments) != 1 or segments[0].removeprefix("@").lower() != username:
            raise ValueError("El usuario no coincide con la URL del perfil.")
        if username in {"accounts", "explore", "reels", "stories", "login", "settings", "home", "watch", "groups", "friends"}:
            raise ValueError("La URL no representa un perfil individual.")
        canonical = f"https://{PLATFORMS[platform]}/{'@' if platform == 'tiktok' else ''}{username}/"
    return {"username": username, "profileUrl": canonical}


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "queue.sqlite3"
        with self.db() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS targets (
                    id INTEGER PRIMARY KEY, platform TEXT NOT NULL, account TEXT NOT NULL,
                    username TEXT NOT NULL, url TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
                    detail TEXT NOT NULL DEFAULT '', updated TEXT NOT NULL, demo INTEGER NOT NULL DEFAULT 0,
                    action TEXT NOT NULL DEFAULT 'unfollow',
                    UNIQUE(platform, account, username));
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY, platform TEXT, account TEXT, username TEXT, started TEXT);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, at TEXT, level TEXT, message TEXT);
                CREATE TABLE IF NOT EXISTS schedule_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    enabled INTEGER NOT NULL DEFAULT 0,
                    kind TEXT NOT NULL DEFAULT 'daily',
                    mode TEXT NOT NULL DEFAULT 'live',
                    run_at TEXT NOT NULL DEFAULT '',
                    daily_time TEXT NOT NULL DEFAULT '22:00',
                    weekdays TEXT NOT NULL DEFAULT '[0,1,2,3,4,5,6]',
                    interval_hours INTEGER NOT NULL DEFAULT 24,
                    all_networks INTEGER NOT NULL DEFAULT 1,
                    platforms TEXT NOT NULL DEFAULT '["instagram","tiktok","facebook"]',
                    session_limit INTEGER NOT NULL DEFAULT 20,
                    daily_limit INTEGER NOT NULL DEFAULT 30,
                    interval_seconds INTEGER NOT NULL DEFAULT 45,
                    network_pause INTEGER NOT NULL DEFAULT 30,
                    headless INTEGER NOT NULL DEFAULT 1,
                    windows_task INTEGER NOT NULL DEFAULT 0,
                    next_run_at TEXT NOT NULL DEFAULT '',
                    last_run_at TEXT NOT NULL DEFAULT '',
                    last_status TEXT NOT NULL DEFAULT 'idle',
                    last_summary TEXT NOT NULL DEFAULT '',
                    updated TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS schedule_halts (
                    platform TEXT NOT NULL,
                    account TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    halted_at TEXT NOT NULL,
                    PRIMARY KEY (platform, account)
                );
            """)
            columns = {r[1] for r in db.execute('PRAGMA table_info(targets)')}
            if 'demo' not in columns:
                db.execute('ALTER TABLE targets ADD COLUMN demo INTEGER NOT NULL DEFAULT 0')
            if 'action' not in columns:
                db.execute("ALTER TABLE targets ADD COLUMN action TEXT NOT NULL DEFAULT 'unfollow'")
            # Una interrupción después del clic nunca puede reintentarse automáticamente.
            db.execute("UPDATE targets SET status='uncertain',detail='Ejecución interrumpida. Revisa el perfil manualmente.' WHERE status='acting'")

    @contextmanager
    def db(self):
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    def replace_pending(self, platform, account, targets, demo=False, action="unfollow"):
        if platform not in PLATFORMS:
            raise ValueError("Plataforma no válida.")
        account = validate_account(account)
        normalized_action = validate_action(platform, action)
        if not isinstance(targets, list) or not 1 <= len(targets) <= 10000:
            raise ValueError("Selecciona entre 1 y 10.000 cuentas.")
        validated = {p['username']: p for p in (validate_target(t, platform) for t in targets)}
        with self.db() as db:
            db.execute("DELETE FROM targets WHERE platform=? AND account=? AND status='pending'", (platform, account))
            for t in validated.values():
                db.execute(
                    "INSERT INTO targets(platform,account,username,url,updated,demo,action) VALUES(?,?,?,?,?,?,?) "
                    "ON CONFLICT(platform,account,username) DO UPDATE SET url=excluded.url, updated=excluded.updated",
                    (platform, account, t['username'], t['profileUrl'], now(), int(bool(demo)), normalized_action),
                )
        return len(validated)

    def rows(self, platform, account):
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM targets WHERE platform=? AND account=? ORDER BY id", (platform, account))]

    def set_state(self, target_id, status, detail=""):
        with self.db() as db:
            db.execute("UPDATE targets SET status=?,detail=?,updated=? WHERE id=?", (status, detail, now(), target_id))

    def today_attempt_count(self, platform, account):
        """Devuelve cuántos intentos se iniciaron hoy (día UTC) para una red y cuenta."""
        date = datetime.now(timezone.utc).date().isoformat()
        with self.db() as db:
            return db.execute(
                "SELECT COUNT(*) FROM attempts WHERE platform=? AND account=? AND substr(started,1,10)=?",
                (platform, account, date),
            ).fetchone()[0]

    def reserve_attempt(self, row, daily_limit):
        date = datetime.now(timezone.utc).date().isoformat()
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute("SELECT COUNT(*) FROM attempts WHERE platform=? AND account=? AND substr(started,1,10)=?", (row['platform'], row['account'], date)).fetchone()[0]
            if count >= daily_limit:
                return False
            db.execute("INSERT INTO attempts(platform,account,username,started) VALUES(?,?,?,?)", (row['platform'], row['account'], row['username'], now()))
            db.execute("UPDATE targets SET status='acting',updated=? WHERE id=? AND status='pending'", (now(), row['id']))
            return True

    def log(self, message, level="info"):
        with self.db() as db:
            db.execute("INSERT INTO events(at,level,message) VALUES(?,?,?)", (now(), level, str(message)[:600]))

    def events(self):
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM events ORDER BY id DESC LIMIT 60")]

    def counts(self):
        with self.db() as db:
            return dict((r[0], r[1]) for r in db.execute("SELECT status,COUNT(*) FROM targets GROUP BY status"))

    def queue_summaries(self):
        """Resume todas las colas persistidas agrupadas por red y cuenta, incluyendo bloqueos de seguridad."""
        date = datetime.now(timezone.utc).date().isoformat()
        with self.db() as db:
            halts = {
                (r['platform'], r['account']): {'reason': r['reason'], 'haltedAt': r['halted_at']}
                for r in db.execute("SELECT platform, account, reason, halted_at FROM schedule_halts")
            }
            attempts_today = {
                (r['platform'], r['account']): r['cnt']
                for r in db.execute(
                    "SELECT platform, account, COUNT(*) AS cnt FROM attempts WHERE substr(started,1,10)=? GROUP BY platform, account",
                    (date,),
                )
            }
            rows = db.execute(
                """
                SELECT
                    platform,
                    account,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending,
                    SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done,
                    SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) AS skipped,
                    SUM(CASE WHEN status = 'uncertain' THEN 1 ELSE 0 END) AS uncertain,
                    MAX(CASE WHEN status = 'pending' THEN demo ELSE 0 END) AS pending_demo
                FROM targets
                GROUP BY platform, account
                """
            ).fetchall()
            action_rows = db.execute(
                "SELECT DISTINCT platform, account, action FROM targets WHERE status = 'pending'"
            ).fetchall()
        actions_map = {}
        for row in action_rows:
            actions_map.setdefault((row['platform'], row['account']), []).append(row['action'] or 'unfollow')

        order_index = {name: idx for idx, name in enumerate(PLATFORM_ORDER)}
        summaries = []
        for row in rows:
            key = (row['platform'], row['account'])
            halt = halts.get(key)
            summaries.append({
                'platform': row['platform'],
                'account': row['account'],
                'pending': int(row['pending'] or 0),
                'done': int(row['done'] or 0),
                'skipped': int(row['skipped'] or 0),
                'uncertain': int(row['uncertain'] or 0),
                'demo': bool(row['pending_demo']),
                'actions': sorted(actions_map.get(key) or ['unfollow']),
                'attemptsToday': int(attempts_today.get(key, 0)),
                'halted': bool(halt),
                'haltReason': halt['reason'] if halt else '',
                'haltedAt': halt['haltedAt'] if halt else '',
            })
        summaries.sort(key=lambda item: (order_index.get(item['platform'], 99), item['account']))
        return summaries

    def get_schedule(self):
        """Lee la configuración de programación automática o devuelve los valores seguros por defecto."""
        with self.db() as db:
            row = db.execute("SELECT * FROM schedule_config WHERE id = 1").fetchone()
        if not row:
            return {
                'enabled': False,
                'kind': 'daily',
                'mode': 'live',
                'runAt': '',
                'dailyTime': '22:00',
                'weekdays': [0, 1, 2, 3, 4, 5, 6],
                'intervalHours': 24,
                'allNetworks': True,
                'platforms': list(PLATFORM_ORDER),
                'limit': 20,
                'dailyLimit': 30,
                'interval': 45,
                'networkPause': 30,
                'headless': True,
                'windowsTask': False,
                'nextRunAt': '',
                'lastRunAt': '',
                'lastStatus': 'idle',
                'lastSummary': '',
                'updated': '',
            }
        return {
            'enabled': bool(row['enabled']),
            'kind': row['kind'],
            'mode': row['mode'],
            'runAt': row['run_at'],
            'dailyTime': row['daily_time'],
            'weekdays': json.loads(row['weekdays'] or '[0,1,2,3,4,5,6]'),
            'intervalHours': int(row['interval_hours']),
            'allNetworks': bool(row['all_networks']),
            'platforms': json.loads(row['platforms'] or '["instagram","tiktok","facebook"]'),
            'limit': int(row['session_limit']),
            'dailyLimit': int(row['daily_limit']),
            'interval': int(row['interval_seconds']),
            'networkPause': int(row['network_pause']),
            'headless': bool(row['headless']),
            'windowsTask': bool(row['windows_task']),
            'nextRunAt': row['next_run_at'],
            'lastRunAt': row['last_run_at'],
            'lastStatus': row['last_status'],
            'lastSummary': row['last_summary'],
            'updated': row['updated'],
        }

    def save_schedule(self, config, next_run_at=""):
        """Guarda la configuración validada del programador automático en SQLite."""
        validated = validate_schedule_config(config)
        current = self.get_schedule()
        timestamp = now()
        with self.db() as db:
            db.execute(
                """
                INSERT INTO schedule_config(
                    id, enabled, kind, mode, run_at, daily_time, weekdays, interval_hours,
                    all_networks, platforms, session_limit, daily_limit, interval_seconds,
                    network_pause, headless, windows_task, next_run_at, last_run_at,
                    last_status, last_summary, updated
                ) VALUES(1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    enabled=excluded.enabled,
                    kind=excluded.kind,
                    mode=excluded.mode,
                    run_at=excluded.run_at,
                    daily_time=excluded.daily_time,
                    weekdays=excluded.weekdays,
                    interval_hours=excluded.interval_hours,
                    all_networks=excluded.all_networks,
                    platforms=excluded.platforms,
                    session_limit=excluded.session_limit,
                    daily_limit=excluded.daily_limit,
                    interval_seconds=excluded.interval_seconds,
                    network_pause=excluded.network_pause,
                    headless=excluded.headless,
                    windows_task=excluded.windows_task,
                    next_run_at=excluded.next_run_at,
                    updated=excluded.updated
                """,
                (
                    int(validated['enabled']),
                    validated['kind'],
                    validated['mode'],
                    validated['runAt'],
                    validated['dailyTime'],
                    json.dumps(validated['weekdays']),
                    validated['intervalHours'],
                    int(validated['allNetworks']),
                    json.dumps(validated['platforms']),
                    validated['limit'],
                    validated['dailyLimit'],
                    validated['interval'],
                    validated['networkPause'],
                    int(validated['headless']),
                    int(validated['windowsTask']),
                    next_run_at,
                    current['lastRunAt'],
                    current['lastStatus'],
                    current['lastSummary'],
                    timestamp,
                ),
            )
        return self.get_schedule()

    def update_schedule_runtime(self, next_run_at=None, last_run_at=None, last_status=None, last_summary=None, enabled=None):
        """Actualiza el estado operativo de la programación tras una ejecución o reprogramación."""
        current = self.get_schedule()
        fields = {
            'next_run_at': current['nextRunAt'] if next_run_at is None else next_run_at,
            'last_run_at': current['lastRunAt'] if last_run_at is None else last_run_at,
            'last_status': current['lastStatus'] if last_status is None else last_status,
            'last_summary': current['lastSummary'] if last_summary is None else str(last_summary)[:400],
            'enabled': int(current['enabled']) if enabled is None else int(bool(enabled)),
            'updated': now(),
        }
        with self.db() as db:
            exists = db.execute("SELECT 1 FROM schedule_config WHERE id = 1").fetchone()
            if not exists:
                self.save_schedule(current, next_run_at=fields['next_run_at'])
            db.execute(
                """
                UPDATE schedule_config
                SET next_run_at=?, last_run_at=?, last_status=?, last_summary=?, enabled=?, updated=?
                WHERE id = 1
                """,
                (
                    fields['next_run_at'],
                    fields['last_run_at'],
                    fields['last_status'],
                    fields['last_summary'],
                    fields['enabled'],
                    fields['updated'],
                ),
            )
        return self.get_schedule()

    def set_schedule_halt(self, platform, account, reason):
        """Pausa automáticamente una red y cuenta tras un captcha, login o error ambiguo."""
        if platform not in PLATFORMS:
            raise ValueError("Plataforma no válida.")
        account = validate_account(account)
        with self.db() as db:
            db.execute(
                """
                INSERT INTO schedule_halts(platform, account, reason, halted_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(platform, account) DO UPDATE SET
                    reason=excluded.reason,
                    halted_at=excluded.halted_at
                """,
                (platform, account, str(reason)[:300], now()),
            )

    def clear_schedule_halt(self, platform, account):
        """Reactiva una red y cuenta previamente pausada por seguridad."""
        if platform not in PLATFORMS:
            raise ValueError("Plataforma no válida.")
        account = validate_account(account)
        with self.db() as db:
            cursor = db.execute(
                "DELETE FROM schedule_halts WHERE platform=? AND account=?",
                (platform, account),
            )
            return cursor.rowcount > 0

    def list_schedule_halts(self):
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT platform, account, reason, halted_at FROM schedule_halts ORDER BY halted_at DESC")]

    def clear_finished(self, platform, account):
        """Elimina de la cola las cuentas completadas u omitidas conservando pendientes, dudosas y el límite diario."""
        if platform not in PLATFORMS:
            raise ValueError("Plataforma no válida.")
        account = validate_account(account)
        with self.db() as db:
            cursor = db.execute(
                "DELETE FROM targets WHERE platform=? AND account=? AND status IN ('done', 'skipped')",
                (platform, account),
            )
            return cursor.rowcount

    def export_state(self):
        with self.db() as db:
            return json.dumps([dict(r) for r in db.execute("SELECT * FROM targets ORDER BY id")], ensure_ascii=False, indent=2)
