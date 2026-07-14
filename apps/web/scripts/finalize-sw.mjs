import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const indexPath = path.join(root, 'dist', 'index.html');
const workerPath = path.join(root, 'dist', 'sw.js');
const [html, worker] = await Promise.all([readFile(indexPath, 'utf8'), readFile(workerPath, 'utf8')]);
const assets = [...html.matchAll(/(?:src|href)="(\/assets\/[^"?#]+)"/g)].map(match => match[1]);
const precache = [...new Set(['/', '/manifest.webmanifest', '/icon.svg', '/privacy.html', '/terms.html', ...assets])].sort();
const versionMaterial = await Promise.all(precache.map(async item => {
  const file = item === '/' ? indexPath : path.join(root, 'dist', item.slice(1));
  const contents = await readFile(file);
  return `${item}:${createHash('sha256').update(contents).digest('hex')}`;
}));
const version = createHash('sha256').update(versionMaterial.join('\n')).digest('hex').slice(0, 12);
const finalized = worker
  .replace("const CACHE = 'kurilka-static-dev';", `const CACHE = 'kurilka-static-${version}';`)
  .replace("const PRECACHE = ['/', '/manifest.webmanifest', '/icon.svg', '/privacy.html', '/terms.html'];", `const PRECACHE = ${JSON.stringify(precache)};`);

if (finalized === worker || !assets.length) throw new Error('Service worker precache finalization failed');
await writeFile(workerPath, finalized, 'utf8');
