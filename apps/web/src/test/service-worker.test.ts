/// <reference types="node" />
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { runInNewContext } from 'node:vm';
import { describe, expect, it, vi } from 'vitest';

type WorkerEvent = { waitUntil: (promise: Promise<unknown>) => void };
type WorkerHandler = (event: WorkerEvent & Record<string, unknown>) => void;

function workerHarness() {
  const handlers = new Map<string, WorkerHandler>();
  const client = {
    url: 'https://example.test/journal',
    navigate: vi.fn(async (_url: string) => client),
    focus: vi.fn(async () => client),
  };
  const showNotification = vi.fn(async (_title: string, _options: Record<string, unknown>) => undefined);
  const openWindow = vi.fn(async (_url: string) => client);
  const worker = {
    location: { origin: 'https://example.test' },
    addEventListener: (type: string, handler: WorkerHandler) => handlers.set(type, handler),
    registration: { showNotification },
    clients: { matchAll: vi.fn(async () => [client]), openWindow, claim: vi.fn(async () => undefined) },
    skipWaiting: vi.fn(async () => undefined),
  };
  const script = readFileSync(resolve(process.cwd(), 'public', 'sw.js'), 'utf8');
  runInNewContext(script, { self: worker, URL, Response });
  return { handlers, client, showNotification, openWindow };
}

describe('service worker notification navigation', () => {
  it('shows a versioned support payload without changing its safe route', async () => {
    const { handlers, showNotification } = workerHarness();
    let completion: Promise<unknown> = Promise.resolve();
    handlers.get('push')?.({
      data: { json: () => ({ version: 1, body: 'Поддержка рядом.', path: '/app/support' }) },
      waitUntil: promise => { completion = Promise.resolve(promise); },
    });
    await completion;
    expect(showNotification).toHaveBeenCalledWith('Последняя пачка', expect.objectContaining({
      body: 'Поддержка рядом.',
      data: { path: '/app/support' },
    }));
  });

  it('replaces a legacy free-text payload with neutral lock-screen copy', async () => {
    const { handlers, showNotification } = workerHarness();
    let completion: Promise<unknown> = Promise.resolve();
    handlers.get('push')?.({
      data: {
        json: () => { throw new SyntaxError('legacy text'); },
        text: () => 'После кофе тебе обычно хочется курить.',
      },
      waitUntil: promise => { completion = Promise.resolve(promise); },
    });
    await completion;
    expect(showNotification).toHaveBeenCalledWith('Последняя пачка', expect.objectContaining({
      body: 'Открой «Последнюю пачку», чтобы продолжить план.',
      data: { path: '/app' },
    }));
    expect(showNotification.mock.calls[0]?.[1]).not.toEqual(expect.objectContaining({ body: expect.stringContaining('кофе') }));
  });

  it('focuses an open app window and rejects an untrusted notification route', async () => {
    const { handlers, client, openWindow } = workerHarness();
    let completion: Promise<unknown> = Promise.resolve();
    const close = vi.fn();
    handlers.get('notificationclick')?.({
      notification: { data: { path: 'https://attacker.test/' }, close },
      waitUntil: promise => { completion = Promise.resolve(promise); },
    });
    await completion;
    expect(close).toHaveBeenCalledOnce();
    expect(client.navigate).toHaveBeenCalledWith('https://example.test/app');
    expect(client.focus).toHaveBeenCalledOnce();
    expect(openWindow).not.toHaveBeenCalled();
  });
});
