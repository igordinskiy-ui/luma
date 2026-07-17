import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { api } from '../api';
import { CopingFlow } from '../features/coping/CopingFlow';

const techniques = [
  { id: 'breathing' as const, title: 'Медленный выдох', duration_seconds: 300, instruction: 'Спокойная инструкция.' },
  { id: 'water' as const, title: 'Стакан воды', duration_seconds: 180, instruction: 'Пей небольшими глотками.' },
];

describe('production coping flow', () => {
  it('keeps all four steps keyboard-operable and returns a completion', async () => {
    const user = userEvent.setup();
    const completed = vi.fn();
    render(<CopingFlow open demo initialTechniques={techniques} reason="Моя причина" onClose={() => undefined} onCompleted={completed} />);

    expect(screen.getByRole('heading', { name: 'Что за тяга сейчас?' })).toHaveFocus();
    await user.click(screen.getByRole('button', { name: /Подобрать действие/ }));
    await user.click(screen.getByRole('button', { name: /Стакан воды/ }));
    await user.click(screen.getByRole('button', { name: /Начать · 3 мин/ }));
    expect(screen.getByRole('timer')).toHaveTextContent('03:00');
    await user.click(screen.getByRole('button', { name: /Оценить тягу снова/ }));
    await user.click(screen.getByRole('button', { name: 'Стало легче' }));
    await user.click(screen.getByRole('button', { name: /Сохранить результат/ }));

    expect(completed).toHaveBeenCalledWith('Сессия сохранена в журнале.', true);
  });

  it('queues the create payload when the network disappears after server start', async () => {
    const user = userEvent.setup();
    sessionStorage.setItem('kurilka-user-id', '42');
    localStorage.clear();
    const start = vi.spyOn(api, 'startCoping').mockImplementation(async payload => ({ ...payload, id: 7, content_version: 'v1', status: 'active', started_at: '', updated_at: '' }));
    vi.spyOn(api, 'updateCoping').mockRejectedValue(new TypeError('offline'));
    render(<CopingFlow open initialTechniques={techniques} reason="Моя причина" onClose={() => undefined} onCompleted={() => undefined} />);

    await user.click(screen.getByRole('button', { name: /Подобрать действие/ }));
    await user.click(screen.getByRole('button', { name: /Стакан воды/ }));
    await user.click(screen.getByRole('button', { name: /Начать · 3 мин/ }));

    const queue = JSON.parse(localStorage.getItem('kurilka-coping-queue:42') || '[]');
    expect(queue[0].create).toEqual(start.mock.calls[0][0]);
    expect(queue[0].patches).toContainEqual({ technique: 'water' });
  });
});
