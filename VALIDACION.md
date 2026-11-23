# Validación de la primera versión

Fecha: 14 de octubre de 2026. Entorno: Windows, Python 3.12, Node 24, Playwright 1.64 y Chromium de Playwright.

- Compilación de TypeScript y Vite: correcta.
- 4 pruebas de importación: cruce de Instagram, archivos fragmentados, relación desconocida frente a seguidores vacíos, URLs ajenas, TikTok TXT/JSON, datos de ejemplo y formatos inválidos.
- 9 pruebas de Python: persistencia, recuperación tras interrupción, presupuesto de intentos, importación atómica, aislamiento de procesos, pausa, simulación y protección de API local.
- 21 comprobaciones en navegador: demo, protección de cuentas, selección, simulación completa, bloqueo de demo en modo real, búsqueda, paginación, cambio de red, importación múltiple, exportación de selección, confirmación con teclado, ausencia de desbordamiento móvil y errores JS, adaptadores con páginas de prueba y parada ante aviso simulado.
- Revisión visual de escritorio a 1440 px y móvil a 390 px. Comprobación de desbordamiento también a 1100 px. Ajustes de foco de teclado, tamaños de texto móvil y contraste.
- El analizador mecánico de estilos no detectó incidencias.
- Sintaxis del lanzador PowerShell y módulos Python: correcta.

## Repetir

```powershell
npm test
npm run build
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
.\.venv\Scripts\python.exe tests/browser_smoke.py
```

Las comprobaciones de navegador levantan un servidor en un puerto temporal con una base de datos temporal. No acceden a cuentas reales. Los adaptadores se ejercitan con páginas HTML interceptadas y controladas, no con las interfaces reales de las redes sociales.

## Pendiente de validación real

No se entregaron exportaciones reales ni sesiones autenticadas. **No se verificó ningún unfollow en Instagram, TikTok o Facebook.** El código de los adaptadores está implementado; sus selectores y la continuidad de sesión necesitan probarse con la cuenta del usuario. TikTok y Facebook se señalan como beta. La simulación no demuestra compatibilidad con las interfaces actuales de las plataformas.
