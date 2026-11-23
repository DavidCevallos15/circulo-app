"""Punto de entrada silencioso para el Programador de tareas de Windows (pythonw.exe)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runner.cli import main  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(main(['--run-scheduled', *sys.argv[1:]]))
