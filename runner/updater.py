"""Comprobador seguro de actualizaciones de Círculo (sin telemetría, solo HTTPS y verificación SHA-256)."""
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .paths import SOURCE_ROOT, is_frozen

DEFAULT_VERSION = '0.4.0'
DEFAULT_UPDATE_URL = 'https://api.github.com/repos/DavidCevallos15/circulo-app/releases/latest'
DEFAULT_ALLOWED_HOSTS = frozenset({
    'api.github.com',
    'github.com',
    'objects.githubusercontent.com',
    'release-assets.githubusercontent.com',
    'davidcevallos.me',
    'www.davidcevallos.me',
})
MAX_RESPONSE_BYTES = 512 * 1024
REQUEST_TIMEOUT_SECONDS = 6
CACHE_TTL_SECONDS = 900
SEMVER_RE = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$')
SHA256_LINE_RE = re.compile(r'^([a-fA-F0-9]{64})\s+\*?(.+)$')


def get_app_version():
    """Lee la versión oficial desde package.json (tanto en desarrollo como en binario congelado)."""
    candidates = []
    if is_frozen():
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            candidates.append(Path(meipass) / 'package.json')
        candidates.append(Path(sys.executable).resolve().parent / 'package.json')
    candidates.append(SOURCE_ROOT / 'package.json')

    for candidate in candidates:
        try:
            if candidate.is_file():
                payload = json.loads(candidate.read_text(encoding='utf-8'))
                version = str(payload.get('version') or '').strip()
                if parse_semver(version):
                    return version.lstrip('vV')
        except Exception:
            continue
    return DEFAULT_VERSION


def parse_semver(raw):
    """Convierte una cadena semver (ej. v0.4.0 o 0.5.0-beta.1) en una tupla comparable."""
    if not isinstance(raw, str):
        return None
    match = SEMVER_RE.match(raw.strip())
    if not match:
        return None
    major, minor, patch, prerelease = match.groups()
    # Una versión estable (1) siempre precede a una pre-release (0) del mismo número.
    return (int(major), int(minor), int(patch), 0 if prerelease else 1, prerelease or '')


def is_newer_version(candidate, current):
    """Indica si la versión candidata es estrictamente más reciente que la actual."""
    parsed_candidate = parse_semver(candidate)
    parsed_current = parse_semver(current)
    if not parsed_candidate or not parsed_current:
        return False
    return parsed_candidate[:4] > parsed_current[:4]


def resolve_allowed_hosts():
    """Combina los hosts confiables por defecto con CIRCULO_UPDATE_ALLOWED_HOSTS si está definida."""
    hosts = set(DEFAULT_ALLOWED_HOSTS)
    extra = os.environ.get('CIRCULO_UPDATE_ALLOWED_HOSTS', '').strip()
    if extra:
        for item in extra.split(','):
            cleaned = item.strip().lower()
            if cleaned and '/' not in cleaned and ':' not in cleaned:
                hosts.add(cleaned)
    return frozenset(hosts)


def validate_update_url(url, allowed_hosts=None):
    """Exige HTTPS limpio sin credenciales y restringido a dominios confiables."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError('La URL de actualización está vacía.')
    parsed = urlparse(url.strip())
    if parsed.scheme != 'https':
        raise ValueError('El canal de actualizaciones solo admite enlaces HTTPS.')
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError('La URL de actualización contiene parámetros no permitidos.')
    host = (parsed.hostname or '').lower()
    allowed = allowed_hosts if allowed_hosts is not None else resolve_allowed_hosts()
    if host not in allowed:
        raise ValueError(f'Dominio de actualización no autorizado: {host or "vacío"}.')
    return parsed.geturl()


def parse_sha256_sums(text, filename=None):
    """Extrae el hash SHA-256 esperado desde un archivo SHA256SUMS.txt."""
    if not isinstance(text, str):
        return None
    target = filename.strip().lower() if filename else None
    first_match = None
    for line in text.splitlines():
        match = SHA256_LINE_RE.match(line.strip())
        if not match:
            continue
        digest, entry_name = match.group(1).lower(), match.group(2).strip()
        if first_match is None:
            first_match = digest
        if target and entry_name.lower().endswith(target):
            return digest
    return first_match if not target else None


def verify_file_sha256(file_path, expected_hex):
    """Valida la integridad SHA-256 de un paquete descargado con comparación en tiempo constante."""
    if not isinstance(expected_hex, str) or not re.fullmatch(r'[a-fA-F0-9]{64}', expected_hex.strip()):
        raise ValueError('El hash SHA-256 esperado no tiene un formato válido.')
    digest = hashlib.sha256()
    with Path(file_path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return hmac.compare_digest(digest.hexdigest().lower(), expected_hex.strip().lower())


def _default_fetch_json(url, timeout=REQUEST_TIMEOUT_SECONDS, user_agent='Circulo'):
    """Descarga un JSON remoto con límite de tamaño estricto y sin telemetría del usuario."""
    request = Request(
        url,
        headers={
            'User-Agent': user_agent,
            'Accept': 'application/vnd.github+json, application/json',
        },
        method='GET',
    )
    with urlopen(request, timeout=timeout) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError('La respuesta del servidor de actualizaciones supera el tamaño permitido.')
        return json.loads(raw.decode('utf-8'))


def _clean_notes(text):
    """Resume las notas de lanzamiento eliminando ruido excesivo de Markdown."""
    if not isinstance(text, str):
        return ''
    collapsed = re.sub(r'\s+', ' ', text).strip()
    return collapsed[:280]


def _extract_release_fields(payload, allowed_hosts):
    """Normaliza tanto respuestas de GitHub Releases como manifiestos JSON propios (futuros planes por uso)."""
    if not isinstance(payload, dict):
        raise ValueError('El manifiesto de actualización debe ser un objeto JSON.')

    # Formato 1: manifiesto propio (ej. https://www.davidcevallos.me/circulo/update.json)
    if 'version' in payload and 'tag_name' not in payload:
        latest_raw = str(payload.get('version') or '').strip()
        if not parse_semver(latest_raw):
            raise ValueError('El manifiesto no contiene una versión semver válida.')
        release_url = payload.get('releaseUrl')
        download_url = payload.get('downloadUrl')
        sha256_raw = str(payload.get('sha256') or '').strip().lower()
        return {
            'latestVersion': latest_raw.lstrip('vV'),
            'releaseUrl': validate_update_url(release_url, allowed_hosts) if release_url else None,
            'downloadUrl': validate_update_url(download_url, allowed_hosts) if download_url else None,
            'sha256': sha256_raw if re.fullmatch(r'[a-f0-9]{64}', sha256_raw) else None,
            'notes': _clean_notes(payload.get('notes', '')),
            'publishedAt': str(payload.get('publishedAt') or '') or None,
            'minSupportedVersion': str(payload.get('minSupportedVersion') or '') or None,
            'source': 'manifest',
        }

    # Formato 2: API estándar de GitHub Releases (/releases/latest)
    tag_name = str(payload.get('tag_name') or '').strip()
    if not parse_semver(tag_name):
        raise ValueError('No se encontró una versión válida en el lanzamiento publicado.')

    release_url = payload.get('html_url')
    download_url = None
    assets = payload.get('assets') if isinstance(payload.get('assets'), list) else []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get('name') or '').lower()
        candidate_url = asset.get('browser_download_url')
        if name.endswith('-win64.zip') and candidate_url:
            download_url = validate_update_url(candidate_url, allowed_hosts)
            break

    return {
        'latestVersion': tag_name.lstrip('vV'),
        'releaseUrl': validate_update_url(release_url, allowed_hosts) if release_url else None,
        'downloadUrl': download_url,
        'sha256': None,
        'notes': _clean_notes(payload.get('body', '')),
        'publishedAt': str(payload.get('published_at') or '') or None,
        'minSupportedVersion': None,
        'source': 'github-releases',
    }


class UpdateChecker:
    """Gestiona comprobaciones de versión bajo demanda con caché en memoria."""

    def __init__(self, current_version=None, endpoint=None, allowed_hosts=None, fetcher=None, ttl_seconds=CACHE_TTL_SECONDS):
        self.current_version = current_version or get_app_version()
        self.endpoint = (endpoint or os.environ.get('CIRCULO_UPDATE_URL') or DEFAULT_UPDATE_URL).strip()
        self.allowed_hosts = allowed_hosts if allowed_hosts is not None else resolve_allowed_hosts()
        self.fetcher = fetcher or _default_fetch_json
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._cached = None
        self._cached_monotonic = 0.0

    def snapshot(self):
        """Devuelve el último estado de actualización conocido sin generar tráfico de red."""
        with self._lock:
            return dict(self._cached) if self._cached else None

    def check(self, force=False):
        """Consulta el canal oficial de lanzamientos y devuelve un resumen seguro."""
        now_mono = time.monotonic()
        with self._lock:
            if not force and self._cached and (now_mono - self._cached_monotonic) < self.ttl_seconds:
                return dict(self._cached)

        checked_at = datetime.now(timezone.utc).isoformat()
        try:
            safe_url = validate_update_url(self.endpoint, self.allowed_hosts)
            raw_payload = self.fetcher(
                safe_url,
                timeout=REQUEST_TIMEOUT_SECONDS,
                user_agent=f'Circulo/{self.current_version}',
            )
            fields = _extract_release_fields(raw_payload, self.allowed_hosts)
            result = {
                'checkedAt': checked_at,
                'currentVersion': self.current_version,
                'latestVersion': fields['latestVersion'],
                'updateAvailable': is_newer_version(fields['latestVersion'], self.current_version),
                'releaseUrl': fields['releaseUrl'],
                'downloadUrl': fields['downloadUrl'],
                'sha256': fields['sha256'],
                'notes': fields['notes'],
                'publishedAt': fields['publishedAt'],
                'minSupportedVersion': fields['minSupportedVersion'],
                'source': fields['source'],
                'error': None,
            }
        except Exception as exc:
            result = {
                'checkedAt': checked_at,
                'currentVersion': self.current_version,
                'latestVersion': None,
                'updateAvailable': False,
                'releaseUrl': None,
                'downloadUrl': None,
                'sha256': None,
                'notes': '',
                'publishedAt': None,
                'minSupportedVersion': None,
                'source': None,
                'error': str(exc)[:220],
            }

        with self._lock:
            self._cached = result
            self._cached_monotonic = time.monotonic()
            return dict(result)
