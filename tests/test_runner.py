import json
import tempfile
import threading
import time
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from runner.cli import run_scheduled_once
from runner.engine import Engine
from runner.instance import InstanceLock
from runner.os_scheduler import TASK_NAME, build_task_xml, install_windows_task, query_windows_task, remove_windows_task
from runner.paths import cloud_sync_provider
from runner.scheduler import GRACE_WINDOW_SECONDS, Scheduler, compute_next_run
from runner.server import make_server
from runner.store import Store, validate_target

TARGET = {'username': 'alice', 'profileUrl': 'https://www.instagram.com/alice/'}


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_completed_and_uncertain_are_never_reset_by_import(self):
        self.store.replace_pending('instagram', 'me', [TARGET])
        row = self.store.rows('instagram', 'me')[0]
        self.store.set_state(row['id'], 'done')
        self.store.replace_pending('instagram', 'me', [TARGET])
        self.assertEqual(self.store.rows('instagram', 'me')[0]['status'], 'done')

    def test_unknown_after_crash_and_daily_attempts_persist(self):
        self.store.replace_pending('instagram', 'me', [TARGET])
        row = self.store.rows('instagram', 'me')[0]
        self.assertTrue(self.store.reserve_attempt(row, 1))
        self.assertFalse(self.store.reserve_attempt(row, 1))
        recovered = Store(self.tmp.name)
        self.assertEqual(recovered.rows('instagram', 'me')[0]['status'], 'uncertain')
        self.store.replace_pending('instagram', 'other', [TARGET])
        self.assertTrue(self.store.reserve_attempt(self.store.rows('instagram', 'other')[0], 1))

    def test_invalid_import_is_atomic(self):
        self.store.replace_pending('instagram', 'me', [TARGET])
        with self.assertRaises(ValueError):
            self.store.replace_pending('instagram', 'me', [{'username': 'bob', 'profileUrl': 'https://evil.test/bob'}])
        self.assertEqual(len(self.store.rows('instagram', 'me')), 1)
        for url in ['https://www.instagram.com/bob/', 'http://www.instagram.com/alice/', 'https://www.instagram.com:123/alice/']:
            with self.assertRaises(ValueError):
                validate_target({**TARGET, 'profileUrl': url}, 'instagram')

    def test_simulation_does_not_consume_queue_and_demo_is_blocked_in_browser_modes(self):
        self.store.replace_pending('instagram', 'me', [TARGET], demo=True)
        engine = Engine(self.store)
        for mode in ['live', 'inspect']:
            with self.assertRaises(ValueError):
                engine.start('instagram', 'me', mode)
        engine.start('instagram', 'me', 'simulate')
        engine.thread.join(timeout=5)
        self.assertEqual(engine.snapshot()['phase'], 'complete')
        self.assertEqual(self.store.rows('instagram', 'me')[0]['status'], 'pending')

    def test_pause_keeps_pending(self):
        self.store.replace_pending('instagram', 'me', [TARGET, {'username': 'bob', 'profileUrl': 'https://www.instagram.com/bob/'}])
        engine = Engine(self.store)
        engine.start('instagram', 'me', 'simulate')
        engine.pause()
        engine.thread.join(timeout=5)
        self.assertEqual(engine.snapshot()['phase'], 'paused')
        self.assertTrue(all(r['status'] == 'pending' for r in self.store.rows('instagram', 'me')))

    def test_only_one_process_uses_a_data_directory(self):
        with InstanceLock(self.tmp.name):
            with self.assertRaises(RuntimeError):
                InstanceLock(self.tmp.name).acquire()
        with InstanceLock(self.tmp.name):
            pass

    def test_action_validation_and_persistence(self):
        fb_target = {'username': 'amigo.fb', 'profileUrl': 'https://www.facebook.com/amigo.fb/'}
        self.store.replace_pending('facebook', 'me', [fb_target], action='unfriend')
        rows = self.store.rows('facebook', 'me')
        self.assertEqual(rows[0]['action'], 'unfriend')
        with self.assertRaises(ValueError):
            self.store.replace_pending('instagram', 'me', [TARGET], action='unfriend')
        with self.assertRaises(ValueError):
            self.store.replace_pending('tiktok', 'me', [{'username': 't1', 'profileUrl': 'https://www.tiktok.com/@t1/'}], action='unfriend')

    def test_schedule_next_run_computation(self):
        base = datetime(2026, 11, 23, 15, 0, tzinfo=timezone.utc)
        once_target = (base + timedelta(hours=2)).isoformat()
        self.assertEqual(
            compute_next_run({'enabled': True, 'kind': 'once', 'runAt': once_target}, base),
            once_target,
        )
        interval_next = compute_next_run({'enabled': True, 'kind': 'interval', 'intervalHours': 6, 'runAt': ''}, base)
        self.assertEqual(interval_next, (base + timedelta(hours=6)).isoformat())
        daily_next = compute_next_run(
            {'enabled': True, 'kind': 'daily', 'dailyTime': '23:30', 'weekdays': [0, 2, 4]},
            base,
        )
        parsed_daily = datetime.fromisoformat(daily_next)
        self.assertGreater(parsed_daily, base)
        self.assertIn(parsed_daily.astimezone().weekday(), {0, 2, 4})

    def test_scheduler_multi_network_tick_and_grace_window(self):
        self.store.replace_pending('instagram', 'me_ig', [TARGET])
        self.store.replace_pending('tiktok', 'me_tt', [{'username': 'tt_one', 'profileUrl': 'https://www.tiktok.com/@tt_one/'}])
        self.store.replace_pending('facebook', 'me_fb', [{'username': 'fb_one', 'profileUrl': 'https://www.facebook.com/fb_one/'}], action='unfriend')
        engine = Engine(self.store)
        mock_runner = lambda args: SimpleNamespace(returncode=1, stdout='', stderr='')
        scheduler = Scheduler(self.store, engine, os_task_runner=mock_runner)

        base = datetime(2026, 11, 23, 18, 0, tzinfo=timezone.utc)
        due = base + timedelta(minutes=10)
        scheduler.configure(
            {
                'enabled': True,
                'kind': 'once',
                'mode': 'simulate',
                'runAt': due.isoformat(),
                'allNetworks': True,
                'limit': 5,
                'dailyLimit': 10,
                'interval': 5,
                'networkPause': 5,
                'headless': True,
                'windowsTask': False,
            },
            reference_now=base,
        )
        self.assertEqual(scheduler.tick(reference_now=base + timedelta(minutes=5)), 'waiting')
        self.assertEqual(scheduler.tick(reference_now=due + timedelta(seconds=30)), 'started')
        engine.thread.join(timeout=10)
        state = engine.snapshot()
        self.assertEqual(state['phase'], 'complete')
        self.assertEqual(state['batchTotal'], 3)
        self.assertEqual(state['batchSource'], 'scheduled')
        # Una programación 'once' se desactiva automáticamente tras ejecutarse.
        self.assertFalse(self.store.get_schedule()['enabled'])

        # Una ejecución 'once' fuera del margen de 15 minutos no se dispara de golpe.
        scheduler.configure(
            {'enabled': True, 'kind': 'once', 'mode': 'simulate', 'runAt': due.isoformat(), 'allNetworks': True},
            reference_now=base,
        )
        self.assertEqual(scheduler.tick(reference_now=due + timedelta(seconds=GRACE_WINDOW_SECONDS + 60)), 'missed')
        self.assertFalse(self.store.get_schedule()['enabled'])
        self.assertEqual(self.store.get_schedule()['lastStatus'], 'missed')

        # Una programación diaria vencida se reprograma limpiamente al futuro sin disparos retrasados.
        scheduler.configure(
            {'enabled': True, 'kind': 'daily', 'mode': 'simulate', 'dailyTime': '09:00', 'weekdays': [0, 1, 2, 3, 4, 5, 6]},
            reference_now=base,
        )
        scheduled_next = datetime.fromisoformat(self.store.get_schedule()['nextRunAt'])
        self.assertEqual(
            scheduler.tick(reference_now=scheduled_next + timedelta(seconds=GRACE_WINDOW_SECONDS + 120)),
            'rescheduled',
        )
        self.assertTrue(self.store.get_schedule()['enabled'])
        self.assertGreater(datetime.fromisoformat(self.store.get_schedule()['nextRunAt']), scheduled_next)

    def test_scheduler_safety_halt_isolates_network_and_clears(self):
        self.store.replace_pending('instagram', 'me_ig', [TARGET])
        self.store.replace_pending('tiktok', 'me_tt', [{'username': 'tt_one', 'profileUrl': 'https://www.tiktok.com/@tt_one/'}])
        engine = Engine(self.store)
        mock_runner = lambda args: SimpleNamespace(returncode=1, stdout='', stderr='')
        scheduler = Scheduler(self.store, engine, os_task_runner=mock_runner)

        self.store.set_schedule_halt('instagram', 'me_ig', 'Captcha detectado.')
        snap = scheduler.snapshot()
        ig = next(q for q in snap['queues'] if q['platform'] == 'instagram')
        self.assertTrue(ig['halted'])
        self.assertFalse(ig['eligible'])
        self.assertEqual(ig['haltReason'], 'Captcha detectado.')

        self.assertTrue(scheduler.clear_halt('instagram', 'me_ig'))
        snap_after = scheduler.snapshot()
        ig_after = next(q for q in snap_after['queues'] if q['platform'] == 'instagram')
        self.assertFalse(ig_after['halted'])

    def test_windows_task_xml_and_mocked_lifecycle(self):
        next_run = '2026-11-24T04:00:00+00:00'
        for cfg, expected_tag in [
            ({'kind': 'once'}, 'TimeTrigger'),
            ({'kind': 'daily', 'weekdays': [0, 1, 2, 3, 4, 5, 6]}, 'ScheduleByDay'),
            ({'kind': 'daily', 'weekdays': [0, 2, 4]}, 'ScheduleByWeek'),
            ({'kind': 'interval', 'intervalHours': 12}, 'Repetition'),
        ]:
            xml_text = build_task_xml(cfg, next_run, self.tmp.name)
            self.assertIn('InteractiveToken', xml_text)
            self.assertIn('LeastPrivilege', xml_text)
            self.assertIn(expected_tag, xml_text)
            # Valida que sea XML sintácticamente válido.
            ET.fromstring(xml_text.split('\n', 1)[1])

        calls = []
        def fake_runner(args):
            calls.append(args)
            return SimpleNamespace(returncode=0, stdout='OK', stderr='')

        self.assertTrue(install_windows_task({'kind': 'daily', 'weekdays': [0, 1, 2, 3, 4, 5, 6]}, next_run, self.tmp.name, runner=fake_runner))
        self.assertEqual(calls[-1][:4], ['schtasks', '/Create', '/TN', TASK_NAME])
        info = query_windows_task(runner=fake_runner)
        self.assertTrue(info['registered'])
        self.assertTrue(remove_windows_task(runner=fake_runner))
        self.assertEqual(calls[-1], ['schtasks', '/Delete', '/TN', TASK_NAME, '/F'])

    def test_cli_run_scheduled_once_executes_due_simulate_batch(self):
        self.store.replace_pending('instagram', 'me_ig', [TARGET])
        now_utc = datetime.now(timezone.utc)
        self.store.save_schedule(
            {'enabled': True, 'kind': 'once', 'mode': 'simulate', 'runAt': (now_utc - timedelta(seconds=10)).isoformat(), 'allNetworks': True},
            next_run_at=(now_utc - timedelta(seconds=10)).isoformat(),
        )
        code = run_scheduled_once(Path(self.tmp.name))
        self.assertEqual(code, 0)
        self.assertFalse(self.store.get_schedule()['enabled'])
        self.assertEqual(self.store.get_schedule()['lastStatus'], 'complete')


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win_calls = []
        def mock_os_runner(args):
            self.win_calls.append(args)
            return SimpleNamespace(returncode=1, stdout='', stderr='')
        self.server = make_server(0, self.tmp.name, os_task_runner=mock_os_runner)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.token = json.load(urlopen(self.url + '/api/status'))['token']

    def tearDown(self):
        self.server.shutdown()
        self.server.engine.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def post(self, route, data, origin=None, token=None):
        headers = {'Content-Type': 'application/json', 'Origin': origin or self.url, 'X-Circulo-Token': token or self.token}
        return urlopen(Request(self.url + route, data=json.dumps(data).encode(), headers=headers, method='POST'))

    def test_foreign_origin_and_invalid_token_cannot_mutate(self):
        for headers in [{'origin': 'https://evil.test'}, {'token': 'invalid'}]:
            with self.assertRaises(HTTPError) as caught:
                self.post('/api/pause', {}, **headers)
            self.assertEqual(caught.exception.code, 403)

    def test_end_to_end_queue_and_simulate(self):
        self.post('/api/queue', {'platform': 'instagram', 'account': 'me', 'targets': [TARGET], 'demo': True}).close()
        self.post('/api/run', {'platform': 'instagram', 'account': 'me', 'mode': 'simulate'}).close()
        self.server.engine.thread.join(timeout=5)
        state = json.load(urlopen(self.url + '/api/status'))
        self.assertEqual(state['phase'], 'complete')
        self.assertEqual(state['processed'], 1)
        rows = json.load(urlopen(self.url + '/api/queue'))
        self.assertEqual(rows[0]['status'], 'pending')
        self.assertEqual(rows[0]['demo'], 1)
        with self.assertRaises(HTTPError) as caught:
            self.post('/api/run', {'platform': 'instagram', 'account': 'me', 'mode': 'live'})
        self.assertEqual(caught.exception.code, 400)

    def test_host_rebinding_is_rejected(self):
        req = Request(self.url + '/api/status', headers={'Host': 'evil.test'})
        with self.assertRaises(HTTPError) as caught:
            urlopen(req)
        self.assertEqual(caught.exception.code, 403)

    def test_session_check_endpoint_and_headless_validation(self):
        status = json.load(urlopen(self.url + '/api/session?platform=instagram&account=me'))
        self.assertEqual(status['saved'], False)
        profile_dir = self.server.engine.profile('instagram', 'me') / 'Default'
        profile_dir.mkdir(parents=True, exist_ok=True)
        status_after = json.load(urlopen(self.url + '/api/session?platform=instagram&account=me'))
        self.assertEqual(status_after['saved'], True)
        self.post('/api/queue', {'platform': 'instagram', 'account': 'me', 'targets': [TARGET], 'demo': True}).close()
        delete_resp = json.load(self.post('/api/session/delete', {'platform': 'instagram', 'account': 'me'}))
        self.assertEqual(delete_resp['removed'], True)
        status_deleted = json.load(urlopen(self.url + '/api/session?platform=instagram&account=me'))
        self.assertEqual(status_deleted['saved'], False)
        # Borrar sesión nunca debe borrar la cola persistente.
        rows = json.load(urlopen(self.url + '/api/queue'))
        self.assertEqual(len(rows), 1)
        with self.assertRaises(HTTPError) as caught:
            self.post('/api/run', {'platform': 'instagram', 'account': 'me', 'mode': 'simulate', 'headless': 'yes'})
        self.assertEqual(caught.exception.code, 400)

    def test_cloud_sync_provider_detection(self):
        self.assertEqual(cloud_sync_provider(Path('C:/Users/Test/OneDrive/Circulo/data')), 'OneDrive')
        self.assertEqual(cloud_sync_provider(Path('C:/Users/Test/Dropbox/Circulo/data')), 'Dropbox')
        self.assertIsNone(cloud_sync_provider(Path(self.tmp.name)))

    def test_clear_finished_removes_done_and_skipped_but_keeps_pending_and_attempts(self):
        targets = [
            {'username': 'alice', 'profileUrl': 'https://www.instagram.com/alice/'},
            {'username': 'bob', 'profileUrl': 'https://www.instagram.com/bob/'},
            {'username': 'carol', 'profileUrl': 'https://www.instagram.com/carol/'},
        ]
        self.post('/api/queue', {'platform': 'instagram', 'account': 'me', 'targets': targets}).close()
        rows = json.load(urlopen(self.url + '/api/queue'))
        self.server.engine.store.reserve_attempt(rows[0], 10)
        self.server.engine.store.set_state(rows[0]['id'], 'done', 'ok')
        self.server.engine.store.set_state(rows[1]['id'], 'skipped', 'ya no sigues')
        resp = json.load(self.post('/api/queue/clear-finished', {'platform': 'instagram', 'account': 'me'}))
        self.assertEqual(resp['removed'], 2)
        remaining = json.load(urlopen(self.url + '/api/queue'))
        self.assertEqual([r['username'] for r in remaining], ['carol'])
        # El límite diario de intentos permanece intacto tras limpiar la lista.
        self.assertFalse(self.server.engine.store.reserve_attempt(remaining[0], 1))

    def test_schedule_endpoints_multi_network_and_facebook_unfriend_action(self):
        fb_target = {'username': 'amigo.fb', 'profileUrl': 'https://www.facebook.com/amigo.fb/'}
        self.post('/api/queue', {'platform': 'instagram', 'account': 'me_ig', 'targets': [TARGET]}).close()
        self.post('/api/queue', {'platform': 'facebook', 'account': 'me_fb', 'targets': [fb_target], 'action': 'unfriend'}).close()

        # Configura y activa programación diaria en modo simulación.
        saved = json.load(self.post('/api/schedule', {
            'enabled': True,
            'kind': 'daily',
            'mode': 'simulate',
            'dailyTime': '22:30',
            'weekdays': [0, 1, 2, 3, 4, 5, 6],
            'allNetworks': True,
            'limit': 10,
            'dailyLimit': 20,
            'interval': 10,
            'networkPause': 5,
            'headless': True,
            'windowsTask': False,
        }))
        self.assertTrue(saved['scheduler']['config']['enabled'])
        self.assertEqual(saved['scheduler']['eligibleCount'], 2)
        fb_q = next(q for q in saved['scheduler']['queues'] if q['platform'] == 'facebook')
        self.assertEqual(fb_q['actions'], ['unfriend'])

        # Pausa rápida y ejecución manual del lote multi-red.
        toggled = json.load(self.post('/api/schedule/toggle', {'enabled': False}))
        self.assertFalse(toggled['scheduler']['config']['enabled'])
        started = json.load(self.post('/api/schedule/run-now', {'mode': 'simulate'}))
        self.assertEqual(started['started'], 2)
        self.server.engine.thread.join(timeout=10)
        status = json.load(urlopen(self.url + '/api/status'))
        self.assertEqual(status['phase'], 'complete')
        self.assertEqual(status['batchTotal'], 2)

        # Limpieza de bloqueo de seguridad y rechazo de origen externo.
        self.server.engine.store.set_schedule_halt('facebook', 'me_fb', 'Revisión manual.')
        cleared = json.load(self.post('/api/schedule/clear-halt', {'platform': 'facebook', 'account': 'me_fb'}))
        self.assertTrue(cleared['cleared'])
        with self.assertRaises(HTTPError) as caught:
            self.post('/api/schedule', {'enabled': False}, origin='https://evil.test')
        self.assertEqual(caught.exception.code, 403)


if __name__ == '__main__':
    unittest.main()
