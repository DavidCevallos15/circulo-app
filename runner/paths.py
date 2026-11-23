"""Rutas de la app para el modo desarrollo y para el ejecutable portable (PyInstaller)."""
import os
import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parent.parent
CLOUD_SYNC_MARKERS = ('onedrive', 'dropbox', 'google drive', 'googledrive', 'my drive', 'icloud', 'icloud drive', 'box sync', 'mega')


def is_frozen():
    """Indica si la app se ejecuta como binario empaquetado."""
    return bool(getattr(sys, 'frozen', False))


def static_dir():
    """Carpeta de la web compilada (dist) según el modo de ejecución."""
    if is_frozen():
        return Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent)) / 'dist'
    return SOURCE_ROOT / 'dist'


def default_data_dir():
    """Carpeta de datos privada. En el ejecutable vive en %LOCALAPPDATA%, fuera de carpetas sincronizadas."""
    if is_frozen():
        base = os.environ.get('LOCALAPPDATA') or str(Path.home() / 'AppData' / 'Local')
        return Path(base) / 'Circulo' / 'data'
    return SOURCE_ROOT / 'data'


def cloud_sync_provider(directory):
    """Devuelve el nombre del servicio de sincronización si la carpeta de datos está dentro de uno."""
    resolved = Path(directory).resolve()
    lowered = str(resolved).lower()
    for variable in ('OneDrive', 'OneDriveConsumer', 'OneDriveCommercial'):
        root = os.environ.get(variable)
        if root and lowered.startswith(str(Path(root).resolve()).lower()):
            return 'OneDrive'
    for part in resolved.parts:
        name = part.lower()
        for marker in CLOUD_SYNC_MARKERS:
            if name == marker or name.startswith(f'{marker} ') or name.startswith(f'{marker}-'):
                return part
    return None
