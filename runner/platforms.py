"""Adaptadores conservadores de interfaz validados en sesiones reales (Instagram y TikTok) y beta (Facebook)."""
import re
import time
from urllib.parse import parse_qs, urlparse

from .store import PLATFORMS, validate_action

PROFILE_READY_TIMEOUT_MS = 12000
ACCOUNT_CHECK_TIMEOUT_MS = 8000
CONFIRM_TIMEOUT_MS = 8000
TIKTOK_CONFIRM_TIMEOUT_MS = 2500
VERIFY_FOLLOW_TIMEOUT_MS = 10000
POLL_INTERVAL_MS = 300

RESERVED_SEGMENTS = {
    'accounts', 'explore', 'reels', 'stories', 'login', 'settings', 'home',
    'watch', 'groups', 'friends', 'direct', 'create', 'messages', 'following',
    'foryou', 'live', 'upload', 'search', 'notifications', 'bookmarks', 'pages',
    'marketplace', 'gaming', 'memories', 'saved', 'events', 'help', 'privacy',
}


class Halt(Exception):
    pass


class DailyLimitReached(Halt):
    """Detención benigna cuando se agota el cupo diario UTC de una cuenta."""
    pass


class Uncertain(Halt):
    pass


class SkipAccount(Exception):
    """Error recuperable de un perfil puntual (eliminado o ya dejado de seguir) que permite continuar la cola."""
    pass


class Adapter:
    def __init__(self, page, platform, action='unfollow'):
        self.page = page
        self.platform = platform
        self.action = validate_action(platform, action)
        # En Instagram Web el botón "Siguiendo"/"Following" incluye un icono SVG desplegable en su nombre accesible.
        if platform == 'instagram':
            self.following = re.compile(
                r"^(Siguiendo|Following)(?:\s+(?:(?:down\s+)?chevron(?:\s+down)?(?:\s+icon)?|icono\s+de\s+[^,]+|flecha\s+[^,]+))?$",
                re.I,
            )
            self.follow = re.compile(r"^(Seguir|Follow|Follow back|Seguir también|Seguir de vuelta)$", re.I)
            self.unfollow = re.compile(r"^(Dejar de seguir|Unfollow)(?:\s+@?[\w.]+)?$", re.I)
            self.secondary_confirm = None
        elif platform == 'tiktok':
            # En TikTok Web el botón del perfil incluye el nombre visible en aria-label (ej. "Following Sergio Rovira").
            self.following = re.compile(r"^(Siguiendo|Following|Amigos|Friends)(?:\s+.+)?$", re.I)
            self.follow = re.compile(r"^(Seguir|Follow|Follow back|Seguir también|Seguir de vuelta)(?:\s+.+)?$", re.I)
            self.unfollow = re.compile(r"^(Dejar de seguir|Unfollow)(?:\s+@?[\w.]+)?$", re.I)
            self.secondary_confirm = None
        elif self.action == 'unfriend':
            # En Facebook (modo beta explícito), quitar de amigos requiere el botón Amigos -> Eliminar de mis amigos -> Confirmar.
            self.following = re.compile(r"^(Amigos|Friends)$", re.I)
            self.follow = re.compile(r"^(Agregar a amigos|Añadir a amigos|Add friend)$", re.I)
            self.unfollow = re.compile(r"^(Eliminar de mis amigos|Eliminar de amigos|Unfriend)$", re.I)
            self.secondary_confirm = re.compile(r"^(Confirmar|Confirm)$", re.I)
        else:
            self.following = re.compile(r"^(Siguiendo|Following)$", re.I)
            self.follow = re.compile(r"^(Seguir|Follow|Follow back|Seguir también|Seguir de vuelta)$", re.I)
            self.unfollow = re.compile(r"^(Dejar de seguir|Unfollow)(?:\s+@?[\w.]+)?$", re.I)
            self.secondary_confirm = None

        self.unavailable = re.compile(
            r"sorry,\s*this\s+page\s+isn['’]t\s+available|esta\s+página\s+no\s+está\s+disponible|couldn['’]t\s+find\s+this\s+account|no\s+se\s+pudo\s+encontrar\s+esta\s+cuenta|profile\s+isn['’]t\s+available|este\s+perfil\s+no\s+está\s+disponible|this\s+content\s+isn['’]t\s+available",
            re.I,
        )

    def guard(self):
        url = self.page.url.lower()
        expected = {'instagram': 'instagram.com', 'tiktok': 'tiktok.com', 'facebook': 'facebook.com'}[self.platform]
        host = urlparse(url).hostname or ''
        if host not in {expected, f'www.{expected}'}:
            raise Halt("El navegador salió de la plataforma. Revisa la sesión.")
        if any(s in url for s in ('/challenge', '/checkpoint', '/captcha', '/login', '/accounts/login')):
            raise Halt("La plataforma requiere iniciar sesión o resolver una verificación. Ejecución detenida.")
        body = self.page.locator('body').inner_text(timeout=10000)
        if re.search(
            r"try again later|inténtalo de nuevo más tarde|intenta de nuevo más tarde|action blocked|acción bloqueada|we restrict certain activity|restringimos ciertas actividades|too many requests|demasiadas solicitudes|confirm.{0,20}(?:human|humano)|suspicious activity|actividad sospechosa|enter.{0,15}code|introduce.{0,15}código",
            body,
            re.I,
        ):
            raise Halt("La plataforma muestra un límite o una verificación. Ejecución detenida.")
        if self.page.locator('input[type="password"]').count() or self.page.locator('iframe[src*="captcha" i]').count() or self.page.locator('[id*="captcha" i]').count():
            raise Halt("Hay un inicio de sesión o captcha pendiente. Ejecución detenida.")

    def visible_matches(self, locator):
        """Devuelve únicamente los elementos actualmente visibles de un localizador."""
        return [locator.nth(i) for i in range(locator.count()) if locator.nth(i).is_visible()]

    def unique_visible(self, locator):
        matches = self.visible_matches(locator)
        if len(matches) != 1:
            raise Halt(f"Se esperó un único control visible; se encontraron {len(matches)}. No se hará clic.")
        return matches[0]

    def profile_scope(self):
        """Acota la búsqueda al encabezado del perfil en Instagram para evitar falsos positivos."""
        if self.platform == 'instagram':
            header = self.page.locator('main header')
            if header.count() == 1 and header.first.is_visible():
                return header.first
        return self.page

    def _tiktok_header_button(self):
        """En TikTok real hay botones 'Following'/'Follow' en la barra lateral y en cuentas sugeridas; solo el encabezado tiene aria-haspopup='dialog'."""
        if self.platform != 'tiktok':
            return None
        scoped = self.visible_matches(self.page.locator('button[data-e2e="follow-button"][aria-haspopup="dialog"]'))
        return scoped if scoped else None

    def _control_label(self, element):
        """Obtiene el texto visible o aria-label de un control para validar su estado exacto."""
        try:
            text = (element.inner_text(timeout=2000) or '').strip()
            if text:
                return text
        except Exception:
            pass
        return (element.get_attribute('aria-label') or '').strip()

    def following_controls(self):
        """Devuelve los controles visibles en estado Siguiendo/Following del perfil actual."""
        tiktok_header = self._tiktok_header_button()
        if tiktok_header is not None:
            return [btn for btn in tiktok_header if self.following.match(self._control_label(btn))]
        return self.visible_matches(self.profile_scope().get_by_role('button', name=self.following))

    def follow_controls(self):
        """Devuelve los controles visibles en estado Seguir/Follow del perfil actual."""
        tiktok_header = self._tiktok_header_button()
        if tiktok_header is not None:
            return [btn for btn in tiktok_header if self.follow.match(self._control_label(btn))]
        return self.visible_matches(self.profile_scope().get_by_role('button', name=self.follow))

    def _extract_handle_from_href(self, href):
        """Extrae el identificador normalizado de una ruta de perfil de la plataforma actual."""
        if not href:
            return None
        parsed = urlparse(href)
        if parsed.hostname and parsed.hostname not in {PLATFORMS[self.platform], PLATFORMS[self.platform].removeprefix('www.')}:
            return None
        if self.platform == 'facebook' and parsed.path == '/profile.php':
            ids = parse_qs(parsed.query).get('id') or []
            return ids[0].lower() if ids and ids[0].isdigit() else None
        segments = [s for s in parsed.path.split('/') if s]
        if len(segments) != 1:
            return None
        handle = segments[0].removeprefix('@').lower()
        if not handle or handle in RESERVED_SEGMENTS:
            return None
        return handle

    def detect_logged_in_account(self):
        """Lee el @usuario autenticado en la navegación de la plataforma sin depender del idioma de la interfaz."""
        if self.platform == 'tiktok':
            nav = self.page.locator('a[data-e2e="nav-profile"]')
            if nav.count() >= 1:
                return self._extract_handle_from_href(nav.first.get_attribute('href') or '')
            return None

        if self.platform == 'instagram':
            # En Instagram la barra lateral puede estar colapsada (el texto "Profile"/"Perfil" está oculto pero el <a> fuera de <main> conserva href e <img alt>).
            href = self.page.evaluate(
                """() => {
                    const reserved = new Set(['accounts', 'explore', 'reels', 'stories', 'login', 'settings', 'home', 'direct', 'create']);
                    const links = Array.from(document.querySelectorAll('a[href^="/"]')).filter(a => !a.closest('main'));
                    for (const a of links) {
                        const text = (a.textContent || '').trim().toLowerCase();
                        const segs = (a.getAttribute('href') || '').split('?')[0].split('/').filter(Boolean);
                        if (segs.length === 1 && !reserved.has(segs[0].toLowerCase())) {
                            if (text === 'profile' || text === 'perfil') return a.getAttribute('href');
                        }
                    }
                    for (const a of links) {
                        const segs = (a.getAttribute('href') || '').split('?')[0].split('/').filter(Boolean);
                        if (segs.length === 1 && !reserved.has(segs[0].toLowerCase()) && a.querySelector('img[alt]')) {
                            return a.getAttribute('href');
                        }
                    }
                    return null;
                }"""
            )
            return self._extract_handle_from_href(href)

        if self.platform == 'facebook':
            href = self.page.evaluate(
                """() => {
                    const navs = document.querySelectorAll('nav[aria-label="Accesos directos"] a[href], nav[aria-label="Shortcuts"] a[href]');
                    if (navs.length > 0) return navs[0].getAttribute('href');
                    const bio = document.querySelector('a[aria-label^="Biografía de "], a[aria-label$="\\'s profile"]');
                    return bio ? bio.getAttribute('href') : null;
                }"""
            )
            return self._extract_handle_from_href(href)

        return None

    def verify_account(self, expected_account, strict=True):
        """Comprueba antes de ejecutar que la sesión abierta coincide con la cuenta declarada por el usuario."""
        expected = expected_account.strip().lstrip('@').lower()
        home_url = f"https://{PLATFORMS[self.platform]}/"
        response = self.page.goto(home_url, wait_until='domcontentloaded', timeout=45000)
        if response and response.status >= 400:
            raise Halt(f"No se pudo comprobar la sesión (HTTP {response.status}).")
        deadline = time.monotonic() + (ACCOUNT_CHECK_TIMEOUT_MS / 1000)
        detected = None
        while True:
            self.guard()
            detected = self.detect_logged_in_account()
            if detected or time.monotonic() >= deadline:
                break
            self.page.wait_for_timeout(POLL_INTERVAL_MS)

        if detected and detected != expected:
            raise Halt(
                f"La sesión abierta pertenece a @{detected}, pero indicaste @{expected}. "
                "Cambia el usuario o vuelve a iniciar sesión para no operar en otra cuenta."
            )
        if not detected and strict:
            raise Halt(
                "No se pudo confirmar qué cuenta tiene la sesión abierta. "
                "Pulsa «Revisar sesión» y comprueba que estás autenticado antes de ejecutar."
            )
        return detected

    def wait_for_profile_ready(self, timeout_ms=PROFILE_READY_TIMEOUT_MS):
        """Espera a que la SPA renderice el control de seguimiento del perfil antes de inspeccionar."""
        deadline = time.monotonic() + (timeout_ms / 1000)
        while True:
            self.guard()
            if self.following_controls() or self.follow_controls():
                return
            body = self.page.locator('body').inner_text(timeout=10000)
            if self.unavailable.search(body):
                raise SkipAccount("La cuenta ya no existe o no está disponible.")
            if time.monotonic() >= deadline:
                return
            self.page.wait_for_timeout(POLL_INTERVAL_MS)

    def confirmation_controls(self):
        """Busca el botón de confirmación priorizando el menú o diálogo modal visible."""
        menus = self.visible_matches(self.page.get_by_role('menu'))
        dialogs = self.visible_matches(self.page.get_by_role('dialog'))
        scope = dialogs[-1] if dialogs else (menus[-1] if menus else self.page)
        return scope.get_by_role('button', name=self.unfollow).or_(scope.get_by_role('menuitem', name=self.unfollow))

    def secondary_confirmation_controls(self):
        """Busca el segundo diálogo de confirmación (por ejemplo, Confirmar al quitar amigo en Facebook)."""
        if not self.secondary_confirm:
            return None
        dialogs = self.visible_matches(self.page.get_by_role('dialog'))
        scope = dialogs[-1] if dialogs else self.page
        return scope.get_by_role('button', name=self.secondary_confirm)

    def wait_for_confirmation(self):
        """Espera a que el menú o diálogo de confirmación termine de cargar sus opciones."""
        timeout_ms = TIKTOK_CONFIRM_TIMEOUT_MS if self.platform == 'tiktok' else CONFIRM_TIMEOUT_MS
        deadline = time.monotonic() + (timeout_ms / 1000)
        while True:
            self.guard()
            visible = self.visible_matches(self.confirmation_controls())
            if visible:
                return visible
            if self.platform == 'tiktok' and len(self.follow_controls()) == 1:
                return []
            if time.monotonic() >= deadline:
                return []
            self.page.wait_for_timeout(POLL_INTERVAL_MS)

    def wait_for_secondary_confirmation(self):
        """Espera el diálogo de confirmación final en acciones de dos pasos (como quitar de amigos en Facebook)."""
        if not self.secondary_confirm:
            return []
        deadline = time.monotonic() + (CONFIRM_TIMEOUT_MS / 1000)
        while True:
            self.guard()
            locator = self.secondary_confirmation_controls()
            visible = self.visible_matches(locator) if locator is not None else []
            if visible:
                return visible
            if len(self.follow_controls()) == 1 and len(self.following_controls()) == 0:
                return []
            if time.monotonic() >= deadline:
                return []
            self.page.wait_for_timeout(POLL_INTERVAL_MS)

    def wait_for_follow_state(self, timeout_ms=VERIFY_FOLLOW_TIMEOUT_MS):
        """Espera a que el estado visible del perfil cambie al estado final esperado tras confirmar."""
        deadline = time.monotonic() + (timeout_ms / 1000)
        while True:
            self.guard()
            if len(self.follow_controls()) == 1 and len(self.following_controls()) == 0:
                return
            if time.monotonic() >= deadline:
                break
            self.page.wait_for_timeout(POLL_INTERVAL_MS)
        matches = self.follow_controls()
        expected_label = 'Agregar a amigos' if self.action == 'unfriend' else 'Seguir'
        if len(matches) != 1 or len(self.following_controls()) != 0:
            raise Halt(f"Se esperó un único control {expected_label} visible; se encontraron {len(matches)}.")

    def visit(self, url):
        response = self.page.goto(url, wait_until='domcontentloaded', timeout=45000)
        if response and response.status == 404:
            raise SkipAccount("La cuenta no existe o fue eliminada (HTTP 404).")
        if response and response.status >= 400:
            raise Halt(f"El perfil respondió HTTP {response.status}.")
        self.wait_for_profile_ready()
        self.guard()
        # Una redirección de perfil no garantiza haber llegado a la cuenta esperada.
        intended = urlparse(url)
        actual = urlparse(self.page.url)
        if intended.path.rstrip('/').lower() != actual.path.rstrip('/').lower() or (intended.query and intended.query != actual.query):
            raise Halt("El perfil redirigió a otra página. Revisa la cuenta antes de continuar.")

    def inspect(self):
        self.guard()
        # Por defecto en Facebook solo se toca Siguiendo; únicamente en modo explícito 'unfriend' se busca Amigos.
        following_matches = self.following_controls()
        if len(following_matches) == 1:
            return following_matches[0]
        if len(following_matches) == 0 and len(self.follow_controls()) == 1:
            raise SkipAccount("Ya no está en tu lista de amigos." if self.action == 'unfriend' else "Ya no sigues esta cuenta.")
        raise Halt(f"Se esperó un único control visible; se encontraron {len(following_matches)}. No se hará clic.")

    def execute(self, before_click=None):
        button = self.inspect()
        self.guard()
        if before_click:
            before_click()
        clicked = False
        try:
            clicked = True
            button.click(timeout=10000)
            # Instagram y Facebook muestran menú/diálogo asíncrono; TikTok puede abrir diálogo o alternar directo.
            visible = self.wait_for_confirmation()
            if visible:
                if len(visible) != 1:
                    raise Uncertain("La confirmación es ambigua. Revisa el perfil manualmente.")
                self.guard()
                visible[0].click(timeout=10000)
                if self.secondary_confirm:
                    second_step = self.wait_for_secondary_confirmation()
                    if second_step:
                        if len(second_step) != 1:
                            raise Uncertain("La confirmación final es ambigua. Revisa el perfil manualmente.")
                        self.guard()
                        second_step[0].click(timeout=10000)
            elif self.platform != 'tiktok':
                raise Uncertain("No se encontró la confirmación. Revisa el perfil manualmente.")
            self.wait_for_follow_state()
        except Exception as exc:
            if clicked:
                raise Uncertain(f"No se pudo verificar el resultado: {exc}") from exc
            raise
