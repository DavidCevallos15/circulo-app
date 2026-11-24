# Círculo

Auditoría privada de audiencia para Instagram, TikTok y Facebook: compara tus listas oficiales de seguidos y seguidores, genera reportes y, si quieres, prepara y ejecuta una cola revisada de unfollows desde **tu propio navegador**, en **tu computadora**. Sin contraseñas, sin servidores de terceros. React + TypeScript, Python + Playwright y SQLite.

| Versión | Dónde | Qué hace |
|---|---|---|
| **Analizador web (gratis)** | [davidcevallos.me/circulo/app](https://www.davidcevallos.me/circulo/app/) | Procesa ZIP/JSON/TXT/CSV 100% en el navegador, reportes CSV/HTML, escudo de protección, exporta `targets.json`. No ejecuta acciones. |
| **App de escritorio Windows (gratis)** | [davidcevallos.me/circulo/descargar](https://www.davidcevallos.me/circulo/descargar/) · [Releases](https://github.com/DavidCevallos15/circulo-app/releases/latest) | Todo lo anterior + ejecutor local con simulación, comprobación, ejecución real, límites diarios, pausa y programación multi-red. |
| **Círculo Pro (reserva $9 USD)** | [davidcevallos.me/circulo](https://www.davidcevallos.me/circulo/#reservar) | Soporte directo, actualizaciones prioritarias y próximas funciones. |

## Descargar e iniciar en Windows (recomendado)

1. Descarga `Circulo-<versión>-win64.zip` desde la [página de descarga](https://www.davidcevallos.me/circulo/descargar/) o desde [Releases](https://github.com/DavidCevallos15/circulo-app/releases/latest).
2. (Recomendado) Verifica la huella: `Get-FileHash .\Circulo-<versión>-win64.zip -Algorithm SHA256` y compárala con `SHA256SUMS.txt` del release.
3. Descomprime **toda** la carpeta (no la ejecutes desde dentro del ZIP) en una ruta fuera de OneDrive/Dropbox, por ejemplo `C:\Apps\Circulo`.
4. Abre `Circulo\Circulo.exe`. El binario aún no está firmado: si SmartScreen avisa, pulsa **Más información → Ejecutar de todas formas**.
5. Se abre `http://127.0.0.1:8765`. Mantén abierta la ventana de consola mientras uses la app; para salir, ciérrala o usa Ctrl+C.

No necesitas Python, Node ni descargar Chromium: vienen incluidos. Tus datos (cola, historial y sesiones) se guardan en `%LOCALAPPDATA%\Circulo\data`.

### Desde el código fuente

1. Instala **Python 3.10 o posterior**.
2. Clona o descarga el repositorio y abre **iniciar.cmd** (en Linux: `bash start.sh`).
3. La primera vez instala Playwright y Chromium (necesita internet). Luego abre **http://127.0.0.1:8765**.

`dist/` se genera con `npm run build`; Node.js solo hace falta para modificar o reconstruir la interfaz.

## Flujo

1. Solicita tu exportación oficial en formato JSON. Descomprime el ZIP.
2. Importa `following.json` y **todos** los `followers_*.json` de Instagram. Se admite el formato con `relationships_following`, arrays de seguidores, títulos y `string_list_data`.
3. Se muestra “No me siguen”. Sin archivo de seguidores no se infiere que nadie te siga: la relación aparece como desconocida.
4. Selecciona cuentas. El escudo protege una cuenta y la excluye de la selección.
5. Escribe tu usuario en el panel derecho. “Abrir navegador” crea un perfil separado por red y usuario. Inicia sesión tú mismo y comprueba la cuenta. “Guardar y cerrar” cierra el navegador conservando la sesión.
6. Prueba **Simulación**, que no abre perfiles ni hace clics. Después usa **Comprobación**, que busca el control Siguiendo sin pulsarlo.
7. En **Ejecución real**, revisa la selección y confirma tu usuario. Se abre Chromium y se procesa la cola.
8. Puedes pausar y procesar los pendientes desde Actividad, incluso después de reiniciar la app. La pausa termina la acción ya iniciada antes de detener el siguiente perfil.

Una simulación y una comprobación **no** marcan cuentas como completadas. El ejemplo está marcado también en SQLite y no permite ejecutar acciones reales, aunque recargues la página.

## Qué está implementado y qué falta validar

- **Instagram (validado en sesión real):** importación directa de `.zip` oficial o JSON (`following.json` + `followers_*.json`); adaptador validado con el icono desplegable `chevron` del botón `Siguiendo`/`Following` y el diálogo modal asíncrono de `Dejar de seguir`/`Unfollow`; verificación automática del usuario autenticado antes de ejecutar.
- **TikTok (selectores validados en sesión real):** soporte directo para `.zip` oficial, `user_data_tiktok.json` combinado (importa seguidos y seguidores a la vez) y TXT/CSV; adaptador acotado al botón del encabezado (`button[data-e2e="follow-button"][aria-haspopup="dialog"]`) para evitar colisiones con la barra lateral y las cuentas sugeridas; verificación automática vía `a[data-e2e="nav-profile"]`.
- **Facebook (beta):** listas de URLs de perfiles en TXT/CSV, JSON o ZIP; detección del perfil activo en los accesos directos; soporta **Dejar de seguir** (`Siguiendo`, por defecto) y modo explícito **Quitar de amigos (beta)** (`Amigos` → `Eliminar de mis amigos` → `Confirmar`) usando URLs exactas de perfil.
- **Programación automática multi-red:** nueva pestaña **Programación** con horarios de una sola vez, diarios (por días de la semana) o cada N horas. Guarda colas en Instagram, TikTok y Facebook con **Guardar en cola** para que se ejecuten secuencialmente con pausa entre redes, aislamiento de errores de seguridad por red y opción nativa en el **Programador de tareas de Windows** (sin permisos de administrador) para arrancar incluso con la ventana cerrada.
- **Reportes y persistencia por red:** al cambiar entre Instagram, TikTok y Facebook se conservan las listas importadas. Incluye filtro **Solo te siguen** (fans) y exportación de **Reporte CSV** (Excel/Sheets) y **Reporte visual HTML**.
- **Segundo plano y omisión segura:** las ejecuciones corren en segundo plano por defecto y omiten cuentas eliminadas (HTTP 404) o ya dejadas de seguir sin detener el lote; cualquier captcha, login o límite detiene toda la ejecución.
- **Protección de sesión local:** botón **Borrar sesión** por cuenta, aviso automático si la carpeta de datos está dentro de OneDrive/Dropbox/Google Drive y verificación previa de cuenta autenticada.

## Empaquetado portable (1 clic para otros usuarios en Windows)

Para distribuir Círculo sin exigir que el usuario instale Python ni descargue Chromium manualmente:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1 -RebuildWeb
```

El script genera `release/Circulo-<versión>-win64.zip` y `release/SHA256SUMS.txt`. Si defines `CIRCULO_SIGN_THUMBPRINT` (o `CIRCULO_SIGN_PFX` + `CIRCULO_SIGN_PFX_PASSWORD`) por variables de entorno, firma `Circulo.exe` con Authenticode SHA-256 y sello de tiempo RFC 3161. En el ejecutable empaquetado, los datos privados se guardan automáticamente en `%LOCALAPPDATA%\Circulo\data` (fuera de carpetas sincronizadas en la nube).

## Persistencia y límites

- Las listas importadas se analizan en memoria en el navegador y se pierden al recargar. Las seleccionadas se envían al ejecutor **local** al iniciar una cola.
- Los usuarios protegidos y el identificador de cuenta se guardan en `localStorage` por red.
- `data/queue.sqlite3`: cola por red y cuenta, historial y registro. `data/profiles/`: cookies y almacenamiento de Chromium; contiene tu sesión privada. No compartas esta carpeta.
- El límite diario cuenta **intentos iniciados**, también resultados dudosos, por día **UTC**, red y perfil local. No es un límite oficial de las plataformas ni garantiza evitar bloqueos.
- El identificador que escribes es la etiqueta del perfil local. En Instagram y TikTok la app verifica la cuenta autenticada antes de ejecutar y se detiene si no coincide; en Facebook (beta) **comprueba tú que la sesión abierta corresponde a esa cuenta**.
- Antes del primer clic se reserva un intento en SQLite. Si se interrumpe el proceso después, queda “Revisar manualmente” y no se vuelve a ejecutar automáticamente. Reimportar una cuenta completada o dudosa conserva su estado.
- Un captcha, página de login, aviso de límite, redirección inesperada o resultado ambiguo detiene toda la ejecución. No se resuelven captchas ni se eluden verificaciones.
- El servidor escucha solo en `127.0.0.1`; valida Host, Origin y un token por proceso en las mutaciones. No habilita CORS. Usa la dirección local directa, no un proxy público.

## Desarrollo

```powershell
npm ci
npm run build
npm test
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m unittest discover -s tests -p "test_*.py" -v
python tests/browser_smoke.py
python -m runner.server --no-open
```

Para un puerto distinto: `python -m runner.server --port 8766`. En Linux: `bash start.sh`; algunas distribuciones requieren dependencias de sistema de Chromium. Playwright no ofrece el mismo soporte para todas las distribuciones.

El servidor y la CLI no pueden usar simultáneamente la misma carpeta de datos; el segundo proceso muestra un error antes de abrir el navegador. Si usas la CLI, cierra primero la app. Los detalles de las verificaciones están en `VALIDACION.md`.

## Uso responsable

Círculo es una herramienta independiente, sin relación con Meta ni ByteDance. Automatizar acciones puede ir contra los términos de cada plataforma; úsala con tu propia cuenta, con límites conservadores y bajo tu responsabilidad.

Puedes usar Vite (`npm run dev`) para trabajar en la interfaz. El ejecutor rechaza mutaciones desde ese origen: **para probar el flujo completo usa la compilación servida por Python en el puerto 8765**. Esto mantiene una única política de origen local.

## CLI

Exporta `targets.json` desde la web. Usa el mismo `--account` que en la interfaz para reutilizar su perfil.

```powershell
# Simulación offline, sin navegador
python -m runner.cli --targets targets.json --account mi.usuario --simulate
# Comprobar controles sin pulsarlos
python -m runner.cli --targets targets.json --account mi.usuario --dry-run --limit 5
# Ejecutar la cola revisada
python -m runner.cli --targets targets.json --account mi.usuario --execute --limit 20 --daily-limit 30 --interval 45
```

Contrato:

```json
{
  "version": 1,
  "platform": "instagram",
  "generatedAt": "2026-10-14T21:00:00Z",
  "demo": false,
  "targets": [
    {"username": "cuenta_x", "profileUrl": "https://www.instagram.com/cuenta_x/", "followsYou": false}
  ]
}
```

La automatización usa un perfil persistente y localizadores por rol de [Playwright](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context). Consulta también su [documentación de autenticación](https://playwright.dev/python/docs/auth).
