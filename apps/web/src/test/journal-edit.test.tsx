import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { JournalView } from '../features/journal/JournalView';

describe('journal correction window', () => {
  it('edits a recent behavioural event and keeps the dialog keyboard accessible', async () => {
    const user = userEvent.setup();
    const createdAt = new Date().toISOString();
    const updateEvent = vi.fn().mockResolvedValue({ id: 7, kind: 'craving', trigger: 'coffee', intensity: 2, note: 'исправлено', created_at: createdAt });
    const loadJournal = vi.fn().mockResolvedValue({
      items: [{ id: 'event:7', source: 'event', type: 'craving', created_at: createdAt, trigger: 'stress', intensity_before: 4, note: 'до', editable_until: new Date(Date.now() + 10 * 60_000).toISOString() }],
      next_cursor: null,
      summary: { total: 1, cravings: 1, coping_completed: 0, relapses: 0, sufficient_data: false, top_trigger: 'stress' },
    });

    render(<JournalView onBack={() => undefined} onSupport={() => undefined} loadJournal={loadJournal} updateEvent={updateEvent} />);
    const edit = await screen.findByRole('button', { name: 'Исправить' });
    await user.click(edit);
    expect(screen.getByRole('dialog', { name: 'Исправить событие' })).toBeVisible();
    expect(screen.getByRole('combobox', { name: 'Триггер события' })).toHaveFocus();
    await user.selectOptions(screen.getByRole('combobox', { name: 'Триггер события' }), 'coffee');
    const note = screen.getByRole('textbox', { name: 'Заметка' });
    await user.clear(note);
    await user.type(note, 'исправлено');
    await user.click(screen.getByRole('button', { name: /Сохранить исправление/ }));

    await waitFor(() => expect(updateEvent).toHaveBeenCalledWith(7, expect.objectContaining({ trigger: 'coffee', note: 'исправлено' })));
    expect(await screen.findByText('исправлено')).toBeVisible();
  });
});
