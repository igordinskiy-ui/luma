import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api';
import { clearQueued, enqueue, enqueueCopingPatch, enqueueCopingStart, syncQueued } from '../offline';

const event = (id: string) => ({
  kind: 'craving' as const,
  trigger: 'stress',
  intensity: 3,
  client_event_id: id,
});

describe('identity-bound offline queue', () => {
  beforeEach(() => {
    localStorage.clear();
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: true });
  });

  it('does not persist an event without an authenticated user', () => {
    enqueue(null, event('anonymous-1'));
    expect(localStorage.length).toBe(0);
  });

  it('synchronises only the selected user queue', async () => {
    enqueue('user-a', event('event-a1'));
    enqueue('user-b', event('event-b1'));
    const send = vi.spyOn(api, 'event').mockResolvedValue({ intervention: 'ok' });

    await syncQueued('user-a');

    expect(send).toHaveBeenCalledTimes(1);
    expect(send).toHaveBeenCalledWith(event('event-a1'));
    expect(localStorage.getItem('kurilka-event-queue:user-a')).toBe('[]');
    expect(localStorage.getItem('kurilka-event-queue:user-b')).toContain('event-b1');
  });

  it('stops at the first retryable failure to preserve event order', async () => {
    enqueue('user-a', event('event-a1'));
    enqueue('user-a', event('event-a2'));
    const send = vi.spyOn(api, 'event').mockRejectedValueOnce(new TypeError('offline')).mockResolvedValue({ intervention: 'ok' });

    await syncQueued('user-a');

    expect(send).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem('kurilka-event-queue:user-a')).toContain('event-a1');
    expect(localStorage.getItem('kurilka-event-queue:user-a')).toContain('event-a2');
  });

  it('removes only the requested user queue', () => {
    enqueue('user-a', event('event-a1'));
    enqueue('user-b', event('event-b1'));
    clearQueued('user-a');
    expect(localStorage.getItem('kurilka-event-queue:user-a')).toBeNull();
    expect(localStorage.getItem('kurilka-event-queue:user-b')).not.toBeNull();
  });

  it('replays a coping lifecycle sequentially after reconnecting', async () => {
    const create = { client_session_id: 'coping-offline-1', source: 'offline' as const, trigger: 'coffee', intensity_before: 7 };
    enqueueCopingStart('user-a', create);
    enqueueCopingPatch('user-a', create.client_session_id, { technique: 'water' });
    enqueueCopingPatch('user-a', create.client_session_id, { status: 'completed', intensity_after: 3 });
    vi.spyOn(api, 'event').mockResolvedValue({ intervention: 'ok' });
    const start = vi.spyOn(api, 'startCoping').mockResolvedValue({ ...create, id: 42, content_version: 'v1', status: 'active', started_at: '', updated_at: '' });
    const patch = vi.spyOn(api, 'updateCoping').mockResolvedValue({ ...create, id: 42, content_version: 'v1', status: 'completed', started_at: '', updated_at: '' });

    await syncQueued('user-a');

    expect(start).toHaveBeenCalledWith(create);
    expect(patch.mock.calls).toEqual([[42, { technique: 'water' }], [42, { status: 'completed', intensity_after: 3 }]]);
    expect(localStorage.getItem('kurilka-coping-queue:user-a')).toBe('[]');
  });

  it('coalesces concurrent reconnects for the same user', async () => {
    const create = { client_session_id: 'coping-single-flight', source: 'offline' as const, trigger: 'coffee', intensity_before: 7 };
    enqueueCopingStart('user-a', create);
    let release!: (value: Awaited<ReturnType<typeof api.startCoping>>) => void;
    const start = vi.spyOn(api, 'startCoping').mockImplementation(() => new Promise(resolve => { release = resolve; }));

    const first = syncQueued('user-a');
    const second = syncQueued('user-a');
    await vi.waitFor(() => expect(start).toHaveBeenCalledTimes(1));
    release({ ...create, id: 43, content_version: 'v1', status: 'active', started_at: '', updated_at: '' });
    await Promise.all([first, second]);

    expect(start).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem('kurilka-coping-queue:user-a')).toBe('[]');
  });
});
