/** Configuración del entorno de ejecución (app local vs. analizador web estático en GitHub Pages). */

export const APP_VERSION = typeof __APP_VERSION__ === 'string' && __APP_VERSION__ ? __APP_VERSION__ : '0.4.0';

const LOCAL_HOSTNAMES = new Set(['127.0.0.1', 'localhost', '::1', '[::1]']);

/**
 * Determina si la interfaz corre en modo analizador web público (sin servidor local de Python).
 * Se puede previsualizar localmente añadiendo ?mode=web a la URL.
 */
export function detectPublicWebMode(
  hostname: string = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1',
  search: string = typeof window !== 'undefined' ? window.location.search : '',
): boolean {
  const params = new URLSearchParams(search);
  const override = params.get('mode')?.trim().toLowerCase();
  if (override === 'web') return true;
  if (override === 'local') return false;
  if (!hostname) return false;
  return !LOCAL_HOSTNAMES.has(hostname.toLowerCase());
}

function resolveHttpsUrl(envValue: string | undefined, fallback: string): string {
  const candidate = envValue?.trim();
  if (!candidate) return fallback;
  try {
    const parsed = new URL(candidate);
    return parsed.protocol === 'https:' ? parsed.toString() : fallback;
  } catch {
    return fallback;
  }
}

export const PUBLIC_LINKS = {
  landingUrl: resolveHttpsUrl(import.meta.env?.VITE_LANDING_URL, 'https://www.davidcevallos.me/circulo/'),
  proUrl: resolveHttpsUrl(import.meta.env?.VITE_PRO_URL, 'https://www.davidcevallos.me/circulo/#reservar'),
  downloadUrl: resolveHttpsUrl(
    import.meta.env?.VITE_DOWNLOAD_URL,
    'https://www.davidcevallos.me/circulo/descargar/',
  ),
  repoUrl: resolveHttpsUrl(import.meta.env?.VITE_REPO_URL, 'https://github.com/DavidCevallos15/circulo-app'),
};
