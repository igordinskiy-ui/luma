import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { PathDialog } from '../ui/PathDialog';
import { PathState } from '../ui/PathState';

describe('Path UI primitives', () => {
  it('announces an error state without relying on colour', () => {
    render(<PathState title="Не удалось сохранить" description="Попробуй ещё раз" tone="error" />);
    expect(screen.getByRole('alert')).toHaveTextContent('Не удалось сохранить');
    expect(screen.getByRole('alert')).toHaveTextContent('Попробуй ещё раз');
  });

  it('closes a dialog with Escape', async () => {
    const onClose = vi.fn();
    render(<PathDialog open onClose={onClose} labelledBy="dialog-title"><h2 id="dialog-title">Поддержка</h2><button>Закрыть</button></PathDialog>);
    expect(screen.getByRole('dialog', { name: 'Поддержка' })).toBeVisible();
    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('returns focus to the opener after closing', async () => {
    function Harness() {
      const [open, setOpen] = useState(false);
      return <><button onClick={() => setOpen(true)}>Открыть помощь</button><PathDialog open={open} onClose={() => setOpen(false)} labelledBy="focus-title"><h2 id="focus-title">Помощь</h2><button onClick={() => setOpen(false)}>Готово</button></PathDialog></>;
    }
    render(<Harness />);
    const opener = screen.getByRole('button', { name: 'Открыть помощь' });
    await userEvent.click(opener);
    await userEvent.click(screen.getByRole('button', { name: 'Готово' }));
    expect(opener).toHaveFocus();
  });

  it('supports an explicit safe initial focus target', () => {
    render(<PathDialog open onClose={() => undefined} labelledBy="delete-test"><h2 id="delete-test">Удаление</h2><button>Закрыть</button><input data-autofocus aria-label="Подтверждение" /></PathDialog>);
    expect(screen.getByRole('textbox', { name: 'Подтверждение' })).toHaveFocus();
  });
});
