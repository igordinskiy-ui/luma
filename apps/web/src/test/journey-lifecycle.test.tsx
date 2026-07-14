import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { api, Dashboard } from '../api';
import { DashboardView } from '../features/journey/DashboardView';

const base: Dashboard = {
  phase: 'quit', paused_from: null, remaining: 0, cigarettes_per_pack: 20, pack_price: 240,
  smoke_free_seconds: 190800, best_smoke_free_seconds: 691200, attempt_number: 2,
  next_milestone_seconds: 259200, next_milestone_label: '3 дня', avoided_cigarettes: 35,
  saved_money: 420, risk: 'low', intervention: 'Следующий маленький шаг.', reasons: 'Моя причина.',
  recent_triggers: [], preparation_steps: [], recovery_until: null, recovery_steps: [], target_quit_at: null,
};

const renderDashboard = (dashboard: Dashboard, updatePlan = vi.fn().mockResolvedValue(undefined)) => {
  const refresh = vi.fn();
  render(<MemoryRouter initialEntries={['/app']}><DashboardView dashboard={dashboard} refresh={refresh} updatePlan={updatePlan} /></MemoryRouter>);
  return { updatePlan, refresh };
};

describe('journey phase UI contracts', () => {
  it.each([
    ['preparation', 'Начать последнюю пачку', 'last_pack'],
    ['last_pack', 'Я больше не курю', 'quit'],
  ] as const)('moves %s through its explicit primary action', async (phase, action, destination) => {
    const { updatePlan, refresh } = renderDashboard({ ...base, phase, remaining: phase === 'last_pack' ? 7 : 20 });
    await userEvent.click(screen.getByRole('button', { name: new RegExp(action) }));
    await waitFor(() => expect(updatePlan).toHaveBeenCalledWith({ phase: destination }));
    expect(refresh).toHaveBeenCalledOnce();
  });

  it('resumes the exact phase saved before pause', async () => {
    const { updatePlan } = renderDashboard({ ...base, phase: 'paused', paused_from: 'preparation', remaining: 20 });
    expect(screen.getByRole('heading', { name: 'Продолжить подготовку?' })).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: /Продолжить путь/ }));
    await waitFor(() => expect(updatePlan).toHaveBeenCalledWith({ phase: 'preparation' }));
  });

  it('pauses only after the non-destructive confirmation', async () => {
    const { updatePlan } = renderDashboard(base);
    await userEvent.click(screen.getByRole('button', { name: 'Поставить путь на паузу' }));
    expect(screen.getByRole('dialog', { name: 'Поставить путь на паузу?' })).toHaveTextContent(/все события и лучший период сохранятся/i);
    await userEvent.click(screen.getByRole('button', { name: 'Поставить на паузу' }));
    await waitFor(() => expect(updatePlan).toHaveBeenCalledWith({ phase: 'paused' }));
  });

  it('explains recovery without punishment or resetting history', () => {
    renderDashboard({ ...base, recovery_until: new Date(Date.now() + 15 * 60000).toISOString(), recovery_steps: ['Выбрать следующий шаг'] });
    expect(screen.getByRole('heading', { name: 'Путь продолжается' })).toBeVisible();
    expect(screen.getByText('Срыв — это информация о сложном моменте, а не оценка тебя.')).toBeVisible();
    expect(screen.getByText('Не с нуля — с опытом')).toBeVisible();
  });

  it('records a relapse only after the recovery confirmation', async () => {
    const record = vi.spyOn(api, 'event').mockResolvedValue({ intervention: 'Начни с короткой паузы.' });
    renderDashboard(base);
    const opener = screen.getByRole('button', { name: 'Отметить срыв без стыда' });

    await userEvent.click(opener);
    const dialog = screen.getByRole('dialog', { name: 'Отметить сложный момент?' });
    expect(dialog).toHaveTextContent(/лучший результат и вся история останутся/i);
    await userEvent.click(screen.getByRole('button', { name: 'Вернуться без отметки' }));
    expect(record).not.toHaveBeenCalled();
    expect(opener).toHaveFocus();

    await userEvent.click(opener);
    await userEvent.click(screen.getByRole('button', { name: 'Сохранить и восстановиться' }));
    await waitFor(() => expect(record).toHaveBeenCalledWith(expect.objectContaining({ kind: 'relapse' })));
  });
});
