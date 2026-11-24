# Validación de Círculo

Última verificación: **23 de noviembre de 2026** · versión **0.4.0** · Windows 11, Python 3.14, Node 24, Playwright 1.64 (Chromium de Playwright).

## Pruebas automatizadas

| Suite | Comando | Resultado |
|---|---|---|
| Parser y reportes (TypeScript) | `npm test` | 7/7 OK — cruce Instagram, archivos fragmentados, relación desconocida, TikTok TXT/JSON combinado, ZIP en memoria, detección del modo web público |
| Compilación | `npm run build` | `tsc -b` + Vite sin errores |
| Ejecutor (Python) | `python -m unittest discover -s tests -p "test_*.py"` | 20/20 OK — persistencia, recuperación tras interrupción, presupuesto de intentos, importación atómica, aislamiento de procesos, pausa, simulación, protección de la API local (Host/Origin/token), programación, updater (HTTPS, allowlist, semver, manifiestos, SHA-256) |
| Navegador end-to-end | `python tests/browser_smoke.py` | 58/58 OK, 0 errores JS — modo local y `?mode=web` a 1440, 768, 390 y 320 px; CTA de descarga gratis; adaptadores IG/TikTok/Facebook contra fixtures HTML controladas |

Las pruebas de navegador levantan un servidor en un puerto temporal con una base de datos temporal y **no** acceden a cuentas reales.

## Validación en sesión real

| Red | Estado | Detalle |
|---|---|---|
| Instagram | Validado | Botón `Siguiendo`/`Following` con icono `chevron`, diálogo asíncrono `Dejar de seguir`, verificación de la cuenta autenticada antes de ejecutar |
| TikTok | Selectores validados | Botón del encabezado `button[data-e2e="follow-button"][aria-haspopup="dialog"]`, verificación vía `a[data-e2e="nav-profile"]` |
| Facebook | Beta | Dejar de seguir y Quitar de amigos con URLs exactas; la verificación de cuenta depende de los accesos directos |

Las interfaces de las plataformas cambian sin aviso: un selector validado hoy puede dejar de funcionar. Ante cualquier resultado ambiguo, captcha, login o aviso de límite, el motor **se detiene** en lugar de reintentar.

## Paquete portable Windows

`packaging/build_windows.ps1` genera `release/Circulo-<versión>-win64.zip` y `release/SHA256SUMS.txt` (Chromium incluido, sin Python ni Node para el usuario final). La huella publicada en cada GitHub Release es la referencia para verificar la descarga.

Build 0.4.0 (23-nov-2026): `Circulo-0.4.0-win64.zip` de 366 MB (847 MB descomprimido), SHA-256 `e8936a988827a3782e483a1973b0214f0e16c4c99fb52e5e5bd9931d7e505060`. Prueba de humo del ZIP extraído: `Circulo.exe --no-open --port 8799` responde `GET /` 200, `GET /api/status` 200 con `version: 0.4.0`, `GET /api/update` sin errores, y el paquete incluye `chromium-1248` y `chromium_headless_shell-1248`.

El binario 0.4.0 **no está firmado** con Authenticode; SmartScreen mostrará una advertencia hasta configurar un certificado de firma de código (`CIRCULO_SIGN_THUMBPRINT` o `CIRCULO_SIGN_PFX`).

## Repetir

```powershell
npm ci
npm test
npm run build
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
.\.venv\Scripts\python.exe tests/browser_smoke.py
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
```
