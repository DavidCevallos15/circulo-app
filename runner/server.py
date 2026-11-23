import argparse
import json
import mimetypes
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .engine import Engine
from .instance import InstanceLock
from .paths import cloud_sync_provider, default_data_dir, static_dir
from .scheduler import Scheduler
from .store import Store

STATIC_ROOT = static_dir()


def make_server(port=8765, data=None, os_task_runner=None):
    directory = Path(data) if data else default_data_dir()
    instance_lock = InstanceLock(directory).acquire()
    store = Store(directory)
    engine = Engine(store)
    scheduler = Scheduler(store, engine, os_task_runner=os_task_runner)
    scheduler.start()
    token = secrets.token_urlsafe(32)
    sync_provider = cloud_sync_provider(directory)

    class Handler(BaseHTTPRequestHandler):
        def allowed_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

        def reply(self, status, payload, content_type='application/json; charset=utf-8'):
            body = json.dumps(payload, ensure_ascii=False).encode() if isinstance(payload, (dict, list)) else payload
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.allowed_host():
                return self.reply(403, {'error': 'Host no permitido.'})
            parsed = urlparse(self.path)
            path = parsed.path
            if path == '/api/status':
                return self.reply(200, {
                    **engine.snapshot(),
                    'token': token,
                    'syncProvider': sync_provider,
                    'scheduler': scheduler.snapshot(),
                })
            if path == '/api/schedule':
                return self.reply(200, scheduler.snapshot(refresh_os_task=True))
            if path == '/api/queue':
                return self.reply(200, json.loads(store.export_state()))
            if path == '/api/session':
                query = parse_qs(parsed.query)
                saved = engine.has_session((query.get('platform') or [''])[0], (query.get('account') or [''])[0])
                return self.reply(200, {'saved': saved})
            if path.startswith('/api/'):
                return self.reply(404, {'error': 'Ruta no encontrada.'})
            relative = 'index.html' if path == '/' else path.lstrip('/')
            candidate = (STATIC_ROOT / relative).resolve()
            if not candidate.is_relative_to(STATIC_ROOT.resolve()) or not candidate.is_file():
                return self.reply(404, {'error': 'Archivo no encontrado. Ejecuta npm run build si falta la web.'})
            return self.reply(200, candidate.read_bytes(), mimetypes.guess_type(str(candidate))[0] or 'application/octet-stream')

        def do_POST(self):
            if not self.allowed_host():
                return self.reply(403, {'error': 'Host no permitido.'})
            valid_origin = {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}
            if self.headers.get('Origin') not in valid_origin or self.headers.get('X-Circulo-Token') != token:
                return self.reply(403, {'error': 'Origen o token no válido. Abre la app desde su dirección local.'})
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 5_000_000 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    return self.reply(400, {'error': 'Se espera JSON de hasta 5 MB.'})
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError('El cuerpo debe ser un objeto JSON.')
                path = self.path
                if path == '/api/queue':
                    with engine.exclusive():
                        count = store.replace_pending(
                            payload.get('platform'),
                            payload.get('account'),
                            payload.get('targets'),
                            payload.get('demo', False),
                            payload.get('action', 'unfollow'),
                        )
                    return self.reply(200, {'count': count, 'scheduler': scheduler.snapshot()})
                if path == '/api/queue/clear-finished':
                    with engine.exclusive():
                        removed = store.clear_finished(payload.get('platform'), payload.get('account'))
                    if removed:
                        store.log(f'Cola actualizada · {removed} cuentas terminadas eliminadas de la lista.')
                    return self.reply(200, {'removed': removed, 'scheduler': scheduler.snapshot()})
                if path == '/api/session/open':
                    engine.open_session(payload.get('platform'), payload.get('account'))
                elif path == '/api/session/close':
                    engine.session_stop.set()
                elif path == '/api/session/delete':
                    removed = engine.delete_session(payload.get('platform'), payload.get('account'))
                    return self.reply(200, {'ok': True, 'removed': removed})
                elif path == '/api/run':
                    engine.start(payload.get('platform'), payload.get('account'), payload.get('mode'), payload.get('limit', 20), payload.get('dailyLimit', 30), payload.get('interval', 45), payload.get('headless', True))
                elif path == '/api/pause':
                    engine.pause()
                elif path == '/api/schedule':
                    state = scheduler.configure(payload)
                    return self.reply(200, {'ok': True, 'scheduler': state})
                elif path == '/api/schedule/toggle':
                    if not isinstance(payload.get('enabled'), bool):
                        raise ValueError('Indica si deseas activar o pausar la programación.')
                    state = scheduler.toggle(payload['enabled'])
                    return self.reply(200, {'ok': True, 'scheduler': state})
                elif path == '/api/schedule/run-now':
                    result = scheduler.run_now(mode_override=payload.get('mode'))
                    return self.reply(200, {'ok': True, **result})
                elif path == '/api/schedule/clear-halt':
                    cleared = scheduler.clear_halt(payload.get('platform'), payload.get('account'))
                    return self.reply(200, {'ok': True, 'cleared': cleared, 'scheduler': scheduler.snapshot()})
                else:
                    return self.reply(404, {'error': 'Ruta no encontrada.'})
                self.reply(200, {'ok': True})
            except (ValueError, TypeError, KeyError) as exc:
                self.reply(400, {'error': str(exc)})
            except Exception:
                store.log('Error interno del servidor local.', 'error')
                self.reply(500, {'error': 'Error interno. Revisa el registro local.'})

        def log_message(self, *_):
            pass

    class LocalServer(ThreadingHTTPServer):
        def server_close(self):
            scheduler.stop()
            super().server_close()
            instance_lock.release()

    try:
        server = LocalServer(('127.0.0.1', port), Handler)
    except BaseException:
        scheduler.stop()
        instance_lock.release()
        raise
    server.engine = engine
    server.scheduler = scheduler
    return server


def main():
    parser = argparse.ArgumentParser(description='Círculo · app local')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-open', action='store_true')
    parser.add_argument('--data', type=Path)
    args = parser.parse_args()
    server = make_server(args.port, args.data)
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'Círculo está disponible en {url}', flush=True)
    if not args.no_open:
        threading.Timer(.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nCerrando Círculo…')
    finally:
        server.scheduler.stop()
        server.engine.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
