import { readdir, readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { gzipSync } from 'node:zlib';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const assetsDir = path.join(root, 'dist', 'assets');
const files = (await readdir(assetsDir)).filter(name => name.endsWith('.js'));
const gzipBytes = (await Promise.all(files.map(async name => gzipSync(await readFile(path.join(assetsDir, name))).byteLength))).reduce((sum, size) => sum + size, 0);
const limitBytes = 150 * 1024;

if (!files.length) throw new Error('No production JavaScript bundle was found');
console.log(`Initial JavaScript budget: ${(gzipBytes / 1024).toFixed(2)} KB gzip / 150.00 KB`);
if (gzipBytes > limitBytes) throw new Error(`Initial JavaScript exceeds the 150 KB gzip release budget by ${((gzipBytes - limitBytes) / 1024).toFixed(2)} KB`);
