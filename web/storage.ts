import { blankLists, type Lists, type Person, type Platform } from './parser';

const PLATFORMS: Platform[] = ['instagram', 'tiktok', 'facebook'];

type SerializedLists = {
  following: [string, Person][];
  followers: string[];
  hasFollowers: boolean;
  hasFollowing: boolean;
  files: string[];
};

/** Lee un conjunto de usuarios protegidos desde localStorage para una red social. */
export function loadProtected(platform: Platform): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(`circulo.protected.${platform}`) || '[]'));
  } catch {
    return new Set();
  }
}

/** Guarda el conjunto de usuarios protegidos en localStorage para una red social. */
export function saveProtected(platform: Platform, users: Set<string>): void {
  try {
    localStorage.setItem(`circulo.protected.${platform}`, JSON.stringify([...users]));
  } catch {
    // Ignoramos errores de cuota o modo privado del navegador.
  }
}

/** Lee el nombre de cuenta local guardado para una red social. */
export function loadAccount(platform: Platform): string {
  try {
    return localStorage.getItem(`circulo.account.${platform}`) || '';
  } catch {
    return '';
  }
}

/** Guarda el nombre de cuenta local para una red social. */
export function saveAccount(platform: Platform, account: string): void {
  try {
    localStorage.setItem(`circulo.account.${platform}`, account);
  } catch {
    // Ignoramos errores de cuota o modo privado del navegador.
  }
}

/** Carga las listas importadas desde sessionStorage para mantenerlas al cambiar de red o recargar. */
export function loadSessionLists(platform: Platform): Lists {
  try {
    const raw = sessionStorage.getItem(`circulo.lists.${platform}`);
    if (!raw) return blankLists();
    const parsed = JSON.parse(raw) as SerializedLists;
    return {
      following: new Map(parsed.following || []),
      followers: new Set(parsed.followers || []),
      hasFollowers: Boolean(parsed.hasFollowers),
      hasFollowing: Boolean(parsed.hasFollowing),
      files: Array.isArray(parsed.files) ? parsed.files : [],
    };
  } catch {
    return blankLists();
  }
}

/** Persiste las listas reales de una red social en sessionStorage (nunca guarda datos de ejemplo). */
export function saveSessionLists(platform: Platform, lists: Lists, isDemo: boolean): void {
  try {
    if (isDemo || !lists.files.length) {
      sessionStorage.removeItem(`circulo.lists.${platform}`);
      return;
    }
    const payload: SerializedLists = {
      following: [...lists.following.entries()],
      followers: [...lists.followers],
      hasFollowers: lists.hasFollowers,
      hasFollowing: lists.hasFollowing,
      files: lists.files,
    };
    sessionStorage.setItem(`circulo.lists.${platform}`, JSON.stringify(payload));
  } catch {
    // Si las listas exceden el límite de sessionStorage, permanecen en memoria sin interrumpir el flujo.
  }
}

/** Inicializa los mapas de estado por red social para evitar perder datos al cambiar de pestaña. */
export function createInitialListsByPlatform(): Record<Platform, Lists> {
  return {
    instagram: loadSessionLists('instagram'),
    tiktok: loadSessionLists('tiktok'),
    facebook: loadSessionLists('facebook'),
  };
}

export function createInitialSelectedByPlatform(): Record<Platform, Set<string>> {
  return { instagram: new Set(), tiktok: new Set(), facebook: new Set() };
}

export function createInitialDemoByPlatform(): Record<Platform, boolean> {
  return { instagram: false, tiktok: false, facebook: false };
}

export function createInitialProtectedByPlatform(): Record<Platform, Set<string>> {
  return Object.fromEntries(PLATFORMS.map(p => [p, loadProtected(p)])) as Record<Platform, Set<string>>;
}

export function createInitialAccountsByPlatform(): Record<Platform, string> {
  return Object.fromEntries(PLATFORMS.map(p => [p, loadAccount(p)])) as Record<Platform, string>;
}
