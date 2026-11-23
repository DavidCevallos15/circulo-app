"""Integración opcional y nativa con el Programador de tareas de Windows mediante XML ISO-8601."""
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from .paths import SOURCE_ROOT, is_frozen

TASK_NAME = 'CirculoAutoUnfollow'
TASK_XML_NAMESPACE = 'http://schemas.microsoft.com/windows/2004/02/mit/task'
WEEKDAY_XML_TAGS = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')


def is_windows_supported():
    """Indica si el sistema operativo actual permite registrar tareas nativas en Windows."""
    return os.name == 'nt'


def resolve_scheduled_command(data_dir):
    """Construye el ejecutable, argumentos y directorio de trabajo para ejecuciones desatendidas."""
    resolved_data = str(Path(data_dir).resolve())
    if is_frozen():
        executable = str(Path(sys.executable).resolve())
        return {
            'command': executable,
            'arguments': f'--run-scheduled --data "{resolved_data}"',
            'workingDirectory': str(Path(executable).parent),
        }
    python_path = Path(sys.executable).resolve()
    pythonw = python_path.with_name('pythonw.exe')
    executable = str(pythonw if pythonw.is_file() else python_path)
    entry_script = str((SOURCE_ROOT / 'runner' / 'scheduled_entry.py').resolve())
    return {
        'command': executable,
        'arguments': f'"{entry_script}" --data "{resolved_data}"',
        'workingDirectory': str(SOURCE_ROOT.resolve()),
    }


def _to_local_iso(iso_timestamp):
    """Convierte una marca ISO UTC a hora local sin zona horaria para StartBoundary de Windows."""
    parsed = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone().replace(tzinfo=None, microsecond=0).isoformat()


def build_task_xml(config, next_run_at, data_dir):
    """Genera el XML oficial de Windows Task Scheduler (independiente del idioma/formato de fecha)."""
    if not next_run_at:
        raise ValueError('No hay una próxima ejecución válida para registrar en Windows.')
    spec = resolve_scheduled_command(data_dir)
    start_boundary = _to_local_iso(next_run_at)

    task = ET.Element('Task', {'version': '1.2', 'xmlns': TASK_XML_NAMESPACE})
    reg = ET.SubElement(task, 'RegistrationInfo')
    ET.SubElement(reg, 'Description').text = 'Ejecuta automáticamente la cola programada de Círculo sin abrir consola.'

    triggers = ET.SubElement(task, 'Triggers')
    kind = config.get('kind', 'daily')
    if kind == 'once':
        trigger = ET.SubElement(triggers, 'TimeTrigger')
        ET.SubElement(trigger, 'StartBoundary').text = start_boundary
        ET.SubElement(trigger, 'Enabled').text = 'true'
    elif kind == 'daily':
        trigger = ET.SubElement(triggers, 'CalendarTrigger')
        ET.SubElement(trigger, 'StartBoundary').text = start_boundary
        ET.SubElement(trigger, 'Enabled').text = 'true'
        weekdays = config.get('weekdays') or [0, 1, 2, 3, 4, 5, 6]
        if len(weekdays) == 7:
            by_day = ET.SubElement(trigger, 'ScheduleByDay')
            ET.SubElement(by_day, 'DaysInterval').text = '1'
        else:
            by_week = ET.SubElement(trigger, 'ScheduleByWeek')
            ET.SubElement(by_week, 'WeeksInterval').text = '1'
            days_elem = ET.SubElement(by_week, 'DaysOfWeek')
            for day in sorted(set(weekdays)):
                ET.SubElement(days_elem, WEEKDAY_XML_TAGS[day])
    else:
        trigger = ET.SubElement(triggers, 'TimeTrigger')
        ET.SubElement(trigger, 'StartBoundary').text = start_boundary
        ET.SubElement(trigger, 'Enabled').text = 'true'
        repetition = ET.SubElement(trigger, 'Repetition')
        ET.SubElement(repetition, 'Interval').text = f"PT{int(config.get('intervalHours', 24))}H"
        ET.SubElement(repetition, 'StopAtDurationEnd').text = 'false'

    principals = ET.SubElement(task, 'Principals')
    principal = ET.SubElement(principals, 'Principal', {'id': 'Author'})
    # InteractiveToken asegura que solo se ejecute con sesión de usuario abierta y nunca pida permisos de administrador.
    ET.SubElement(principal, 'LogonType').text = 'InteractiveToken'
    ET.SubElement(principal, 'RunLevel').text = 'LeastPrivilege'

    settings = ET.SubElement(task, 'Settings')
    ET.SubElement(settings, 'MultipleInstancesPolicy').text = 'IgnoreNew'
    ET.SubElement(settings, 'DisallowStartIfOnBatteries').text = 'false'
    ET.SubElement(settings, 'StopIfGoingOnBatteries').text = 'false'
    ET.SubElement(settings, 'AllowHardTerminate').text = 'true'
    ET.SubElement(settings, 'StartWhenAvailable').text = 'false'
    ET.SubElement(settings, 'RunOnlyIfNetworkAvailable').text = 'true'
    ET.SubElement(settings, 'AllowStartOnDemand').text = 'true'
    ET.SubElement(settings, 'Enabled').text = 'true'
    ET.SubElement(settings, 'Hidden').text = 'false'
    ET.SubElement(settings, 'ExecutionTimeLimit').text = 'PT4H'

    actions = ET.SubElement(task, 'Actions', {'Context': 'Author'})
    exec_action = ET.SubElement(actions, 'Exec')
    ET.SubElement(exec_action, 'Command').text = spec['command']
    ET.SubElement(exec_action, 'Arguments').text = spec['arguments']
    ET.SubElement(exec_action, 'WorkingDirectory').text = spec['workingDirectory']

    return '<?xml version="1.0" encoding="UTF-16"?>\n' + ET.tostring(task, encoding='unicode')


def _default_run(args):
    return subprocess.run(args, capture_output=True, text=True, check=False, shell=False, timeout=15)


def query_windows_task(runner=_default_run):
    """Comprueba si la tarea programada de Círculo existe actualmente en Windows."""
    if not is_windows_supported():
        return {'supported': False, 'registered': False, 'detail': 'Solo disponible en Windows.'}
    try:
        result = runner(['schtasks', '/Query', '/TN', TASK_NAME])
        if result.returncode == 0:
            return {'supported': True, 'registered': True, 'detail': f'Tarea «{TASK_NAME}» registrada en Windows.'}
        return {'supported': True, 'registered': False, 'detail': 'Sin tarea registrada en Windows.'}
    except Exception as exc:
        return {'supported': True, 'registered': False, 'detail': f'No se pudo consultar el Programador de tareas: {exc}'}


def install_windows_task(config, next_run_at, data_dir, runner=_default_run):
    """Registra o actualiza la tarea nativa en Windows para ejecutar incluso con Círculo cerrado."""
    if not is_windows_supported():
        raise ValueError('La integración con el Programador de tareas solo está disponible en Windows.')
    xml_body = build_task_xml(config, next_run_at, data_dir)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-16', suffix='.xml', delete=False) as handle:
            handle.write(xml_body)
            temp_path = Path(handle.name)
        result = runner(['schtasks', '/Create', '/TN', TASK_NAME, '/XML', str(temp_path), '/F'])
        if result.returncode != 0:
            error_text = (result.stderr or result.stdout or '').strip()
            raise ValueError(f'No se pudo registrar la tarea de Windows: {error_text or "error desconocido"}')
        return True
    finally:
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def remove_windows_task(runner=_default_run):
    """Elimina la tarea programada de Windows si existe."""
    if not is_windows_supported():
        return False
    result = runner(['schtasks', '/Delete', '/TN', TASK_NAME, '/F'])
    return result.returncode == 0
