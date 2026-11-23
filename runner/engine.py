import hashlib
import random
import shutil
import threading
from contextlib import contextmanager

from .platforms import Adapter, DailyLimitReached, Halt, SkipAccount, Uncertain
from .store import PLATFORMS, validate_account

# Ventana fuera de pantalla para el modo segundo plano: mismo navegador visible que ya validamos, sin robar el foco.
BACKGROUND_WINDOW_ARGS = [
    '--window-position=-32000,-32000',
    '--disable-backgrounding-occluded-windows',
    '--disable-renderer-backgrounding',
]
VIEWPORT = {'width': 1180, 'height': 840}
PLATFORM_LABELS = {'instagram': 'Instagram', 'tiktok': 'TikTok', 'facebook': 'Facebook'}


class Engine:
    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.session_stop = threading.Event()
        self.thread = None
        self.session_thread = None
        self.state = {
            'phase': 'idle',
            'mode': None,
            'platform': None,
            'account': '',
            'current': '',
            'processed': 0,
            'total': 0,
            'message': 'Listo para preparar tu sesión.',
            'sessionOpen': False,
            'batchIndex': 0,
            'batchTotal': 0,
            'batchSource': 'manual',
        }

    def snapshot(self):
        with self.lock:
            return {**self.state, 'events': self.store.events(), 'counts': self.store.counts()}

    def update(self, **values):
        with self.lock:
            self.state.update(values)

    def is_busy(self):
        return bool(self.thread and self.thread.is_alive()) or bool(self.session_thread and self.session_thread.is_alive())

    @contextmanager
    def exclusive(self):
        with self.lock:
            if self.is_busy():
                raise ValueError("Hay una ejecución o sesión abierta. Ciérrala antes de continuar.")
            yield

    def profile(self, platform, account):
        digest = hashlib.sha256(f'{platform}:{account}'.encode()).hexdigest()[:20]
        return self.store.root / 'profiles' / digest

    def has_session(self, platform, account):
        """Comprueba si ya existe un perfil persistente guardado localmente para la red y cuenta."""
        if platform not in PLATFORMS:
            return False
        try:
            normalized = validate_account(account)
        except ValueError:
            return False
        profile_dir = self.profile(platform, normalized)
        return (profile_dir / 'Default').is_dir() or (profile_dir / 'Local State').is_file()

    def delete_session(self, platform, account):
        """Elimina cookies y almacenamiento del perfil local de una cuenta. No toca la cola ni el historial."""
        if platform not in PLATFORMS:
            raise ValueError('Plataforma no válida.')
        account = validate_account(account)
        with self.exclusive():
            profile_dir = self.profile(platform, account).resolve()
            profiles_root = (self.store.root / 'profiles').resolve()
            if not profile_dir.is_relative_to(profiles_root):
                raise ValueError('Ruta de perfil no válida.')
            if not profile_dir.exists():
                return False
            try:
                shutil.rmtree(profile_dir)
            except OSError as exc:
                raise ValueError('No se pudo borrar la sesión. Cierra cualquier ventana de Círculo y vuelve a intentarlo.') from exc
            self.store.log(f'Sesión local de {platform} · {account} borrada de este equipo.')
            return True

    def launch_context(self, pw, platform, account, background):
        """Abre el perfil persistente. En segundo plano la ventana queda fuera de pantalla."""
        return pw.chromium.launch_persistent_context(
            str(self.profile(platform, account)),
            headless=False,
            viewport=VIEWPORT,
            args=BACKGROUND_WINDOW_ARGS if background else [],
        )

    def open_session(self, platform, account):
        if platform not in PLATFORMS:
            raise ValueError('Plataforma no válida.')
        account = validate_account(account)
        with self.exclusive():
            self.session_stop.clear()
            self.update(sessionOpen=True, platform=platform, account=account, phase='session', message='Abriendo navegador para iniciar sesión…')
            self.session_thread = threading.Thread(target=self._session, args=(platform, account), daemon=True)
            self.session_thread.start()

    def _session(self, platform, account):
        try:
            already_saved = self.has_session(platform, account)
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                context = pw.chromium.launch_persistent_context(str(self.profile(platform, account)), headless=False, viewport=VIEWPORT)
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    page.goto(f'https://{PLATFORMS[platform]}/', wait_until='domcontentloaded')
                    self.update(
                        message=(
                            'Comprueba que tu cuenta sigue conectada. Cuando termines, cierra la ventana o pulsa Guardar y cerrar.'
                            if already_saved
                            else 'Inicia sesión en el navegador. Después pulsa Guardar y cerrar aquí.'
                        )
                    )
                    while not self.session_stop.is_set() and context.pages:
                        try:
                            context.pages[0].wait_for_timeout(300)
                        except Exception:
                            # Si el usuario cerró la pestaña o ventana manualmente, terminamos guardando el perfil.
                            if not context.pages:
                                break
                finally:
                    try:
                        context.close()
                    except Exception:
                        pass
            self.store.log(f'Sesión de {platform} · {account} cerrada; el perfil queda guardado localmente.')
            self.update(phase='idle', message='Perfil guardado. La sesión se comprobará al ejecutar.')
        except Exception as exc:
            self.store.log(f'No se pudo abrir la sesión: {exc}', 'error')
            self.update(phase='error', message='No se pudo abrir el navegador. Revisa el registro y ejecuta la instalación.')
        finally:
            self.update(sessionOpen=False)

    def _validate_run_params(self, mode, limit, daily_limit, interval, headless, network_pause=30):
        """Valida los parámetros numéricos y de modo antes de lanzar una sesión o lote."""
        if mode not in {'simulate', 'inspect', 'live'}:
            raise ValueError('Plataforma o modo no válido.')
        if not isinstance(headless, bool):
            raise ValueError('El modo en segundo plano debe ser verdadero o falso.')
        for name, value, low, high in [
            ('Límite de sesión', limit, 1, 500),
            ('Límite diario', daily_limit, 1, 1000),
            ('Intervalo', interval, 5, 3600),
            ('Pausa entre redes', network_pause, 5, 600),
        ]:
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'{name}: escribe un entero entre {low} y {high}.')

    def start(self, platform, account, mode, limit=20, daily_limit=30, interval=45, headless=True):
        if platform not in PLATFORMS:
            raise ValueError('Plataforma o modo no válido.')
        self._validate_run_params(mode, limit, daily_limit, interval, headless)
        account = validate_account(account)
        with self.exclusive():
            rows = [r for r in self.store.rows(platform, account) if r['status'] == 'pending'][:limit]
            if not rows:
                raise ValueError('No hay cuentas pendientes en esta cola. Los resultados dudosos requieren revisión manual.')
            if mode != 'simulate' and any(r['demo'] for r in rows):
                raise ValueError('Esta cola contiene datos de ejemplo. Importa y selecciona tus datos reales antes de usar el navegador.')
            self.stop.clear()
            self.update(
                phase='running',
                mode=mode,
                platform=platform,
                account=account,
                processed=0,
                total=len(rows),
                current='',
                batchIndex=1,
                batchTotal=1,
                batchSource='manual',
                message='Preparando ejecución…',
            )
            self.thread = threading.Thread(
                target=self._run_batch,
                args=([{'platform': platform, 'account': account, 'rows': rows}], mode, daily_limit, interval, headless, 0, 'manual', None, None),
                daemon=True,
            )
            self.thread.start()

    def start_batch(
        self,
        jobs,
        mode,
        limit=20,
        daily_limit=30,
        interval=45,
        headless=True,
        network_pause=30,
        source='scheduled',
        on_job_halt=None,
        on_complete=None,
    ):
        """Inicia una ejecución secuencial sobre varias redes sociales conservando aislamiento por perfil."""
        self._validate_run_params(mode, limit, daily_limit, interval, headless, network_pause)
        if not isinstance(jobs, list) or not jobs:
            raise ValueError('No hay colas elegibles para procesar en el lote.')
        prepared = []
        seen = set()
        for item in jobs:
            platform = item.get('platform')
            if platform not in PLATFORMS:
                raise ValueError(f'Plataforma no válida en lote: {platform}.')
            account = validate_account(item.get('account'))
            if (platform, account) in seen:
                continue
            seen.add((platform, account))
            rows = [r for r in self.store.rows(platform, account) if r['status'] == 'pending'][:limit]
            if not rows:
                continue
            if mode != 'simulate' and any(r['demo'] for r in rows):
                raise ValueError(f'La cola de {PLATFORM_LABELS[platform]} (@{account}) contiene datos de ejemplo.')
            prepared.append({'platform': platform, 'account': account, 'rows': rows})
        if not prepared:
            raise ValueError('No hay cuentas pendientes en las redes seleccionadas.')
        with self.exclusive():
            self.stop.clear()
            first = prepared[0]
            self.update(
                phase='running',
                mode=mode,
                platform=first['platform'],
                account=first['account'],
                processed=0,
                total=len(first['rows']),
                current='',
                batchIndex=1,
                batchTotal=len(prepared),
                batchSource=source,
                message=f"Preparando lote automático ({len(prepared)} {'red' if len(prepared) == 1 else 'redes'})…",
            )
            self.thread = threading.Thread(
                target=self._run_batch,
                args=(prepared, mode, daily_limit, interval, headless, network_pause, source, on_job_halt, on_complete),
                daemon=True,
            )
            self.thread.start()
        return len(prepared)

    def pause(self):
        self.stop.set()
        self.update(message='Pausa solicitada. La acción en curso terminará antes de detenerse.')

    def _execute_single_job(self, job, mode, daily_limit, interval, headless, batch_index, batch_total, source):
        """Procesa secuencialmente las cuentas pendientes de una red y cuenta cerrando Chromium al terminar."""
        platform = job['platform']
        account = job['account']
        rows = job['rows']
        label = PLATFORM_LABELS.get(platform, platform)
        prefix = f'[{batch_index}/{batch_total} · {label}] ' if batch_total > 1 else ''
        context = None
        pw_manager = None
        processed = 0
        done_count = 0
        skipped_count = 0
        try:
            self.update(
                platform=platform,
                account=account,
                processed=0,
                total=len(rows),
                current='',
                batchIndex=batch_index,
                batchTotal=batch_total,
                message=f'{prefix}Preparando ejecución para @{account}…',
            )
            if mode != 'simulate':
                if not self.has_session(platform, account):
                    raise Halt(
                        f'No hay sesión guardada para {label} (@{account}). '
                        'Pulsa «Iniciar sesión (1 vez)» en esa red antes de ejecutar.'
                    )
                if mode == 'live' and self.store.today_attempt_count(platform, account) >= daily_limit:
                    raise DailyLimitReached('Se alcanzó el límite diario de intentos (día UTC).')
                from playwright.sync_api import sync_playwright
                pw_manager = sync_playwright().start()
                context = self.launch_context(pw_manager, platform, account, headless)
                page = context.pages[0] if context.pages else context.new_page()
                verifier = Adapter(page, platform, action='unfollow')
                self.update(message=f'{prefix}Confirmando la cuenta @{account} con sesión abierta…')
                detected = verifier.verify_account(account, strict=(mode == 'live'))
                if detected:
                    self.store.log(f"Sesión verificada · {label} · @{detected} coincide con el perfil local.", 'success')
                else:
                    self.store.log(f'No se pudo leer el usuario de la sesión en {label}; comprobación sin clics continúa.')
            mode_label = f"{mode}{' · segundo plano' if mode != 'simulate' and headless else ''}"
            origin_label = 'programado · ' if source == 'scheduled' else ''
            self.store.log(f"Inicio · {origin_label}{platform} · {account} · modo {mode_label} · {len(rows)} cuentas.")
            for index, row in enumerate(rows):
                if self.stop.is_set():
                    break
                action = row.get('action') or 'unfollow'
                action_verb = 'Quitando de amigos a' if action == 'unfriend' else 'Revisando'
                self.update(current=row['username'], message=f"{prefix}{action_verb} @{row['username']}…")
                if mode == 'simulate':
                    if self.stop.wait(.35):
                        break
                    action_text = 'quitar de amigos' if action == 'unfriend' else 'dejar de seguir'
                    self.store.log(f"Simulación · {label} · @{row['username']} ({action_text}) · no se abrió el perfil ni se hicieron clics.")
                else:
                    adapter = Adapter(page, platform, action=action)
                    try:
                        adapter.visit(row['url'])
                        adapter.inspect()
                    except SkipAccount as exc:
                        if mode == 'live':
                            self.store.set_state(row['id'], 'skipped', str(exc))
                        skipped_count += 1
                        self.store.log(f"Omitida · {label} · @{row['username']} · {exc}")
                        processed = index + 1
                        self.update(processed=processed)
                        if index < len(rows) - 1:
                            if self.stop.wait(min(interval, 8)):
                                break
                        continue
                    if self.stop.is_set():
                        break
                    if mode == 'inspect':
                        control_name = 'Amigos' if action == 'unfriend' else 'Siguiendo'
                        self.store.log(f"Comprobación · {label} · @{row['username']} · control {control_name} encontrado; sin cambios.")
                    else:
                        def reserve():
                            if self.stop.is_set():
                                raise Halt('Pausa solicitada antes del clic.')
                            if not self.store.reserve_attempt(row, daily_limit):
                                raise DailyLimitReached('Se alcanzó el límite diario de intentos (día UTC).')
                        try:
                            adapter.execute(before_click=reserve)
                        except Uncertain as exc:
                            self.store.set_state(row['id'], 'uncertain', str(exc))
                            raise
                        done_count += 1
                        done_detail = (
                            'Se verificó el botón Agregar a amigos después de confirmar.'
                            if action == 'unfriend'
                            else 'Se observó el control Seguir después de confirmar.'
                        )
                        self.store.set_state(row['id'], 'done', done_detail)
                        self.store.log(f"Completado · {label} · @{row['username']} · se verificó el nuevo estado.", 'success')
                processed = index + 1
                self.update(processed=processed)
                if index < len(rows) - 1 and mode != 'simulate':
                    delay = interval + random.uniform(0, interval * .2)
                    self.update(message=f'{prefix}Esperando {round(delay)} s antes del siguiente perfil…')
                    if self.stop.wait(delay):
                        break
            return {'status': 'paused' if self.stop.is_set() else 'complete', 'processed': processed, 'done': done_count, 'skipped': skipped_count, 'detail': ''}
        except DailyLimitReached as exc:
            self.store.log(f'{label} · @{account} · {exc}', 'info')
            return {'status': 'daily_limit', 'processed': processed, 'done': done_count, 'skipped': skipped_count, 'detail': str(exc)}
        except Exception as exc:
            self.store.log(f'{label} · @{account} · {exc}', 'error')
            return {'status': 'error', 'processed': processed, 'done': done_count, 'skipped': skipped_count, 'detail': str(exc)}
        finally:
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            if pw_manager:
                pw_manager.stop()

    def _run_batch(self, jobs, mode, daily_limit, interval, headless, network_pause, source, on_job_halt, on_complete):
        """Coordina una o varias redes secuencialmente aislando errores de seguridad por red."""
        batch_total = len(jobs)
        results = []
        try:
            for index, job in enumerate(jobs):
                if self.stop.is_set():
                    break
                outcome = self._execute_single_job(
                    job,
                    mode,
                    daily_limit,
                    interval,
                    headless,
                    index + 1,
                    batch_total,
                    source,
                )
                results.append({'platform': job['platform'], 'account': job['account'], **outcome})
                if outcome['status'] == 'error' and on_job_halt and not self.stop.is_set():
                    try:
                        on_job_halt(job['platform'], job['account'], outcome['detail'])
                    except Exception:
                        pass
                if self.stop.is_set():
                    break
                if batch_total == 1 and outcome['status'] in {'error', 'daily_limit'}:
                    break
                if index < batch_total - 1 and mode != 'simulate' and network_pause > 0:
                    next_label = PLATFORM_LABELS.get(jobs[index + 1]['platform'], jobs[index + 1]['platform'])
                    self.update(message=f'Pausa de seguridad ({network_pause} s) antes de continuar con {next_label}…')
                    if self.stop.wait(network_pause):
                        break

            paused = self.stop.is_set()
            errors = [r for r in results if r['status'] == 'error']
            daily_limits = [r for r in results if r['status'] == 'daily_limit']
            total_done = sum(r['done'] for r in results)
            total_processed = sum(r['processed'] for r in results)

            if paused:
                phase = 'paused'
                message = 'En pausa. La cola conserva los pendientes.'
            elif batch_total == 1 and errors:
                phase = 'error'
                message = errors[0]['detail'][:300]
            elif batch_total == 1 and daily_limits:
                phase = 'error'
                message = daily_limits[0]['detail'][:300]
            elif batch_total > 1:
                if len(errors) == len(results) and results:
                    phase = 'error'
                    message = f"Lote detenido con errores en todas las redes ({len(errors)}). Revisa Actividad."
                elif errors:
                    phase = 'complete'
                    message = f"Lote multi-red completado parcialmente: {total_processed} perfiles revisados, {len(errors)} red(es) pausadas por seguridad."
                elif mode == 'simulate':
                    phase = 'complete'
                    message = f"Simulación multi-red terminada ({len(results)} redes · {total_processed} cuentas). No se modificó ninguna cuenta."
                else:
                    phase = 'complete'
                    message = f"Lote multi-red terminado ({len(results)} redes · {total_done} completadas)."
            else:
                phase = 'complete'
                message = (
                    'Simulación terminada. No se modificó ninguna cuenta.'
                    if mode == 'simulate'
                    else 'Sesión terminada. Revisa los resultados en el registro.'
                )

            self.update(phase=phase, current='', message=message)
            if on_complete:
                try:
                    on_complete({'phase': phase, 'message': message, 'results': results})
                except Exception:
                    pass
        except Exception as exc:
            self.store.log(str(exc), 'error')
            self.update(phase='error', current='', message=str(exc)[:300])
            if on_complete:
                try:
                    on_complete({'phase': 'error', 'message': str(exc)[:300], 'results': results})
                except Exception:
                    pass

    def shutdown(self):
        self.stop.set()
        self.session_stop.set()
        for worker in [self.thread, self.session_thread]:
            if worker and worker.is_alive():
                worker.join(timeout=3)
