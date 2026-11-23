import argparse
import json
import time
from pathlib import Path

from .engine import Engine
from .instance import InstanceLock
from .paths import default_data_dir
from .scheduler import Scheduler
from .store import Store


def _wait_engine(engine):
    previous = ''
    try:
        while engine.thread and engine.thread.is_alive():
            state = engine.snapshot()
            if state['message'] != previous:
                previous = state['message']
                print(previous, flush=True)
            time.sleep(.25)
    except KeyboardInterrupt:
        engine.pause()
        if engine.thread:
            engine.thread.join()


def run_scheduled_once(data_dir):
    """Ejecuta una comprobación única de la programación (pensado para tareas de Windows con la app cerrada)."""
    try:
        instance_lock = InstanceLock(data_dir).acquire()
    except RuntimeError:
        # Si el servidor principal de Círculo ya está abierto, él mismo gestionará el disparo programado.
        print('Círculo ya está en ejecución; el programador interno gestionará este horario.', flush=True)
        return 0
    store = Store(data_dir)
    engine = Engine(store)
    scheduler = Scheduler(store, engine)
    try:
        result = scheduler.tick()
        if result == 'started':
            _wait_engine(engine)
            final_state = engine.snapshot()
            print(final_state['message'], flush=True)
            return 1 if final_state['phase'] == 'error' else 0
        print(f'Programador verificado: {result}.', flush=True)
        return 0
    finally:
        engine.shutdown()
        instance_lock.release()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Ejecutor local de Círculo. Comprobación sin clics por defecto.')
    parser.add_argument('--targets', type=Path)
    parser.add_argument('--account')
    parser.add_argument('--action', default='unfollow', choices=('unfollow', 'unfriend'))
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--daily-limit', type=int, default=30)
    parser.add_argument('--interval', type=int, default=45)
    parser.add_argument('--data', type=Path, default=default_data_dir())
    parser.add_argument('--run-scheduled', action='store_true')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--execute', action='store_true')
    modes.add_argument('--dry-run', action='store_true')
    modes.add_argument('--simulate', action='store_true')
    args = parser.parse_args(argv)

    if args.run_scheduled:
        return run_scheduled_once(args.data)
    if not args.targets or not args.account:
        parser.error('Indica --targets y --account, o usa --run-scheduled.')

    payload = json.loads(args.targets.read_text(encoding='utf-8-sig'))
    if payload.get('demo') and args.execute:
        parser.error('No se ejecutan acciones reales con datos de ejemplo.')
    instance_lock = InstanceLock(args.data).acquire()
    store = Store(args.data)
    engine = Engine(store)
    store.replace_pending(payload['platform'], args.account, payload['targets'], payload.get('demo', False), args.action)
    mode = 'live' if args.execute else 'simulate' if args.simulate else 'inspect'
    engine.start(payload['platform'], args.account, mode, args.limit, args.daily_limit, args.interval)
    try:
        _wait_engine(engine)
    finally:
        engine.shutdown()
        instance_lock.release()
    print(engine.snapshot()['message'])
    return 1 if engine.snapshot()['phase'] == 'error' else 0


if __name__ == '__main__':
    raise SystemExit(main())
