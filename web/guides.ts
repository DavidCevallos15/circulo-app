import type { Platform } from './parser';

export type GuideStep = {
  title: string;
  detail: string;
};

export type PlatformGuide = {
  name: string;
  estimatedTime: string;
  filesHint: string;
  steps: GuideStep[];
  quickTip: string;
};

/** Guías paso a paso por red social para solicitar y descargar la exportación oficial en formato JSON. */
export const PLATFORM_GUIDES: Record<Platform, PlatformGuide> = {
  instagram: {
    name: 'Instagram',
    estimatedTime: '5 a 15 minutos',
    filesHint: 'Archivo ZIP oficial de Meta (directo) o following.json + followers_*.json',
    steps: [
      {
        title: 'Abre el Centro de cuentas de Meta',
        detail: 'En Instagram ve a Configuración → Centro de cuentas → Tu información y tus permisos → Exportar tu información.',
      },
      {
        title: 'Elige solo tu cuenta e información parcial',
        detail: 'Selecciona únicamente tu perfil de Instagram y marca "Información parcial" (no descargues toda tu información).',
      },
      {
        title: 'Marca "Seguidores y seguidos"',
        detail: 'Selecciona solo la casilla de Seguidores y seguidos y elige "Descargar al dispositivo".',
      },
      {
        title: 'Configura JSON y "Desde el principio"',
        detail: 'Cambia el rango de fechas a "Desde el principio", el formato a JSON (no HTML) y calidad multimedia en Baja. Pulsa Crear archivos.',
      },
      {
        title: 'Arrastra el ZIP directo a Círculo',
        detail: 'Cuando descargues el archivo .zip, suéltalo tal cual en Círculo: extrae automáticamente following.json y todos los followers_*.json en memoria.',
      },
    ],
    quickTip: 'No hace falta descomprimir el ZIP: Círculo lee en memoria solo las listas de seguidores y seguidos sin tocar el resto del archivo.',
  },
  tiktok: {
    name: 'TikTok',
    estimatedTime: 'Algunas horas hasta 24 h',
    filesHint: 'Archivo ZIP oficial de TikTok (directo), user_data_tiktok.json o listas TXT/CSV',
    steps: [
      {
        title: 'Entra a Descargar tus datos',
        detail: 'En TikTok Web o la app móvil ve a Ajustes → Privacidad (o Cuenta) → Descargar tus datos.',
      },
      {
        title: 'Cambia el formato a JSON',
        detail: 'En "Select file format" cambia de TXT a JSON antes de enviar la solicitud.',
      },
      {
        title: 'Selecciona solo Profile and Settings y Your Activity',
        detail: 'Desmarca mensajes, comentarios y publicaciones para que TikTok genere el archivo mucho más rápido.',
      },
      {
        title: 'Solicita y descarga el ZIP',
        detail: 'Pulsa "Request data". Cuando pase de Pending a Download en la pestaña "Download data", descarga el ZIP.',
      },
      {
        title: 'Arrastra el ZIP o el JSON directo a Círculo',
        detail: 'Suelta el archivo .zip o user_data_tiktok.json en la pestaña TikTok: Círculo lee ambas listas automáticamente.',
      },
    ],
    quickTip: '¿Quieres probar hoy sin esperar? Crea un archivo siguiendo.txt con 1 usuario (o URL de perfil) por línea y súbelo en la pestaña TikTok.',
  },
  facebook: {
    name: 'Facebook',
    estimatedTime: '10 a 30 minutos',
    filesHint: 'Archivos JSON con URLs de perfiles o listas TXT/CSV con una URL por línea',
    steps: [
      {
        title: 'Abre Exportar tu información en Meta',
        detail: 'Ve a Configuración y privacidad → Configuración → Centro de cuentas → Tu información y tus permisos → Exportar tu información.',
      },
      {
        title: 'Selecciona solo tu perfil de Facebook',
        detail: 'Elige "Información parcial" y marca únicamente las secciones de páginas/perfiles que sigues y seguidores.',
      },
      {
        title: 'Usa formato JSON y rango completo',
        detail: 'Selecciona "Descargar al dispositivo", rango "Desde el principio" y formato JSON.',
      },
      {
        title: 'Importa URLs de perfiles (no nombres sueltos)',
        detail: 'Círculo trabaja únicamente con enlaces exactos de perfil para dejar de seguir o quitar de amigos (beta). El archivo your_friends.json de Meta solo trae nombres y no permite identificar perfiles sin ambigüedad.',
      },
    ],
    quickTip: 'Por defecto Facebook usa el botón explícito Siguiendo. Si eliges "Quitar de amigos (beta)" en el panel de ejecución, prepara una lista TXT/CSV con las URLs exactas de esos perfiles.',
  },
};
