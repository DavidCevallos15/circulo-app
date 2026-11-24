import io
import json
import os
import sys
import threading
import tempfile
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT
sys.path.insert(0, str(APP))
from runner.server import make_server
from runner.platforms import Adapter, Halt, SkipAccount, Uncertain
from playwright.sync_api import sync_playwright

review = APP / '.impeccable' / 'review'
review.mkdir(parents=True, exist_ok=True)
temporary_data = tempfile.mkdtemp(prefix='circulo-qa-')
server = make_server(0, temporary_data)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
url = f'http://127.0.0.1:{server.server_port}'
errors = []
checks = []

def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)

try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
        page.on('pageerror', lambda err: errors.append(str(err)))
        page.goto(url)
        page.get_by_text('Ejecutor local conectado').wait_for()
        if os.environ.get('CAPTURE_QA') == '1': page.screenshot(path=str(review / 'desktop-empty.png'), full_page=True)
        page.get_by_role('button', name='Explorar con datos de ejemplo').click()
        check('demo filter shows 8 non-mutual accounts', page.locator('tbody tr').count() == 8)
        page.get_by_label('Proteger estudio.norte', exact=True).click()
        check('protect disables selection', page.get_by_label('Seleccionar estudio.norte', exact=True).is_disabled())
        page.get_by_label('Seleccionar todas las cuentas del filtro').check()
        page.get_by_label('Tu cuenta de Instagram').fill('qa.demo')
        if os.environ.get('CAPTURE_QA') == '1': page.screenshot(path=str(review / 'desktop.png'), full_page=True)
        page.get_by_role('button', name='Iniciar simulación', exact=True).click()
        page.get_by_text('Simulación terminada. No se modificó ninguna cuenta.', exact=True).wait_for(timeout=20000)
        check('offline simulation recorded 7 pending accounts', page.get_by_text('7 pendientes', exact=True).is_visible())
        page.get_by_label('Modo de ejecución').select_option('live')
        page.get_by_role('button', name='Procesar 7 pendientes').click()
        check('demo queue blocked for real execution', page.get_by_text('Carga tus archivos reales antes de comprobar o ejecutar.', exact=True).is_visible())
        page.get_by_role('button', name='Conexiones', exact=False).first.click()
        page.get_by_label('Buscar una cuenta').fill('cafe')
        check('search filters account list', page.locator('tbody tr').count() == 2)
        page.get_by_label('Buscar una cuenta').fill('')
        page.set_viewport_size({'width': 390, 'height': 844})
        if os.environ.get('CAPTURE_QA') == '1': page.screenshot(path=str(review / 'mobile.png'), full_page=True)
        check('mobile has no document overflow', page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        check('mobile bottom navigation is visible', page.get_by_label('Navegación móvil').is_visible())
        page.set_viewport_size({'width': 320, 'height': 640})
        check('small phone 320px has no document overflow', page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        page.set_viewport_size({'width': 768, 'height': 900})
        check('tablet 768px has no document overflow', page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        page.set_viewport_size({'width': 1100, 'height': 850})
        check('compact desktop has no overflow', page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        page.get_by_label('Filtrar conexiones').select_option('all')
        check('pagination limits to ten rows', page.locator('tbody tr').count() == 10)
        page.get_by_role('button', name='Siguiente', exact=True).click()
        check('pagination shows remaining rows', page.locator('tbody tr').count() == 2)
        page.get_by_role('tab', name='TikTok', exact=False).click()
        check('platform switch isolates empty platform', page.get_by_text('Tu círculo empieza aquí.').is_visible())
        page.get_by_role('tab', name='Instagram', exact=False).click()
        check('switching back preserves previous platform data', page.locator('tbody tr').count() > 0)
        page.get_by_label('Archivos de seguidos y seguidores').set_input_files([
            {'name': 'following.json', 'mimeType': 'application/json', 'buffer': json.dumps({'relationships_following': [{'title': 'alice', 'string_list_data': [{'href': 'https://www.instagram.com/alice/'}]}, {'title': 'bob', 'string_list_data': [{'href': 'https://www.instagram.com/bob/'}]}]}).encode()},
            {'name': 'followers_1.json', 'mimeType': 'application/json', 'buffer': json.dumps([{'string_list_data': [{'value': 'alice'}]}, {'string_list_data': [{'value': 'carol_fan'}]}]).encode()}
        ])
        page.get_by_text('2 archivos importados. Los datos se procesaron en tu navegador.', exact=True).wait_for()
        check('browser multi-file import and comparison', page.locator('tbody tr').count() == 1 and '@bob' in page.locator('tbody').inner_text())
        check('demo label is removed after real-format import', page.get_by_text('Datos de ejemplo. Ninguna de estas cuentas es tuya.').count() == 0)
        page.get_by_label('Filtrar conexiones').select_option('fans')
        check('fans filter lists followers user does not follow back', '@carol_fan' in page.locator('tbody').inner_text())
        with page.expect_download() as csv_download:
            page.get_by_role('button', name='Reporte CSV', exact=True).click()
        csv_body = Path(csv_download.value.path()).read_text(encoding='utf-8-sig')
        check('csv report includes non-mutuals and fans', 'bob' in csv_body and 'carol_fan' in csv_body)
        page.get_by_label('Filtrar conexiones').select_option('not-following')
        # Comprueba carga directa de un archivo ZIP oficial en memoria sin descomprimir.
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('connections/followers_and_following/following.json', json.dumps({'relationships_following': [{'title': 'zip_target'}]}))
            zf.writestr('connections/followers_and_following/followers_1.json', json.dumps([]))
        page.get_by_role('tab', name='TikTok', exact=False).click()
        page.get_by_role('tab', name='Instagram', exact=False).click()
        page.get_by_label('Archivos de seguidos y seguidores').set_input_files([
            {'name': 'instagram-export.zip', 'mimeType': 'application/zip', 'buffer': zip_buf.getvalue()}
        ])
        page.get_by_text('ZIP procesado en memoria:', exact=False).wait_for()
        check('direct zip import extracts non-mutuals in browser', '@zip_target' in page.locator('tbody').inner_text())
        page.get_by_label('Seleccionar bob', exact=True).check()
        with page.expect_download() as download:
            page.get_by_role('button', name='Exportar JSON', exact=True).click()
        payload = json.loads(Path(download.value.path()).read_text())
        check('download exports only selected accounts', payload['targets'][0]['username'] == 'bob' and payload['demo'] is False)
        page.get_by_role('button', name='Dejar de seguir selección', exact=True).click()
        dialog = page.get_by_role('dialog')
        dialog.wait_for()
        check('confirmation makes background inert', page.locator('.main-shell').get_attribute('inert') is not None)
        page.get_by_label('Escribe tu usuario para ejecutar').fill('qa.demo')
        dialog.get_by_role('button', name='Ejecutar ahora').focus()
        page.keyboard.press('Tab')
        check('confirmation tab wraps focus', dialog.get_by_role('button', name='Cerrar confirmación').evaluate('(element) => element === document.activeElement'))
        page.keyboard.press('Escape')
        check('escape closes confirmation and restores focus', page.get_by_role('dialog').count() == 0 and page.get_by_role('button', name='Dejar de seguir selección', exact=True).evaluate('(element) => element === document.activeElement'))
        # Guarda cola de Instagram sin ejecutar aún y prepara otra en Facebook con Quitar de amigos (beta).
        page.get_by_role('button', name='Guardar en cola', exact=True).click()
        page.get_by_text('Se guardaron 1 cuentas en la cola de Instagram', exact=False).wait_for()
        page.get_by_role('tab', name='Facebook', exact=False).click()
        page.get_by_label('Tu cuenta de Facebook').fill('qa.fb')
        page.get_by_label('Acción en Facebook').select_option('unfriend')
        check('facebook unfriend warning is visible', page.get_by_text('Irreversible sin nueva solicitud de amistad.', exact=False).is_visible())
        page.get_by_label('Archivos de seguidos y seguidores').set_input_files([
            {'name': 'following.txt', 'mimeType': 'text/plain', 'buffer': b'https://www.facebook.com/amigo.prueba/\n'}
        ])
        page.get_by_text('1 archivo importado.', exact=False).wait_for()
        page.get_by_label('Filtrar conexiones').select_option('all')
        page.get_by_label('Seleccionar amigo.prueba', exact=True).check()
        page.get_by_role('button', name='Guardar en cola', exact=True).click()
        page.get_by_text('Se guardaron 1 cuentas en la cola de Facebook', exact=False).wait_for()
        # Abre la pestaña Programación y valida flujo multi-red, responsive y confirmación real.
        page.set_viewport_size({'width': 1440, 'height': 1000})
        page.get_by_role('button', name='Programación', exact=False).first.click()
        page.get_by_text('Tu limpieza, a la hora que elijas.', exact=True).wait_for()
        check('schedule view lists both instagram and facebook queues', page.get_by_text('Instagram · @qa.demo').is_visible() and page.get_by_text('Facebook · @qa.fb').is_visible())
        check('schedule view shows facebook unfriend action', page.locator('.schedule-view').get_by_text('Quitar de amigos (beta)', exact=False).is_visible())
        page.get_by_label('Modo de ejecución programada').select_option('live')
        page.get_by_role('button', name='Guardar y activar programación', exact=True).click()
        page.get_by_role('dialog').wait_for()
        check('live schedule requires explicit PROGRAMAR confirmation', page.get_by_label('Escribe PROGRAMAR para activar').is_visible())
        page.keyboard.press('Escape')
        page.get_by_label('Modo de ejecución programada').select_option('simulate')
        page.get_by_role('button', name='Guardar y activar programación', exact=True).click()
        page.get_by_text('Programación activa', exact=True).wait_for()
        check('schedule armed shows next run time', page.get_by_text('Próxima ejecución:', exact=False).is_visible())
        if os.environ.get('CAPTURE_QA') == '1': page.screenshot(path=str(review / 'schedule-desktop.png'), full_page=True)
        for vp in [{'width': 390, 'height': 844}, {'width': 320, 'height': 640}, {'width': 768, 'height': 900}]:
            page.set_viewport_size(vp)
            if os.environ.get('CAPTURE_QA') == '1' and vp['width'] == 390: page.screenshot(path=str(review / 'schedule-mobile.png'), full_page=True)
            check(f'schedule view has no overflow at {vp["width"]}px', page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        page.set_viewport_size({'width': 1440, 'height': 1000})
        page.get_by_role('button', name='Ejecutar lote ahora', exact=False).click()
        page.get_by_text('Simulación multi-red terminada', exact=False).wait_for(timeout=20000)
        check('multi-network batch simulation completed across networks', page.get_by_text('Simulación multi-red terminada (2 redes', exact=False).is_visible())
        # Comprueba el modo Analizador Web público (?mode=web): sin errores de ejecutor local, sin llamadas /api y responsive limpio.
        web_page = browser.new_page(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
        web_errors = []
        web_api_calls = []
        web_page.on('pageerror', lambda err: web_errors.append(str(err)))
        web_page.on('request', lambda req: web_api_calls.append(req.url) if '/api/' in req.url else None)
        web_page.goto(url + '/?mode=web')
        web_page.get_by_text('Analizador web privado', exact=True).wait_for()
        check('public web mode hides offline local runner error', web_page.get_by_text('El ejecutor local no está disponible').count() == 0)
        check('public web mode shows Pro reservation CTA', web_page.get_by_role('link', name='Reservar Círculo Pro · $9 USD').is_visible())
        download_cta = web_page.get_by_role('link', name='Descargar gratis para Windows')
        check('public web mode shows free Windows download CTA', download_cta.is_visible() and download_cta.get_attribute('href') == 'https://www.davidcevallos.me/circulo/descargar/')
        check('public web mode makes zero /api requests', web_api_calls == [])
        web_page.get_by_role('button', name='Explorar con datos de ejemplo').click()
        check('public web mode analyzes demo accounts locally', web_page.locator('tbody tr').count() == 8)
        for vp in [{'width': 1440, 'height': 900}, {'width': 768, 'height': 900}, {'width': 390, 'height': 844}, {'width': 320, 'height': 640}]:
            web_page.set_viewport_size(vp)
            check(f'public web mode has no overflow at {vp["width"]}px', web_page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        check('public web mode has zero JS errors', web_errors == [])
        web_page.close()
        check('no browser JavaScript errors', errors == [])
        # Exercise adapters against controlled HTML, with every platform URL intercepted.
        fixture = browser.new_page()
        fixture.route('**/*', lambda route: route.fulfill(status=200, content_type='text/html; charset=utf-8', body='''<html><body><button id="following" onclick="document.getElementById('dialog').hidden=false">Siguiendo</button><div id="dialog" role="dialog" hidden><button onclick="document.getElementById('following').textContent='Seguir';document.getElementById('dialog').hidden=true">Dejar de seguir</button></div></body></html>'''))
        for platform, target in [('instagram','https://www.instagram.com/alice/'), ('facebook','https://www.facebook.com/alice/')]:
            adapter = Adapter(fixture, platform)
            adapter.visit(target)
            adapter.execute()
            check(f'{platform} adapter confirms and verifies in fixture', fixture.get_by_role('button', name='Seguir', exact=True).is_visible())
        fixture.unroute('**/*')
        # Verifica quitar de amigos en Facebook (beta): Amigos -> menú Eliminar de mis amigos -> diálogo Confirmar -> Agregar a amigos.
        fb_unfriend_fixture = '''<html><body>
            <button id="friend-btn" onclick="document.getElementById('menu').hidden=false">Amigos</button>
            <div id="menu" role="menu" hidden>
                <div role="menuitem" onclick="document.getElementById('menu').hidden=true;document.getElementById('confirm').hidden=false">Eliminar de mis amigos</div>
            </div>
            <div id="confirm" role="dialog" hidden>
                <button onclick="document.getElementById('friend-btn').textContent='Agregar a amigos';document.getElementById('confirm').hidden=true">Confirmar</button>
            </div>
        </body></html>'''
        fixture.route('**/*', lambda route: route.fulfill(status=200, content_type='text/html; charset=utf-8', body=fb_unfriend_fixture))
        fb_unfriend = Adapter(fixture, 'facebook', action='unfriend')
        fb_unfriend.visit('https://www.facebook.com/amigo.prueba/')
        fb_unfriend.execute()
        check('facebook unfriend adapter confirms two steps and verifies add-friend state', fixture.get_by_role('button', name='Agregar a amigos', exact=True).is_visible())
        try:
            fb_unfriend.inspect()
            raise AssertionError('already unfriended not skipped')
        except SkipAccount:
            checks.append('facebook already unfriended raises SkipAccount')
        fixture.unroute('**/*')
        # Verifica que en modo unfollow (por defecto) Facebook nunca toca el botón Amigos.
        fixture.route('**/*', lambda route: route.fulfill(status=200, content_type='text/html; charset=utf-8', body='<html><body><button>Amigos</button></body></html>'))
        try:
            fb_default = Adapter(fixture, 'facebook', action='unfollow')
            fb_default.visit('https://www.facebook.com/solo.amigo/')
            fb_default.inspect()
            raise AssertionError('default facebook unfollow touched Amigos')
        except Halt:
            checks.append('facebook default unfollow never touches Amigos button')
        fixture.unroute('**/*')
        # Simula el DOM real de Instagram: botón Following con icono SVG chevron y diálogo asíncrono tras spinner.
        instagram_real_fixture = '''<html><body><main><header>
            <button id="following" type="button" onclick="const d=document.getElementById('dialog');d.hidden=false;setTimeout(()=>{d.innerHTML='<div role=\\'button\\' tabindex=\\'0\\' onclick=&quot;document.getElementById(\\'following\\').innerHTML=\\'Follow\\';document.getElementById(\\'dialog\\').hidden=true&quot;>Unfollow</div>';}, 800)">
                <div><div>Following</div><div><svg aria-label="Down chevron icon" role="img"><title>Down chevron icon</title></svg></div></div>
            </button>
            <div role="button">Message</div>
        </header></main>
        <div id="dialog" role="dialog" aria-modal="true" hidden><div role="progressbar"></div></div>
        </body></html>'''
        fixture.route('**/*', lambda route: route.fulfill(status=200, content_type='text/html; charset=utf-8', body=instagram_real_fixture))
        adapter = Adapter(fixture, 'instagram')
        adapter.visit('https://www.instagram.com/innovabots/')
        adapter.execute()
        check('instagram adapter handles chevron svg and async dialog', fixture.get_by_role('button', name='Follow', exact=True).is_visible())
        fixture.unroute('**/*')
        fixture.route('**/*', lambda route: route.fulfill(status=200, content_type='text/html; charset=utf-8', body='<html><body><button onclick="this.textContent=\'Seguir\'">Siguiendo</button></body></html>'))
        adapter = Adapter(fixture, 'tiktok')
        adapter.visit('https://www.tiktok.com/@alice/')
        adapter.execute()
        check('tiktok direct toggle verified in fixture', fixture.get_by_role('button', name='Seguir', exact=True).is_visible())
        fixture.unroute('**/*')
        # Simula el DOM real de TikTok con 24 botones (barra lateral Following/Friends + sugeridos + 1 botón de encabezado con aria-haspopup="dialog").
        suggested = ''.join(f'<button type="button" data-e2e="follow-button" aria-label="Follow Sugerido {i}">Follow</button>' for i in range(20))
        tiktok_real_fixture = f'''<html><body>
            <aside><button role="listitem" aria-label="Following">Following</button><button role="listitem" aria-label="Friends">Friends</button></aside>
            <div data-e2e="user-page">
                <button type="button" id="hdr" data-e2e="follow-button" aria-haspopup="dialog" aria-label="Following Sergio Rovira" onclick="this.textContent='Follow';this.setAttribute('aria-label','Follow Sergio Rovira')">Following</button>
                <section>{suggested}</section>
            </div>
        </body></html>'''
        fixture.route('**/*', lambda route: route.fulfill(status=200, content_type='text/html; charset=utf-8', body=tiktok_real_fixture))
        adapter = Adapter(fixture, 'tiktok')
        adapter.visit('https://www.tiktok.com/@sergio.rovira/')
        adapter.execute()
        check('tiktok real 24-button DOM isolates header follow button', fixture.locator('#hdr').inner_text() == 'Follow')
        fixture.unroute('**/*')
        # Verifica la detección automática de cuenta autenticada en Instagram (barra colapsada) y TikTok (nav-profile).
        ig_home = '''<html><body><nav><a href="/davosaurio__/"><img alt="davosaurio__'s profile picture"><div style="display:none"><span>Profile</span></div></a></nav><main><a href="/otro/"><img alt="otro's profile picture"></a></main></body></html>'''
        fixture.route('**/*', lambda route: route.fulfill(status=200, content_type='text/html; charset=utf-8', body=ig_home))
        check('instagram account verification matches logged-in user', Adapter(fixture, 'instagram').verify_account('davosaurio__') == 'davosaurio__')
        try:
            Adapter(fixture, 'instagram').verify_account('cuenta_incorrecta')
            raise AssertionError('mismatched instagram account not halted')
        except Halt:
            checks.append('instagram account verification halts on mismatch')
        fixture.unroute('**/*')
        tt_home = '''<html><body><nav><a data-e2e="nav-profile" href="/@userfedora123">Profile</a></nav></body></html>'''
        fixture.route('**/*', lambda route: route.fulfill(status=200, content_type='text/html; charset=utf-8', body=tt_home))
        check('tiktok account verification matches nav-profile handle', Adapter(fixture, 'tiktok').verify_account('userfedora123') == 'userfedora123')
        try:
            Adapter(fixture, 'tiktok').verify_account('otra_cuenta')
            raise AssertionError('mismatched tiktok account not halted')
        except Halt:
            checks.append('tiktok account verification halts on mismatch')
        fixture.unroute('**/*')
        fixture.route('**/*', lambda route: route.fulfill(status=200, content_type='text/html; charset=utf-8', body='<html><body><p>Inténtalo de nuevo más tarde</p><button>Siguiendo</button></body></html>'))
        try:
            Adapter(fixture, 'instagram').visit('https://www.instagram.com/alice/')
            raise AssertionError('block not detected')
        except Halt:
            checks.append('platform warning halts before action')
        fixture.unroute('**/*')
        fixture.route('**/*', lambda route: route.fulfill(status=200, content_type='text/html; charset=utf-8', body='<html><body><main><header><button>Follow</button></header></main></body></html>'))
        try:
            adapter = Adapter(fixture, 'instagram')
            adapter.visit('https://www.instagram.com/already_unfollowed/')
            adapter.inspect()
            raise AssertionError('already unfollowed not skipped')
        except SkipAccount:
            checks.append('already unfollowed profile raises SkipAccount')
        fixture.unroute('**/*')
        fixture.route('**/*', lambda route: route.fulfill(status=404, content_type='text/html; charset=utf-8', body='<html><body>Not found</body></html>'))
        try:
            Adapter(fixture, 'instagram').visit('https://www.instagram.com/deleted_user/')
            raise AssertionError('404 not skipped')
        except SkipAccount:
            checks.append('http 404 profile raises SkipAccount')
        browser.close()
finally:
    server.shutdown()
    server.engine.shutdown()
    server.server_close()
    thread.join(timeout=2)
    shutil.rmtree(temporary_data)

(review / 'qa-results.json').write_text(json.dumps({'checks': checks, 'errors': errors}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'passed': len(checks), 'checks': checks, 'errors': errors}, ensure_ascii=False))
