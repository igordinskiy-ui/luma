import { Dashboard } from '../../api';

export const journeyDashboardDemo: Dashboard = {
  phase: 'quit', remaining: 0, cigarettes_per_pack: 20, pack_price: 240,
  smoke_free_seconds: 190800, best_smoke_free_seconds: 691200, attempt_number: 2,
  next_milestone_seconds: 259200, next_milestone_label: '3 дня', avoided_cigarettes: 35,
  saved_money: 420, risk: 'low', intervention: 'Сделай один спокойный вдох и выбери следующий маленький шаг.',
  reasons: 'Хочу просыпаться легче и быть рядом с семьёй.', recent_triggers: ['coffee'],
  preparation_steps: [], recovery_until: null, recovery_steps: [], target_quit_at: null,
};

export const journeyPausedDemo: Dashboard = {
  ...journeyDashboardDemo, phase: 'paused', paused_from: 'preparation', remaining: 20,
  smoke_free_seconds: 0, avoided_cigarettes: 0, saved_money: 0,
  next_milestone_seconds: null, next_milestone_label: null,
  target_quit_at: new Date(Date.now() + 7 * 86400000).toISOString(),
};

export const journeyPreparationDemo: Dashboard = {
  ...journeyPausedDemo, phase: 'preparation', paused_from: null,
  preparation_steps: ['Убрать пепельницы из быстрого доступа', 'Подготовить воду или жвачку', 'Предупредить близкого человека'],
};

export const journeyLastPackDemo: Dashboard = {
  ...journeyDashboardDemo, phase: 'last_pack', remaining: 7,
  smoke_free_seconds: 0, avoided_cigarettes: 0, saved_money: 0,
  next_milestone_seconds: null, next_milestone_label: null,
};

export const journeyRecoveryDemo: Dashboard = {
  ...journeyDashboardDemo,
  recovery_until: new Date(Date.now() + 15 * 60000).toISOString(),
  recovery_steps: ['Отметить, что было триггером', 'Выбрать одну короткую технику', 'Вернуться к следующему часу, не обнуляя историю'],
};

export const copingTechniquesDemo = [
  { id: 'breathing' as const, title: 'Медленный выдох', duration_seconds: 300, instruction: 'Вдыхай спокойно и делай выдох немного длиннее вдоха.' },
  { id: 'water' as const, title: 'Стакан воды', duration_seconds: 180, instruction: 'Пей небольшими глотками и замечай температуру воды.' },
  { id: 'walk' as const, title: 'Короткая прогулка', duration_seconds: 420, instruction: 'Смени пространство и пройди несколько десятков шагов.' },
];

export const journalDemo = async () => ({ items: [
  { id: 'coping:2', source: 'coping' as const, type: 'coping' as const, created_at: new Date().toISOString(), trigger: 'coffee', intensity_before: 7, intensity_after: 3, technique: 'water' as const, status: 'completed' as const, note: '' },
  { id: 'event:1', source: 'event' as const, type: 'craving' as const, created_at: new Date(Date.now() - 300000).toISOString(), trigger: 'coffee', intensity_before: 4, note: '', editable_until: new Date(Date.now() + 600000).toISOString() },
], next_cursor: null, summary: { total: 2, cravings: 1, coping_completed: 1, relapses: 0, sufficient_data: false, top_trigger: null } });

export const journalUpdateDemo = async (id: number, data: { trigger?: string | null; intensity?: number | null; note?: string }) => ({ id, kind: 'craving' as const, trigger: data.trigger || undefined, intensity: data.intensity || undefined, note: data.note || '', created_at: new Date().toISOString() });
