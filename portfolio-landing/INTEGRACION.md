# Integración de Círculo en `DavidCevallos15/personal_web` (`davidcevallos.me`)

Estado: **integrado** (23-nov-2026). Esta carpeta es la copia fuente de lo publicado en `personal_web/frontend/public/circulo/`.

| Ruta pública | Archivo | Propósito |
|---|---|---|
| `/circulo/` | `public/circulo/index.html` | Landing: descarga gratis, analizador web, reserva Pro ($9) y auditoría ($25+) con Web3Forms |
| `/circulo/descargar/` | `public/circulo/descargar/index.html` | Descarga del ZIP, huella SHA-256, requisitos, instalación, recomendaciones de uso seguro y FAQ |
| `/circulo/update.json` | `public/circulo/update.json` | Manifiesto opcional para el comprobador de actualizaciones (`CIRCULO_UPDATE_URL`) |

Todo cumple el `Content-Security-Policy` de `frontend/vercel.json`: cero scripts inline (`landing.js` externo), formulario a `api.web3forms.com` (en `connect-src`) y GTM desde `googletagmanager.com`.

## Publicar una nueva versión

1. Sube `version` en `package.json` y `runner/updater.py` (`DEFAULT_VERSION`).
2. `powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1 -RebuildWeb`
3. `gh release create vX.Y.Z release\Circulo-X.Y.Z-win64.zip release\SHA256SUMS.txt --title "Círculo X.Y.Z" --notes "..."`
4. En `public/circulo/descargar/index.html` y `update.json` actualiza versión, URL del ZIP, tamaño, fecha y SHA-256 (de `release/SHA256SUMS.txt`).
5. Copia esta carpeta a `personal_web/frontend/public/circulo/` y haz push.

## Eventos GA4 / GTM (`GTM-TP42PVRG`)

- `circulo_download_click` (`topbar`, `hero`, `pricing`): intención de descargar desde la landing.
- `circulo_download_file` (`topbar`, `hero`, `footer`): clic real en el ZIP en `/circulo/descargar/`.
- `circulo_try_free_click` (`topbar`, `hero`, `pricing`, `download`): analizador web.
- `circulo_pro_reserve_click` (`hero`, `pricing`, `download`): intención de Círculo Pro ($9 USD).
- `circulo_service_click`: auditoría hecha por ti / agencias ($25+).
- `generate_lead` (`plan_interest`, `network`, `value`): registros enviados por el formulario.
