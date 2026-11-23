import type { Platform } from './parser';

/** Archivo de texto extraído de un ZIP. */
export type ZipTextEntry = { path: string; name: string; text: string };

const EOCD_SIGNATURE = 0x06054b50;
const ZIP64_LOCATOR_SIGNATURE = 0x07064b50;
const ZIP64_EOCD_SIGNATURE = 0x06064b50;
const CENTRAL_SIGNATURE = 0x02014b50;
const LOCAL_SIGNATURE = 0x04034b50;
const MAX_EOCD_SEARCH = 22 + 0xffff;
const MAX_ENTRY_BYTES = 60_000_000;
const UINT32_MAX = 0xffffffff;

type CentralEntry = {
  path: string;
  method: number;
  encrypted: boolean;
  compressedSize: number;
  uncompressedSize: number;
  localOffset: number;
};

async function readBytes(file: Blob, start: number, end: number): Promise<DataView> {
  const buffer = await file.slice(start, end).arrayBuffer();
  return new DataView(buffer);
}

/** Localiza el registro final del directorio central (incluye ZIP64 para exportaciones grandes). */
async function readDirectoryLocation(file: Blob): Promise<{ offset: number; size: number; count: number }> {
  const tailStart = Math.max(0, file.size - MAX_EOCD_SEARCH);
  const tail = await readBytes(file, tailStart, file.size);
  let eocd = -1;
  for (let i = tail.byteLength - 22; i >= 0; i -= 1) {
    if (tail.getUint32(i, true) === EOCD_SIGNATURE) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) throw new Error('El archivo no es un ZIP válido o está dañado.');
  let count = tail.getUint16(eocd + 10, true);
  let size = tail.getUint32(eocd + 12, true);
  let offset = tail.getUint32(eocd + 16, true);

  if (offset === UINT32_MAX || size === UINT32_MAX || count === 0xffff) {
    const locator = eocd - 20;
    if (locator < 0 || tail.getUint32(locator, true) !== ZIP64_LOCATOR_SIGNATURE) {
      throw new Error('ZIP64 incompleto: no se encontró el localizador.');
    }
    const zip64Offset = Number(tail.getBigUint64(locator + 8, true));
    const record = await readBytes(file, zip64Offset, zip64Offset + 56);
    if (record.getUint32(0, true) !== ZIP64_EOCD_SIGNATURE) throw new Error('ZIP64 dañado.');
    count = Number(record.getBigUint64(32, true));
    size = Number(record.getBigUint64(40, true));
    offset = Number(record.getBigUint64(48, true));
  }
  return { offset, size, count };
}

/** Aplica los tamaños de 64 bits del campo extra ZIP64 cuando la cabecera trae 0xFFFFFFFF. */
function applyZip64Extra(view: DataView, start: number, length: number, entry: CentralEntry) {
  let cursor = start;
  const end = start + length;
  while (cursor + 4 <= end) {
    const id = view.getUint16(cursor, true);
    const size = view.getUint16(cursor + 2, true);
    if (id === 0x0001) {
      let field = cursor + 4;
      if (entry.uncompressedSize === UINT32_MAX) { entry.uncompressedSize = Number(view.getBigUint64(field, true)); field += 8; }
      if (entry.compressedSize === UINT32_MAX) { entry.compressedSize = Number(view.getBigUint64(field, true)); field += 8; }
      if (entry.localOffset === UINT32_MAX) { entry.localOffset = Number(view.getBigUint64(field, true)); }
      return;
    }
    cursor += 4 + size;
  }
}

async function readCentralDirectory(file: Blob): Promise<CentralEntry[]> {
  const { offset, size, count } = await readDirectoryLocation(file);
  if (offset + size > file.size) throw new Error('El índice del ZIP apunta fuera del archivo.');
  const view = await readBytes(file, offset, offset + size);
  const utf8 = new TextDecoder('utf-8');
  const entries: CentralEntry[] = [];
  let cursor = 0;
  for (let i = 0; i < count && cursor + 46 <= view.byteLength; i += 1) {
    if (view.getUint32(cursor, true) !== CENTRAL_SIGNATURE) throw new Error('El índice del ZIP está dañado.');
    const flags = view.getUint16(cursor + 8, true);
    const nameLength = view.getUint16(cursor + 28, true);
    const extraLength = view.getUint16(cursor + 30, true);
    const commentLength = view.getUint16(cursor + 32, true);
    const nameBytes = new Uint8Array(view.buffer, view.byteOffset + cursor + 46, nameLength);
    const entry: CentralEntry = {
      path: utf8.decode(nameBytes).replace(/\\/g, '/'),
      method: view.getUint16(cursor + 10, true),
      encrypted: (flags & 0x1) === 0x1,
      compressedSize: view.getUint32(cursor + 20, true),
      uncompressedSize: view.getUint32(cursor + 24, true),
      localOffset: view.getUint32(cursor + 42, true),
    };
    applyZip64Extra(view, cursor + 46 + nameLength, extraLength, entry);
    entries.push(entry);
    cursor += 46 + nameLength + extraLength + commentLength;
  }
  return entries;
}

/** Descomprime una entrada en memoria usando DecompressionStream nativo del navegador. */
async function readEntryText(file: Blob, entry: CentralEntry): Promise<string> {
  if (entry.encrypted) throw new Error(`${entry.path}: el ZIP está protegido con contraseña.`);
  if (entry.uncompressedSize > MAX_ENTRY_BYTES) throw new Error(`${entry.path}: supera 60 MB descomprimido.`);
  const header = await readBytes(file, entry.localOffset, entry.localOffset + 30);
  if (header.getUint32(0, true) !== LOCAL_SIGNATURE) throw new Error(`${entry.path}: cabecera local dañada.`);
  const dataStart = entry.localOffset + 30 + header.getUint16(26, true) + header.getUint16(28, true);
  const compressed = file.slice(dataStart, dataStart + entry.compressedSize);
  if (entry.method === 0) return new TextDecoder('utf-8').decode(await compressed.arrayBuffer());
  if (entry.method !== 8) throw new Error(`${entry.path}: método de compresión no compatible.`);
  const stream = compressed.stream().pipeThrough(new DecompressionStream('deflate-raw'));
  return new Response(stream).text();
}

const baseName = (path: string) => path.split('/').filter(Boolean).pop() || path;

/** Indica si una ruta del ZIP contiene listas de seguidos/seguidores útiles para la red elegida. */
export function isRelevantExportEntry(path: string, platform: Platform): boolean {
  const normalized = path.toLowerCase();
  if (normalized.endsWith('/') || normalized.startsWith('__macosx/') || normalized.includes('/__macosx/')) return false;
  const name = baseName(normalized);
  if (platform === 'instagram') return /^following\.json$/.test(name) || /^followers(_\d+)?\.json$/.test(name);
  if (platform === 'tiktok') {
    if (/\.json$/.test(name)) return /user_data|following|follower/.test(name);
    return /\.(txt|csv)$/.test(name) && /(following|follower|fans)/.test(name);
  }
  return /\.(json|txt|csv)$/.test(name) && /follow/.test(name);
}

/** Extrae del ZIP solo los archivos de listas relevantes, sin escribir nada en disco. */
export async function extractExportEntries(file: Blob, platform: Platform): Promise<ZipTextEntry[]> {
  const entries = (await readCentralDirectory(file)).filter(entry => isRelevantExportEntry(entry.path, platform));
  const results: ZipTextEntry[] = [];
  for (const entry of entries) {
    results.push({ path: entry.path, name: baseName(entry.path), text: await readEntryText(file, entry) });
  }
  return results;
}
