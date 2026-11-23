export type Platform = 'instagram' | 'tiktok' | 'facebook';
export type Relation = 'following' | 'followers';
export type Person = { username: string; profileUrl: string; followsYou: boolean | null };
export type Lists = { following: Map<string, Person>; followers: Set<string>; hasFollowers: boolean; hasFollowing: boolean; files: string[] };
export const blankLists = (): Lists => ({ following: new Map(), followers: new Set(), hasFollowers: false, hasFollowing: false, files: [] });
const hosts: Record<Platform, string> = { instagram: 'www.instagram.com', tiktok: 'www.tiktok.com', facebook: 'www.facebook.com' };
const names: Record<Platform, RegExp> = { instagram: /^[a-z0-9._]{1,30}$/i, tiktok: /^[a-z0-9._]{1,32}$/i, facebook: /^[a-z0-9._-]{1,100}$/i };

export function person(raw: string, platform: Platform, href?: string): Person | null {
  let username = raw.trim().replace(/^@/, '');
  let profileUrl = '';
  const candidate = href || (/^https?:\/\//i.test(username) ? username : '');
  if (candidate) {
    try {
      const u = new URL(candidate);
      if (!['https:', 'http:'].includes(u.protocol) || u.username || u.password || ![hosts[platform], hosts[platform].replace('www.', '')].includes(u.hostname)) return null;
      if (platform === 'facebook' && u.pathname === '/profile.php' && /^\d+$/.test(u.searchParams.get('id') || '')) {
        username = u.searchParams.get('id')!;
        profileUrl = `https://${hosts[platform]}/profile.php?id=${username}`;
      } else {
        const parts = u.pathname.split('/').filter(Boolean);
        if (platform === 'instagram' && parts[0] === '_u') parts.shift();
        if (parts.length !== 1) return null;
        username = decodeURIComponent(parts[0]).replace(/^@/, '');
      }
    } catch { return null; }
  }
  if (!names[platform].test(username) || ['explore', 'accounts', 'reels', 'stories', 'login', 'settings', 'home', 'watch', 'groups', 'friends'].includes(username.toLowerCase())) return null;
  username = username.toLowerCase();
  return { username, profileUrl: profileUrl || `https://${hosts[platform]}/${platform === 'tiktok' ? '@' : ''}${username}/`, followsYou: null };
}

export type ParsedSection = { relation: Relation; people: Person[]; demo: boolean };

function extractPeopleFromRows(rows: unknown[], platform: Platform): Person[] {
  const people: Person[] = [];
  for (const row of rows) {
    const item: any = row;
    const entries = item?.string_list_data;
    const candidates = Array.isArray(entries) && entries.length
      ? entries.map((e: any) => ({ username: e.value || item.title, href: e.href }))
      : [{
          username: typeof item === 'string' ? item : item?.username || item?.UserName || item?.Username || item?.title || item?.name,
          href: item?.profileUrl || item?.href || item?.uri || item?.URL || item?.Url,
        }];
    for (const c of candidates) {
      const p = person(String(c.username || c.href || ''), platform, c.href);
      if (p) people.push(p);
    }
  }
  return people;
}

/** Extrae listas combinadas de exportaciones oficiales de TikTok (user_data_tiktok.json). */
function extractTikTokCombinedSections(data: any, platform: Platform): ParsedSection[] {
  const activity = data?.Activity || data?.['Your Activity'];
  const profile = data?.Profile || data?.['Profile And Settings'] || data?.['Profile and Settings'];
  const followingRows =
    activity?.['Following List']?.Following ||
    activity?.['Following List']?.List ||
    activity?.Following?.['Following List'] ||
    profile?.['Following List']?.Following ||
    profile?.['Following List']?.List ||
    data?.['Following List']?.Following ||
    data?.['Following List']?.List ||
    data?.Following?.['Following List'];
  const followerRows =
    activity?.['Follower List']?.FansList ||
    activity?.['Follower List']?.List ||
    activity?.Follower?.FansList ||
    profile?.['Follower List']?.FansList ||
    profile?.['Follower List']?.List ||
    data?.['Follower List']?.FansList ||
    data?.['Follower List']?.List ||
    data?.Follower?.FansList;

  const sections: ParsedSection[] = [];
  if (Array.isArray(followingRows)) {
    sections.push({ relation: 'following', people: extractPeopleFromRows(followingRows, platform), demo: false });
  }
  if (Array.isArray(followerRows)) {
    sections.push({ relation: 'followers', people: extractPeopleFromRows(followerRows, platform), demo: false });
  }
  return sections;
}

/** Analiza un archivo de exportación y devuelve una o más secciones (soporta archivos combinados de TikTok). */
export function parseExportSections(text: string, filename: string, platform: Platform, fallback?: Relation): ParsedSection[] {
  const file = filename.toLowerCase();
  if (file.endsWith('.json') && platform === 'tiktok') {
    let data: any;
    try { data = JSON.parse(text.replace(/^\uFEFF/, '')); } catch { throw new Error(`${filename}: el JSON no es válido.`); }
    if (data.platform && data.platform !== platform) throw new Error(`${filename}: pertenece a ${data.platform}. Cambia la red antes de importarlo.`);
    const combined = extractTikTokCombinedSections(data, platform);
    if (combined.length > 0) {
      if (!combined.some(section => section.people.length > 0) && combined.length > 0) {
        // Permite listas legítimamente vacías cuando el JSON sí tenía la estructura oficial.
        return combined;
      }
      return combined;
    }
  }
  return [parseExport(text, filename, platform, fallback)];
}

export function parseExport(text: string, filename: string, platform: Platform, fallback?: Relation): ParsedSection {
  const file = filename.toLowerCase();
  let relation: Relation | undefined = /following|siguiendo/.test(file) ? 'following' : /follower|seguidores/.test(file) ? 'followers' : fallback;
  let rows: unknown[] | undefined;
  let data: any;
  if (file.endsWith('.json')) {
    try { data = JSON.parse(text.replace(/^\uFEFF/, '')); } catch { throw new Error(`${filename}: el JSON no es válido.`); }
    if (data.platform && data.platform !== platform) throw new Error(`${filename}: pertenece a ${data.platform}. Cambia la red antes de importarlo.`);
    if (data.relationships_following) { relation = 'following'; rows = data.relationships_following; }
    else if (data.relationships_followers) { relation = 'followers'; rows = data.relationships_followers; }
    else if (data.targets) { relation = 'following'; rows = data.targets; }
    else if (data['Following List']?.List || data['Following List']?.Following || data.Following?.['Following List']) { relation = 'following'; rows = data['Following List']?.List || data['Following List']?.Following || data.Following['Following List']; }
    else if (data['Follower List']?.List || data['Follower List']?.FansList || data.Follower?.['FansList']) { relation = 'followers'; rows = data['Follower List']?.List || data['Follower List']?.FansList || data.Follower['FansList']; }
    else if (data.Activity?.['Following List']?.List || data.Activity?.['Follower List']?.List) {
      if (data.Activity['Following List'] && data.Activity['Follower List']) throw new Error('Este archivo contiene ambas listas. Exporta cada lista por separado.');
      relation = data.Activity['Following List'] ? 'following' : 'followers'; rows = data.Activity[relation === 'following' ? 'Following List' : 'Follower List'].List;
    }
    else if (Array.isArray(data)) rows = data;
    else if (Array.isArray(data.following)) { relation = 'following'; rows = data.following; }
    else if (Array.isArray(data.followers)) { relation = 'followers'; rows = data.followers; }
    else throw new Error(`${filename}: formato no reconocido. Usa JSON de Instagram o una lista TXT/CSV de usuarios.`);
  } else if (/\.(txt|csv)$/i.test(file)) {
    rows = text.replace(/^\uFEFF/, '').split(/\r?\n/).map(line => line.trim()).filter(line => line && !/^(date|fecha)\s*:/i.test(line)).map(line => line.replace(/^(username|nombre de usuario)\s*:\s*/i, '').split(/[,;\t]/)[0].replace(/^"|"$/g, '')).filter(line => !/^(username|usuario|profileurl|url)$/i.test(line));
  } else throw new Error('Descomprime tu exportación y elige archivos JSON, TXT o CSV.');
  if (!relation) throw new Error(`${filename}: elige si contiene las cuentas que sigues o tus seguidores.`);
  if (!Array.isArray(rows)) throw new Error(`${filename}: no se encontró una lista de cuentas.`);
  const people = extractPeopleFromRows(rows, platform);
  if (rows.length && !people.length) throw new Error(`${filename}: no se reconocieron usuarios de ${platform}. Revisa el formato o la red seleccionada.`);
  return { relation, people, demo: data?.demo === true };
}

export function mergeFiles(base: Lists, parsed: { name: string; relation: Relation; people: Person[] }[]): Lists {
  const next: Lists = { following: new Map(base.following), followers: new Set(base.followers), hasFollowers: base.hasFollowers, hasFollowing: base.hasFollowing, files: [...base.files] };
  for (const { name, relation, people } of parsed) {
    if (relation === 'followers') { next.hasFollowers = true; people.forEach(p => next.followers.add(p.username)); }
    else { next.hasFollowing = true; people.forEach(p => next.following.set(p.username, p)); }
    if (!next.files.includes(name)) next.files.push(name);
  }
  for (const [key, p] of next.following) next.following.set(key, { ...p, followsYou: next.hasFollowers ? next.followers.has(key) : null });
  return next;
}

export function demoLists(platform: Platform): Lists {
  const handles = ['estudio.norte', 'cafe.con.codigo', 'viajes.lentos', 'diseno.diario', 'pixel.colectivo', 'daniel.crea', 'el.buen.cafe', 'luz.y.forma', 'codigo.abierto', 'ana.ilustra', 'club.creativo', 'archivo.digital'];
  return mergeFiles(blankLists(), [
    { name: 'following_ejemplo.json', relation: 'following', people: handles.map(h => person(h, platform)!) },
    { name: 'followers_ejemplo.json', relation: 'followers', people: handles.slice(8).map(h => person(h, platform)!) }
  ]);
}
