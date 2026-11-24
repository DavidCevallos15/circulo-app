/**
 * Entrada publicada en personal_web/frontend/src/data/projects.ts (interfaz Project del portafolio DC.dev).
 * videoUrl ocupa la portada de la card con la demo de YouTube; demoUrl lleva a la landing con la descarga.
 */
export const circuloProjectEntry = {
  id: 'circulo',
  title: 'Círculo',
  summary:
    'Descubre quién no te sigue en Instagram, TikTok y Facebook con tu exportación oficial, sin entregar tu contraseña. Protege cuentas, exporta reportes y limpia tu cuenta con límites seguros. Gratis para Windows.',
  category: 'producto' as const,
  context: 'App local · Redes sociales',
  tags: ['React', 'TypeScript', 'Python', 'Playwright', 'SQLite'],
  videoUrl: 'https://youtu.be/Bxo4Vg8SQes',
  demoUrl: '/circulo/',
  demoLabel: 'Descargar gratis',
  status: 'en producción' as const,
};
