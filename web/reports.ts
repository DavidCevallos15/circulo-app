import type { Lists, Person, Platform } from './parser';

export type ReportRow = {
  username: string;
  profileUrl: string;
  category: 'not-following' | 'mutual' | 'fan' | 'unknown';
  categoryLabel: string;
  protected: boolean;
  selected: boolean;
};

export type ReportSummary = {
  platform: Platform;
  account: string;
  generatedAt: string;
  totalFollowing: number;
  totalFollowers: number;
  hasFollowers: boolean;
  notFollowing: number;
  mutual: number;
  fans: number;
  unknown: number;
  protectedCount: number;
  selectedCount: number;
  rows: ReportRow[];
};

const PLATFORM_LABELS: Record<Platform, string> = {
  instagram: 'Instagram',
  tiktok: 'TikTok',
  facebook: 'Facebook',
};

const PLATFORM_HOSTS: Record<Platform, string> = {
  instagram: 'www.instagram.com',
  tiktok: 'www.tiktok.com',
  facebook: 'www.facebook.com',
};

/** Construye la URL canónica de un perfil según la red social. */
export function buildProfileUrl(username: string, platform: Platform): string {
  if (platform === 'facebook' && /^\d+$/.test(username)) {
    return `https://${PLATFORM_HOSTS.facebook}/profile.php?id=${username}`;
  }
  return `https://${PLATFORM_HOSTS[platform]}/${platform === 'tiktok' ? '@' : ''}${username}/`;
}

/** Obtiene la lista de seguidores que el usuario no sigue de vuelta ("solo te siguen"). */
export function getFanPeople(lists: Lists, platform: Platform): Person[] {
  if (!lists.hasFollowers) return [];
  const fans: Person[] = [];
  for (const username of lists.followers) {
    if (!lists.following.has(username)) {
      fans.push({
        username,
        profileUrl: buildProfileUrl(username, platform),
        followsYou: true,
      });
    }
  }
  return fans;
}

/** Construye el resumen estructurado y todas las filas del reporte de conexiones. */
export function buildReportSummary(
  lists: Lists,
  platform: Platform,
  account: string,
  protectedUsers: Set<string>,
  selected: Set<string>,
): ReportSummary {
  const rows: ReportRow[] = [];
  let notFollowing = 0;
  let mutual = 0;
  let unknown = 0;

  for (const person of lists.following.values()) {
    const isProtected = protectedUsers.has(person.username);
    const isSelected = selected.has(person.username) && !isProtected;
    if (person.followsYou === false) {
      notFollowing += 1;
      rows.push({
        username: person.username,
        profileUrl: person.profileUrl,
        category: 'not-following',
        categoryLabel: 'No te sigue',
        protected: isProtected,
        selected: isSelected,
      });
    } else if (person.followsYou === true) {
      mutual += 1;
      rows.push({
        username: person.username,
        profileUrl: person.profileUrl,
        category: 'mutual',
        categoryLabel: 'Conexión mutua',
        protected: isProtected,
        selected: isSelected,
      });
    } else {
      unknown += 1;
      rows.push({
        username: person.username,
        profileUrl: person.profileUrl,
        category: 'unknown',
        categoryLabel: 'Sin comprobar',
        protected: isProtected,
        selected: isSelected,
      });
    }
  }

  const fans = getFanPeople(lists, platform);
  for (const fan of fans) {
    rows.push({
      username: fan.username,
      profileUrl: fan.profileUrl,
      category: 'fan',
      categoryLabel: 'Solo te sigue',
      protected: protectedUsers.has(fan.username),
      selected: false,
    });
  }

  return {
    platform,
    account: account.trim().replace(/^@/, '') || 'sin-especificar',
    generatedAt: new Date().toISOString(),
    totalFollowing: lists.following.size,
    totalFollowers: lists.followers.size,
    hasFollowers: lists.hasFollowers,
    notFollowing,
    mutual,
    fans: fans.length,
    unknown,
    protectedCount: protectedUsers.size,
    selectedCount: rows.filter(r => r.selected).length,
    rows,
  };
}

/** Escapa una celda CSV y neutraliza caracteres de inyección de fórmulas en hojas de cálculo. */
function escapeCsvCell(value: string): string {
  const safe = /^[=+\-@\t\r]/.test(value) ? `'${value}` : value;
  return `"${safe.replace(/"/g, '""')}"`;
}

/** Genera un reporte CSV con BOM UTF-8 compatible con Excel y Google Sheets. */
export function buildCsvReport(summary: ReportSummary): string {
  const header = ['Usuario', 'URL', 'Relación', 'Protegida', 'Seleccionada para dejar de seguir'];
  const lines = [
    header.map(escapeCsvCell).join(','),
    ...summary.rows.map(row =>
      [
        row.username,
        row.profileUrl,
        row.categoryLabel,
        row.protected ? 'Sí' : 'No',
        row.selected ? 'Sí' : 'No',
      ]
        .map(escapeCsvCell)
        .join(','),
    ),
  ];
  return `\uFEFF${lines.join('\r\n')}`;
}

/** Escapa caracteres especiales para evitar inyección HTML/XSS en reportes exportados. */
function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** Genera un reporte HTML autónomo y listo para abrir o imprimir en cualquier navegador. */
export function buildHtmlReport(summary: ReportSummary): string {
  const dateLabel = new Date(summary.generatedAt).toLocaleString('es', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
  const platformName = PLATFORM_LABELS[summary.platform];
  const tableRows = summary.rows
    .map(
      row =>
        `<tr><td><a href="${escapeHtml(row.profileUrl)}" target="_blank" rel="noreferrer">@${escapeHtml(row.username)}</a></td><td><span class="tag ${row.category}">${escapeHtml(row.categoryLabel)}</span></td><td>${row.protected ? 'Sí' : '—'}</td><td>${row.selected ? 'Sí' : '—'}</td></tr>`,
    )
    .join('');

  return `<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reporte Círculo · ${escapeHtml(platformName)} · @${escapeHtml(summary.account)}</title>
<style>
  body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#f7f8f4;color:#24352a;margin:0;padding:32px 20px;line-height:1.5}
  main{max-width:960px;margin:auto;background:#fff;border:1px solid #e2e6de;border-radius:12px;padding:32px}
  h1{margin:0 0 6px;font-size:24px;letter-spacing:-.02em}
  .meta{color:#657268;font-size:13px;margin:0 0 24px}
  .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:12px;margin-bottom:26px}
  .stat{background:#f7f8f4;border:1px solid #e2e6de;border-radius:8px;padding:14px}
  .stat span{display:block;font-size:11px;color:#657268}
  .stat strong{font-size:22px;font-variant-numeric:tabular-nums}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th{text-align:left;background:#f0f3eb;color:#546647;padding:10px 12px;font-size:11px;text-transform:uppercase;letter-spacing:.03em}
  td{padding:10px 12px;border-top:1px solid #e9ece5}
  a{color:#24352a;font-weight:600;text-decoration:none}
  a:hover{text-decoration:underline}
  .tag{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600}
  .not-following{background:#f5eae2;color:#7c603b}
  .mutual{background:#e2ebd5;color:#4c6c36}
  .fan{background:#e4eef2;color:#355d73}
  .unknown{background:#edf0eb;color:#6b7866}
  @media print{body{background:#fff;padding:0}main{border:0;padding:0}}
</style>
</head>
<body>
<main>
  <h1>Reporte de conexiones · ${escapeHtml(platformName)}</h1>
  <p class="meta">Cuenta: @${escapeHtml(summary.account)} · Generado: ${escapeHtml(dateLabel)} · Procesado 100% localmente con Círculo</p>
  <section class="stats">
    <div class="stat"><span>Siguiendo</span><strong>${summary.totalFollowing}</strong></div>
    <div class="stat"><span>No te siguen</span><strong>${summary.hasFollowers ? summary.notFollowing : '—'}</strong></div>
    <div class="stat"><span>Mutuas</span><strong>${summary.hasFollowers ? summary.mutual : '—'}</strong></div>
    <div class="stat"><span>Solo te siguen</span><strong>${summary.hasFollowers ? summary.fans : '—'}</strong></div>
    <div class="stat"><span>Protegidas</span><strong>${summary.protectedCount}</strong></div>
    <div class="stat"><span>Seleccionadas</span><strong>${summary.selectedCount}</strong></div>
  </section>
  <table>
    <thead><tr><th>Cuenta</th><th>Relación</th><th>Protegida</th><th>Seleccionada</th></tr></thead>
    <tbody>${tableRows}</tbody>
  </table>
</main>
</body>
</html>`;
}
