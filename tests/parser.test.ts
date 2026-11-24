import { test } from 'node:test';
import assert from 'node:assert/strict';
import { deflateRawSync } from 'node:zlib';
import { blankLists, mergeFiles, parseExport, parseExportSections, person } from '../web/parser';
import { buildCsvReport, buildHtmlReport, buildReportSummary } from '../web/reports';
import { detectPublicWebMode } from '../web/runtime';
import { extractExportEntries } from '../web/zip';

test('Instagram: title-only following and multiple followers files are merged by username', () => {
  const following = parseExport(JSON.stringify({ relationships_following: [
    { title: 'Alice', string_list_data: [{ href: 'https://www.instagram.com/_u/alice', timestamp: 1 }] },
    { title: 'bob', string_list_data: [{ href: 'https://www.instagram.com/bob/', timestamp: 1 }] }
  ] }), 'following.json', 'instagram');
  const followers1 = parseExport(JSON.stringify([{ string_list_data: [{ value: 'ALICE', href: 'https://www.instagram.com/alice/' }] }]), 'followers_1.json', 'instagram');
  const followers2 = parseExport(JSON.stringify([{ string_list_data: [{ value: 'carol' }] }]), 'followers_2.json', 'instagram');
  const result = mergeFiles(blankLists(), [following, followers1, followers2].map((p, i) => ({ ...p, name: `${i}.json` })));
  assert.equal(result.following.get('alice')?.followsYou, true);
  assert.equal(result.following.get('bob')?.followsYou, false);
  assert.equal(result.followers.size, 2);
});

test('A missing followers file stays unknown; a loaded empty file means known empty', () => {
  const p = parseExport('["alice"]', 'following.json', 'instagram');
  const first = mergeFiles(blankLists(), [{ ...p, name: 'following.json' }]);
  assert.equal(first.following.get('alice')?.followsYou, null);
  const second = mergeFiles(first, [{ ...parseExport('[]', 'followers_1.json', 'instagram'), name: 'followers_1.json' }]);
  assert.equal(second.following.get('alice')?.followsYou, false);
});

test('URLs cannot point outside the chosen platform or to multi-segment pages', () => {
  for (const url of ['javascript:alert(1)', 'https://instagram.com.evil.test/alice/', 'https://www.instagram.com/reel/123', 'https://u:p@www.instagram.com/alice/']) {
    assert.equal(person('alice', 'instagram', url), null);
  }
  assert.equal(person('https://www.facebook.com/profile.php?id=123456', 'facebook')?.username, '123456');
});

test('TikTok list and TXT, canonical JSON platform mismatch and malformed files', () => {
  const p = parseExport('{"Following List":{"List":[{"UserName":"@someone","Date":"2026-01-01"}]}}', 'data.json', 'tiktok');
  assert.equal(p.relation, 'following'); assert.equal(p.people[0].username, 'someone');
  assert.equal(parseExport('Date: yesterday\nUsername: alice\n\nUsername: bob', 'following.txt', 'tiktok').people.length, 2);
  assert.throws(() => parseExport('{"platform":"tiktok","targets":[]}', 'targets.json', 'instagram'), /pertenece/);
  assert.throws(() => parseExport('broken', 'following.json', 'instagram'), /no es válido/);
  assert.throws(() => parseExport('{"random":[]}', 'following.json', 'instagram'), /no reconocido/);
  assert.equal(parseExport('{"platform":"instagram","demo":true,"targets":[{"username":"alice","profileUrl":"https://www.instagram.com/alice/"}]}', 'targets.json', 'instagram').demo, true);
});

test('Combined TikTok JSON imports both lists and reports include fans safely', () => {
  const combined = JSON.stringify({
    'Your Activity': {
      'Following List': { Following: [{ UserName: 'alice' }, { UserName: 'bob' }] },
      'Follower List': { FansList: [{ UserName: 'alice' }, { UserName: 'fan_uno' }] },
    },
  });
  const sections = parseExportSections(combined, 'user_data_tiktok.json', 'tiktok');
  assert.equal(sections.length, 2);
  const lists = mergeFiles(blankLists(), sections.map(s => ({ ...s, name: 'user_data_tiktok.json' })));
  const summary = buildReportSummary(lists, 'tiktok', 'davosaurio', new Set(['alice']), new Set(['bob']));
  assert.equal(summary.notFollowing, 1);
  assert.equal(summary.mutual, 1);
  assert.equal(summary.fans, 1);
  const csv = buildCsvReport(summary);
  assert.ok(csv.includes('Solo te sigue'));
  assert.ok(csv.includes('fan_uno'));
  const html = buildHtmlReport(summary);
  assert.ok(html.includes('@fan_uno'));
  assert.ok(html.includes('Reporte de conexiones'));
});

function buildDeflateZip(files: { name: string; content: string }[]): Blob {
  const localParts: Uint8Array[] = [];
  const centralParts: Uint8Array[] = [];
  let offset = 0;
  for (const file of files) {
    const nameBytes = Buffer.from(file.name, 'utf8');
    const raw = Buffer.from(file.content, 'utf8');
    const compressed = deflateRawSync(raw);

    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(8, 8);
    local.writeUInt32LE(compressed.length, 18);
    local.writeUInt32LE(raw.length, 22);
    local.writeUInt16LE(nameBytes.length, 26);
    localParts.push(local, nameBytes, compressed);

    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(20, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt16LE(8, 10);
    central.writeUInt32LE(compressed.length, 20);
    central.writeUInt32LE(raw.length, 24);
    central.writeUInt16LE(nameBytes.length, 28);
    central.writeUInt32LE(offset, 42);
    centralParts.push(central, nameBytes);

    offset += local.length + nameBytes.length + compressed.length;
  }
  const centralSize = centralParts.reduce((acc, part) => acc + part.length, 0);
  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(files.length, 8);
  eocd.writeUInt16LE(files.length, 10);
  eocd.writeUInt32LE(centralSize, 12);
  eocd.writeUInt32LE(offset, 16);
  return new Blob([...localParts, ...centralParts, eocd], { type: 'application/zip' });
}

test('Direct ZIP reader extracts Instagram JSON lists in memory and skips unrelated entries', async () => {
  const zip = buildDeflateZip([
    { name: 'media/photo.jpg', content: 'binary-ignored' },
    { name: 'connections/followers_and_following/following.json', content: JSON.stringify({ relationships_following: [{ title: 'alice' }, { title: 'bob' }] }) },
    { name: 'connections/followers_and_following/followers_1.json', content: JSON.stringify([{ string_list_data: [{ value: 'alice' }] }]) },
  ]);
  const extracted = await extractExportEntries(zip, 'instagram');
  assert.equal(extracted.length, 2);
  const sections = extracted.flatMap(entry => parseExportSections(entry.text, entry.name, 'instagram').map(s => ({ ...s, name: entry.name })));
  const merged = mergeFiles(blankLists(), sections);
  assert.equal(merged.following.get('alice')?.followsYou, true);
  assert.equal(merged.following.get('bob')?.followsYou, false);
});

test('Public web analyzer mode activates on public domains and ?mode=web override', () => {
  assert.equal(detectPublicWebMode('127.0.0.1', ''), false);
  assert.equal(detectPublicWebMode('localhost', ''), false);
  assert.equal(detectPublicWebMode('127.0.0.1', '?mode=web'), true);
  assert.equal(detectPublicWebMode('davidcevallos15.github.io', ''), true);
  assert.equal(detectPublicWebMode('www.davidcevallos.me', ''), true);
  assert.equal(detectPublicWebMode('davidcevallos15.github.io', '?mode=local'), false);
});
