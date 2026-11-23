"""Programador automático multi-red persistido en SQLite con aislamiento de fallos por red."""
import threading
import time
from datetime import datetime, timedelta, timezone

from .os_scheduler import install_windows_task, is_windows_supported, query_windows_task, remove_windows_task
from .store import PLATFORM_ORDER, now as utc_now, validate_schedule_config

GRACE_WINDOW_SECONDS = 900  # 15 minutos de margen ante demoras de arranque o tareas de Windows.
POLL_INTERVAL_SECONDS = 15
WINDOWS_TASK_CACHE_TTL = 60.0


def _parse_utc(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def compute_next_run(config, reference_now=None):
    """Calcula la próxima marca UTC de ejecución según el horario local configurado."""
    if not config.get('enabled'):
        return ''
    ref_utc = reference_now.astimezone(timezone.utc) if reference_now else datetime.now(timezone.utc)
    kind = config.get('kind', 'daily')

    if kind == 'once':
        target = _parse_utc(config.get('runAt', ''))
        if not target:
            raise ValueError('Elige la fecha y hora exacta para la programación de una sola vez.')
        return target.isoformat()

    if kind == 'daily':
        hour, minute = (int(part) for part in config.get('dailyTime', '22:00').split(':'))
        weekdays = set(config.get('weekdays') or [0, 1, 2, 3, 4, 5, 6])
        local_ref = ref_utc.astimezone()
        for day_offset in range(0, 8):
            candidate_date = local_ref.date() + timedelta(days=day_offset)
            if candidate_date.weekday() not in weekdays:
                continue
            candidate_local = datetime(
                candidate_date.year,
                candidate_date.month,
                candidate_date.day,
                hour,
                minute,
                0,
                tzinfo=local_ref.tzinfo,
            )
            # Re-normaliza la zona horaria local para respetar cambios de horario de verano (DST).
            candidate_local = candidate_local.replace(tzinfo=None).astimezone()
            if candidate_local.astimezone(timezone.utc) > ref_utc:
                return candidate_local.astimezone(timezone.utc).isoformat()
        raise ValueError('No se pudo calcular la próxima fecha diaria.')

    # Intervalo fijo cada N horas.
    hours = int(config.get('intervalHours', 24))
    step = timedelta(hours=hours)
    anchor = _parse_utc(config.get('runAt', ''))
    if anchor and anchor > ref_utc:
        return anchor.isoformat()
    if anchor:
        elapsed = ref_utc - anchor
        jumps = int(elapsed.total_seconds() // step.total_seconds()) + 1
        return (anchor + step * jumps).isoformat()
    return (ref_utc + step).isoformat()


def resolve_eligible_queues(store, engine, config):
    """Devuelve colas elegibles y descartadas para la configuración actual del programador."""
    summaries = store.queue_summaries()
    allowed = set(PLATFORM_ORDER if config.get('allNetworks', True) else config.get('platforms', []))
    mode = config.get('mode', 'live')
    daily_limit = int(config.get('dailyLimit', 30))

    enriched = []
    eligible = []
    for item in summaries:
        session_saved = engine.has_session(item['platform'], item['account'])
        included = item['platform'] in allowed
        skip_reason = ''
        if not included:
            skip_reason = 'Red excluida en la programación.'
        elif item['pending'] <= 0:
            skip_reason = 'Sin cuentas pendientes.'
        elif item['halted']:
            skip_reason = f"Pausada por seguridad: {item['haltReason']}"
        elif mode != 'simulate' and item['demo']:
            skip_reason = 'Contiene datos de ejemplo.'
        elif mode != 'simulate' and not session_saved:
            skip_reason = 'Falta iniciar sesión una vez en esta red.'
        elif mode == 'live' and item['attemptsToday'] >= daily_limit:
            skip_reason = 'Cupo diario UTC ya alcanzado hoy.'

        entry = {
            **item,
            'sessionSaved': session_saved,
            'included': included,
            'eligible': included and item['pending'] > 0 and not skip_reason,
            'skipReason': skip_reason,
        }
        enriched.append(entry)
        if entry['eligible']:
            eligible.append(entry)
    return eligible, enriched


class Scheduler:
    """Orquestador en segundo plano que dispara colas multi-red sin requerir una pestaña abierta."""

    def __init__(self, store, engine, poll_seconds=POLL_INTERVAL_SECONDS, os_task_runner=None):
        self.store = store
        self.engine = engine
        self.poll_seconds = poll_seconds
        self.os_task_runner = os_task_runner
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._busy_logged = False
        self._win_task_cache = None
        self._win_task_checked_at = 0.0

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()
        worker = self._thread
        if worker and worker.is_alive():
            worker.join(timeout=2)

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as exc:
                self.store.log(f'Error en el comprobador de programación: {exc}', 'error')
            self._stop.wait(self.poll_seconds)

    def _get_windows_task_info(self, force_refresh=False):
        """Consulta el estado de la tarea de Windows con caché para evitar procesos repetidos durante el polling."""
        now_mono = time.monotonic()
        if not force_refresh and self._win_task_cache is not None and (now_mono - self._win_task_checked_at) < WINDOWS_TASK_CACHE_TTL:
            return self._win_task_cache
        kwargs = {'runner': self.os_task_runner} if self.os_task_runner else {}
        self._win_task_cache = query_windows_task(**kwargs)
        self._win_task_checked_at = now_mono
        return self._win_task_cache

    def _sync_windows_task(self, config, next_run_at, had_windows_task=False):
        """Sincroniza la tarea nativa de Windows solo cuando se activa o debe limpiarse una tarea existente."""
        if not is_windows_supported():
            return
        kwargs = {'runner': self.os_task_runner} if self.os_task_runner else {}
        if config.get('enabled') and config.get('windowsTask') and next_run_at:
            install_windows_task(config, next_run_at, self.store.root, **kwargs)
            self._win_task_cache = None
            return
        if had_windows_task or (self._win_task_cache and self._win_task_cache.get('registered')):
            remove_windows_task(**kwargs)
            self._win_task_cache = None

    def snapshot(self, refresh_os_task=False):
        with self._lock:
            config = self.store.get_schedule()
            eligible, queues = resolve_eligible_queues(self.store, self.engine, config)
            win_info = self._get_windows_task_info(force_refresh=refresh_os_task)
            return {
                'config': config,
                'queues': queues,
                'eligibleCount': len(eligible),
                'totalPendingEligible': sum(q['pending'] for q in eligible),
                'windowsTask': win_info,
                'serverNow': utc_now(),
            }

    def configure(self, payload, reference_now=None):
        """Valida, persiste y arma (o desarma) la programación automática."""
        with self._lock:
            validated = validate_schedule_config(payload)
            ref_utc = reference_now.astimezone(timezone.utc) if reference_now else datetime.now(timezone.utc)
            if validated['enabled'] and validated['kind'] == 'once':
                target = _parse_utc(validated['runAt'])
                if not target or target <= ref_utc:
                    raise ValueError('La fecha y hora elegida ya pasó. Selecciona un horario futuro.')
            if validated['windowsTask'] and not is_windows_supported():
                raise ValueError('La tarea en segundo plano con la app cerrada solo está disponible en Windows.')

            previous = self.store.get_schedule()
            next_run = compute_next_run(validated, ref_utc) if validated['enabled'] else ''
            saved = self.store.save_schedule(validated, next_run_at=next_run)
            if validated['enabled']:
                eligible, _ = resolve_eligible_queues(self.store, self.engine, saved)
                if validated['mode'] != 'simulate' and not eligible:
                    # Permitimos guardar, pero advertimos en el registro si aún faltan sesiones o colas.
                    self.store.log('Programación activada sin colas listas todavía; guarda colas y sesiones antes de la hora elegida.')
            self._sync_windows_task(saved, next_run, had_windows_task=previous.get('windowsTask', False))
            if saved['enabled']:
                self.store.log(f"Programación activada · modo {saved['mode']} · próxima ejecución {next_run}.")
            else:
                self.store.log('Programación automática desactivada.')
            return self.snapshot()

    def toggle(self, enabled, reference_now=None):
        """Activa o pausa rápidamente la programación conservando el horario guardado."""
        with self._lock:
            current = self.store.get_schedule()
            current['enabled'] = bool(enabled)
            return self.configure(current, reference_now=reference_now)

    def clear_halt(self, platform, account):
        with self._lock:
            removed = self.store.clear_schedule_halt(platform, account)
            if removed:
                self.store.log(f'Bloqueo de programación limpiado para {platform} · @{account}.')
            return removed

    def _on_job_halt(self, platform, account, reason):
        self.store.set_schedule_halt(platform, account, reason)
        self.store.log(f'Red pausada automáticamente ({platform} · @{account}): {reason}', 'error')

    def _on_batch_complete(self, outcome):
        phase = outcome.get('phase', 'complete')
        message = outcome.get('message', '')
        self.store.update_schedule_runtime(
            last_run_at=utc_now(),
            last_status=phase,
            last_summary=message,
        )

    def run_now(self, mode_override=None):
        """Lanza de inmediato el lote multi-red con las colas elegibles actuales."""
        with self._lock:
            config = self.store.get_schedule()
            if mode_override:
                config = {**config, 'mode': mode_override}
            eligible, _ = resolve_eligible_queues(self.store, self.engine, config)
            if not eligible:
                raise ValueError('No hay colas listas para ejecutar. Guarda al menos una cola pendiente y comprueba su sesión.')
            jobs = [{'platform': q['platform'], 'account': q['account']} for q in eligible]
            started = self.engine.start_batch(
                jobs=jobs,
                mode=config['mode'],
                limit=config['limit'],
                daily_limit=config['dailyLimit'],
                interval=config['interval'],
                headless=config['headless'],
                network_pause=config['networkPause'],
                source='manual',
                on_job_halt=self._on_job_halt,
                on_complete=self._on_batch_complete,
            )
            return {'started': started, 'jobs': jobs}

    def tick(self, reference_now=None):
        """Evalúa si corresponde disparar una ejecución programada. Seguro para pruebas unitarias."""
        with self._lock:
            config = self.store.get_schedule()
            if not config.get('enabled'):
                return 'disabled'
            ref_utc = reference_now.astimezone(timezone.utc) if reference_now else datetime.now(timezone.utc)
            next_run = _parse_utc(config.get('nextRunAt', ''))
            if not next_run:
                recalculated = compute_next_run(config, ref_utc)
                self.store.update_schedule_runtime(next_run_at=recalculated)
                return 'recalculated'
            if ref_utc < next_run:
                self._busy_logged = False
                return 'waiting'

            overdue_seconds = (ref_utc - next_run).total_seconds()
            if overdue_seconds > GRACE_WINDOW_SECONDS:
                if config['kind'] == 'once':
                    summary = 'La hora programada pasó mientras la app estaba cerrada. Reprograma si aún deseas ejecutarla.'
                    self.store.update_schedule_runtime(
                        enabled=False,
                        next_run_at='',
                        last_status='missed',
                        last_summary=summary,
                    )
                    self._sync_windows_task({**config, 'enabled': False}, '', had_windows_task=config.get('windowsTask', False))
                    self.store.log(summary, 'info')
                    return 'missed'
                next_future = compute_next_run(config, ref_utc)
                summary = 'Ejecución programada omitida por superar el margen de 15 min; reprogramada al siguiente horario.'
                self.store.update_schedule_runtime(
                    next_run_at=next_future,
                    last_status='missed',
                    last_summary=summary,
                )
                self._sync_windows_task(config, next_future, had_windows_task=config.get('windowsTask', False))
                self.store.log(summary, 'info')
                return 'rescheduled'

            if self.engine.is_busy():
                if not self._busy_logged:
                    self.store.log('Ejecución programada en espera: hay otra operación o sesión abierta.')
                    self._busy_logged = True
                return 'busy'

            self._busy_logged = False
            eligible, queues = resolve_eligible_queues(self.store, self.engine, config)

            # Avanzamos la programación antes de iniciar para impedir disparos duplicados.
            if config['kind'] == 'once':
                next_future = ''
                next_enabled = False
            else:
                next_future = compute_next_run(config, ref_utc + timedelta(seconds=1))
                next_enabled = True

            self.store.update_schedule_runtime(
                enabled=next_enabled,
                next_run_at=next_future,
                last_run_at=ref_utc.isoformat(),
                last_status='running' if eligible else 'skipped',
                last_summary=(
                    f"Iniciando lote programado en {len(eligible)} {'red' if len(eligible) == 1 else 'redes'}…"
                    if eligible
                    else 'Sin colas listas al llegar la hora programada.'
                ),
            )
            updated_config = {**config, 'enabled': next_enabled}
            try:
                self._sync_windows_task(updated_config, next_future, had_windows_task=config.get('windowsTask', False))
            except Exception as exc:
                self.store.log(f'Aviso al actualizar la tarea de Windows: {exc}', 'error')

            if not eligible:
                missing_sessions = [q for q in queues if q['included'] and q['pending'] > 0 and not q['sessionSaved']]
                if missing_sessions:
                    names = ', '.join(f"{q['platform']} (@{q['account']})" for q in missing_sessions)
                    self.store.log(f'Ejecución programada omitida: falta sesión guardada en {names}.', 'error')
                else:
                    self.store.log('Ejecución programada omitida: no había colas pendientes elegibles.')
                return 'no_jobs'

            jobs = [{'platform': q['platform'], 'account': q['account']} for q in eligible]
            self.engine.start_batch(
                jobs=jobs,
                mode=config['mode'],
                limit=config['limit'],
                daily_limit=config['dailyLimit'],
                interval=config['interval'],
                headless=config['headless'],
                network_pause=config['networkPause'],
                source='scheduled',
                on_job_halt=self._on_job_halt,
                on_complete=self._on_batch_complete,
            )
            return 'started'
