import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const baseURL = process.env.E2E_BASE_URL || 'http://127.0.0.1:41792';
const parsed = new URL(baseURL);
const server = spawn(process.execPath, [
  'node_modules/vite/bin/vite.js', 'preview',
  '--host', parsed.hostname,
  '--port', parsed.port || '80',
  '--strictPort',
], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'] });

let serverOutput = '';
server.stdout.on('data', chunk => { serverOutput += chunk.toString(); });
server.stderr.on('data', chunk => { serverOutput += chunk.toString(); });

async function waitUntilReady() {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    if (server.exitCode !== null) throw new Error(`Preview server exited early.\n${serverOutput}`);
    try {
      const response = await fetch(baseURL);
      if (response.ok) return;
    } catch {
      // The server is still starting.
    }
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  throw new Error(`Preview server did not become ready.\n${serverOutput}`);
}

try {
  await waitUntilReady();
  const tests = spawn(process.execPath, ['node_modules/@playwright/test/cli.js', 'test', ...process.argv.slice(2)], {
    cwd: root,
    env: { ...process.env, E2E_BASE_URL: baseURL },
    stdio: 'inherit',
  });
  const exitCode = await new Promise(resolve => tests.on('exit', code => resolve(code ?? 1)));
  process.exitCode = exitCode;
} finally {
  server.kill();
}
