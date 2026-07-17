import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, currentUserId, Dashboard, EventInput, eventId, RelapseContext } from '../../api';
import { enqueue } from '../../offline';
import { PathDialog } from '../../ui/PathDialog';
import { CopingFlow } from '../coping/CopingFlow';
import { JournalView } from '../journal/JournalView';
import { SettingsView } from '../settings/SettingsView';

const triggers = [
  ['stress', 'Стресс'], ['anger', 'Злость'], ['boredom', 'Скука'], ['physical', 'Телесная тяга'],
  ['coffee', 'Кофе'], ['after_meal', 'После еды'], ['driving', 'За рулём'], ['work_break', 'Перерыв'],
  ['social', 'В компании'], ['alcohol', 'Алкоголь'], ['focus', 'Сосредоточиться'], ['hands', 'Занять руки'],
  ['outside', 'На улице'], ['habit', 'По привычке'],
] as const;

const relapseContexts: [RelapseContext, string][] = [
  ['one', 'Одна сигарета'], ['day', 'Курил сегодня'], ['days', 'Курю несколько дней'],
  ['afraid', 'Боюсь начинать снова'], ['angry', 'Злюсь на себя'], ['hopeless', 'Кажется, всё бессмысленно'],
];

export const formatDuration = (seconds: number) => {
  const hours = Math.floor(seconds / 3600);
  const days = Math.floor(hours / 24);
  return days ? `${days} д. ${hours % 24} ч.` : `${hours} ч. ${Math.floor(seconds % 3600 / 60)} мин.`;
};

const triggerLabel = (value?: string) => triggers.find(([id]) => id === value)?.[1] || value || 'Контекст не указан';

function PreparationCard({ steps }: { steps: string[] }) {
  if (!steps.length) return null;
  return <section className="path-journey-card preparation-card">
    <header><span className="path-kicker">Следующий отрезок</span><h2>Подготовь первые дни без сигарет</h2></header>
    <ol>{steps.map((step, index) => <li key={step}><i>{index + 1}</i><span>{step}</span></li>)}</ol>
  </section>;
}

function RecoveryCard({ until, steps }: { until: string | null; steps: string[] }) {
  if (!until || !steps.length) return null;
  const minutes = Math.max(0, Math.ceil((new Date(until).getTime() - Date.now()) / 60000));
  return <section className="path-recovery-card">
    <header><div><span className="path-kicker">Режим восстановления</span><h2>Путь продолжается</h2></div><strong>{minutes}<small>мин.</small></strong></header>
    <p>Срыв — это информация о сложном моменте, а не оценка тебя.</p>
    <ol>{steps.map((step, index) => <li key={step}><i>{index + 1}</i><span>{step}</span></li>)}</ol>
  </section>;
}

type DashboardViewProps = {
  dashboard: Dashboard;
  refresh: () => void | Promise<void>;
  initialScreen?: 'home' | 'journal' | 'settings';
  updatePlan?: (data: object) => Promise<unknown>;
};

export function DashboardView({ dashboard, refresh, initialScreen = 'home', updatePlan = api.plan }: DashboardViewProps) {
  const [trigger, setTrigger] = useState<EventInput['trigger']>('stress');
  const [note, setNote] = useState('');
  const [notice, setNotice] = useState('');
  const [screen, setScreen] = useState<'home' | 'journal' | 'settings'>(initialScreen);
  const navigate = useNavigate();
  const [supportOpen, setSupportOpen] = useState(false);
  const [pauseOpen, setPauseOpen] = useState(false);
  const [relapseOpen, setRelapseOpen] = useState(false);
  const [relapseContext, setRelapseContext] = useState<RelapseContext>('one');
  const [phaseBusy, setPhaseBusy] = useState(false);
  const [relapseBusy, setRelapseBusy] = useState(false);
  const isQuit = dashboard.phase === 'quit';
  const changeScreen = (next: 'home' | 'journal' | 'settings') => {
    setScreen(next);
    navigate(next === 'home' ? '/app' : `/${next}`);
  };

  const record = async (kind: EventInput['kind'], relapse_context?: RelapseContext) => {
    const entry: EventInput = { kind, trigger, note, client_event_id: eventId(), relapse_context };
    try {
      const result = await api.event(entry);
      setNotice(result.intervention);
      setNote('');
      await refresh();
      return true;
    } catch (error) {
      if (!navigator.onLine || error instanceof TypeError) {
        enqueue(currentUserId(), entry);
        setNotice('Запись сохранена на устройстве и синхронизируется при появлении сети.');
        return true;
      } else setNotice('Не удалось сохранить запись. Попробуй ещё раз.');
      return false;
    }
  };

  const changePhase = async (phase: Dashboard['phase']) => {
    setPhaseBusy(true);
    try {
      await updatePlan({ phase });
      setNotice(phase === 'paused' ? 'Путь на паузе. История и лучший период сохранены.' : 'Путь продолжен с той точки, где ты остановился.');
      setPauseOpen(false);
      await refresh();
    } catch {
      setNotice('Не удалось изменить состояние пути. Проверь соединение и попробуй ещё раз.');
    } finally {
      setPhaseBusy(false);
    }
  };

  const confirmRelapse = async () => {
    setRelapseBusy(true);
    try {
      if (await record('relapse', relapseContext)) setRelapseOpen(false);
    } finally {
      setRelapseBusy(false);
    }
  };

  if (screen === 'journal') return <JournalView onBack={() => changeScreen('home')} onSupport={() => { changeScreen('home'); setSupportOpen(true); }} />;
  if (screen === 'settings') return <SettingsView onBack={() => changeScreen('home')} />;

  const phaseTitle = dashboard.phase === 'quit' ? 'Без сигарет' : dashboard.phase === 'paused' ? 'Путь на паузе' : dashboard.phase === 'preparation' ? 'Подготовка' : 'Последняя пачка';
  const targetDateLabel = dashboard.target_quit_at ? new Date(dashboard.target_quit_at).toLocaleString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' }) : 'Дата пока не выбрана';
  const dashboardTitle = isQuit ? 'Твой путь продолжается' : dashboard.phase === 'paused' ? 'Можно продолжить без спешки' : dashboard.phase === 'preparation' ? 'Подготовь спокойный старт' : `Осталось ${dashboard.remaining}`;
  const milestoneProgress = dashboard.next_milestone_seconds ? Math.min(100, Math.round(dashboard.smoke_free_seconds / dashboard.next_milestone_seconds * 100)) : 100;
  const orbitValue = dashboard.smoke_free_seconds < 86400 ? Math.floor(dashboard.smoke_free_seconds / 3600) : Math.floor(dashboard.smoke_free_seconds / 86400);
  const orbitUnit = dashboard.smoke_free_seconds < 86400 ? 'часов' : 'дней';
  return <main className="path-app-shell">
    <header className="path-app-header"><div className="path-wordmark"><img className="path-brand-mark" src="/brand/luma-mark.svg" alt="" /><b>Luma</b></div><button type="button" aria-label="Открыть настройки" onClick={() => changeScreen('settings')}>⚙</button></header>
    <section className="path-dashboard-intro"><div><span className="path-kicker">{phaseTitle}</span><h1>{dashboardTitle}</h1></div><time>{new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' }).format(new Date())}</time></section>
    <section className={`path-live-card phase-${dashboard.phase}`}>
      {isQuit ? <><div><span>Без сигарет</span><b>{formatDuration(dashboard.smoke_free_seconds)}</b><small>Каждый час — часть твоей истории</small></div><div className="path-live-orbit"><i /><b>{orbitValue}</b><span>{orbitUnit}</span></div><footer><div><span>Не выкурено</span><b>{dashboard.avoided_cigarettes}</b></div><div><span>Сэкономлено</span><b>{dashboard.saved_money.toLocaleString('ru-RU')} ₽</b></div></footer></> : <><div><span>{dashboard.phase === 'paused' ? 'Сейчас' : dashboard.phase === 'preparation' ? 'Выбранный старт' : 'В пачке'}</span><b>{dashboard.phase === 'paused' ? 'Пауза' : dashboard.phase === 'preparation' ? targetDateLabel : `${dashboard.remaining} из ${dashboard.cigarettes_per_pack}`}</b><small>{dashboard.phase === 'paused' ? 'Вернуться можно в своём темпе' : dashboard.phase === 'preparation' ? 'До этого момента можно подготовить опоры и ритуалы' : 'Честная отметка важнее идеальной серии'}</small></div>{dashboard.phase === 'last_pack' && <div className="path-pack-progress" role="progressbar" aria-label="Остаток последней пачки" aria-valuemin={0} aria-valuemax={dashboard.cigarettes_per_pack} aria-valuenow={dashboard.remaining} aria-valuetext={`Осталось ${dashboard.remaining} из ${dashboard.cigarettes_per_pack}`}><i style={{ width: `${Math.max(0, Math.min(100, dashboard.remaining / dashboard.cigarettes_per_pack * 100))}%` }} /></div>}</>}
    </section>
    {isQuit && <section className="path-attempt-card" aria-label="История текущей попытки"><header><div><span className="path-kicker">Попытка {dashboard.attempt_number || 1}</span><h2>Не с нуля — с опытом</h2></div><div><span>Лучший период</span><b>{formatDuration(dashboard.best_smoke_free_seconds)}</b></div></header>{dashboard.next_milestone_seconds && dashboard.next_milestone_label ? <div className="path-milestone-progress"><div><span>Ближайшая остановка</span><b>{dashboard.next_milestone_label}</b><small>Осталось {formatDuration(Math.max(0, dashboard.next_milestone_seconds - dashboard.smoke_free_seconds))}</small></div><div role="progressbar" aria-label={`Прогресс до вехи ${dashboard.next_milestone_label}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={milestoneProgress}><i style={{ width: `${milestoneProgress}%` }} /></div></div> : <p>Большие вехи уже позади. История остаётся с тобой.</p>}</section>}
    <div className="path-main-actions"><button type="button" className="support" onClick={() => setSupportOpen(true)}><i>≈</i><span><b>Мне сейчас тяжело</b><small>Получить короткий план</small></span><strong>→</strong></button><button type="button" onClick={() => changeScreen('journal')}><i>≡</i><span><b>Мой журнал</b><small>События и триггеры</small></span><strong>→</strong></button></div>
    {dashboard.phase === 'preparation' && <section className="path-phase-control advance"><div><span className="path-kicker">Когда решение созрело</span><h2>Перейти к последней пачке</h2><p>Дата подготовки останется в плане, а счётчик начнёт уменьшаться только после твоих отметок.</p></div><button className="path-button primary" disabled={phaseBusy} type="button" onClick={() => void changePhase('last_pack')}>{phaseBusy ? 'Сохраняем…' : 'Начать последнюю пачку'} <span>→</span></button></section>}
    {dashboard.phase === 'last_pack' && <section className="path-phase-control advance"><div><span className="path-kicker">Не обязательно заканчивать пачку</span><h2>Начать период без сигарет сейчас</h2><p>Оставшийся счётчик станет нулём, а новая попытка начнётся с этого момента.</p></div><button className="path-button primary" disabled={phaseBusy} type="button" onClick={() => void changePhase('quit')}>{phaseBusy ? 'Начинаем…' : 'Я больше не курю'} <span>→</span></button></section>}
    {dashboard.phase === 'paused' ? <section className="path-phase-control resume"><div><span className="path-kicker">Точка сохранена</span><h2>Продолжить {dashboard.paused_from === 'preparation' ? 'подготовку' : dashboard.paused_from === 'last_pack' ? 'последнюю пачку' : 'период без сигарет'}?</h2><p>Записи и лучший результат остались в истории.</p></div><button className="path-button primary" disabled={phaseBusy} type="button" onClick={() => void changePhase(dashboard.paused_from || (dashboard.remaining > 0 ? 'last_pack' : 'quit'))}>{phaseBusy ? 'Возвращаемся…' : 'Продолжить путь'} <span>→</span></button></section> : <div className="path-phase-control pause"><span>Нужна более длинная передышка?</span><button type="button" onClick={() => setPauseOpen(true)}>Поставить путь на паузу</button></div>}
    {dashboard.recovery_until && <RecoveryCard until={dashboard.recovery_until} steps={dashboard.recovery_steps} />}
    {!dashboard.recovery_until && <PreparationCard steps={dashboard.preparation_steps} />}
    {!isQuit && dashboard.phase !== 'paused' && <section className="path-checkin-card"><header><span className="path-kicker">Честная отметка</span><h2>Что произошло сейчас?</h2></header><div className="path-trigger-list">{triggers.map(([id, label]) => <button aria-pressed={trigger === id} type="button" className={trigger === id ? 'active' : ''} key={id} onClick={() => setTrigger(id)}>{label}</button>)}</div><label>Заметка <span>необязательно</span><textarea value={note} onChange={event => setNote(event.target.value)} placeholder="Коротко опиши момент. Не указывай медицинские данные." maxLength={1000} /></label><button className="path-button quiet" type="button" onClick={() => record('smoked')}>Отметить сигарету <span>→</span></button></section>}
    {isQuit && <section className="path-reason-card"><span className="path-kicker">Твоя опора</span><blockquote>{dashboard.reasons || 'Продолжать этот путь в своём темпе.'}</blockquote><button type="button" onClick={() => setRelapseOpen(true)}>Отметить срыв без стыда</button></section>}
    <section className="path-guidance" aria-live="polite"><span>{notice ? 'Обновление' : 'Следующий шаг'}</span><p>{notice || dashboard.intervention}</p>{dashboard.recent_triggers.length > 0 && <small>Недавно отмечалось: {dashboard.recent_triggers.map(triggerLabel).join(' · ')}</small>}</section>
    <nav className="path-bottom-nav" aria-label="Основная навигация"><button className="active" type="button" onClick={() => changeScreen('home')}><span>⌂</span>Сегодня</button><button className="support" type="button" onClick={() => setSupportOpen(true)}><span>＋</span>Поддержка</button><button type="button" onClick={() => changeScreen('journal')}><span>≡</span>Журнал</button></nav>
    <PathDialog open={pauseOpen} onClose={() => setPauseOpen(false)} labelledBy="pause-title" className="path-pause-dialog"><header><div><span className="path-kicker">Без потери истории</span><h2 id="pause-title">Поставить путь на паузу?</h2></div><button type="button" aria-label="Закрыть" onClick={() => setPauseOpen(false)}>×</button></header><p>Текущая точка, все события и лучший период сохранятся. Вернуться можно будет одним действием.</p><div className="path-form-actions"><button className="path-button ghost" type="button" onClick={() => setPauseOpen(false)}>Остаться в пути</button><button className="path-button primary" disabled={phaseBusy} type="button" onClick={() => void changePhase('paused')}>{phaseBusy ? 'Сохраняем…' : 'Поставить на паузу'}</button></div></PathDialog>
    <PathDialog open={relapseOpen} onClose={() => setRelapseOpen(false)} labelledBy="relapse-title" className="path-relapse-dialog"><header><div><span className="path-kicker">Без наказания и обнуления опыта</span><h2 id="relapse-title">Что происходит сейчас?</h2></div><button type="button" aria-label="Закрыть" onClick={() => setRelapseOpen(false)}>×</button></header><p>Выбери ближайший вариант — от него зависит короткий план возвращения. Лучший результат и вся история останутся.</p><div className="path-relapse-options">{relapseContexts.map(([id, label]) => <button aria-pressed={relapseContext === id} className={relapseContext === id ? 'active' : ''} key={id} type="button" onClick={() => setRelapseContext(id)}>{label}</button>)}</div><div className="path-form-actions"><button className="path-button ghost" type="button" disabled={relapseBusy} onClick={() => setRelapseOpen(false)}>Вернуться без отметки</button><button className="path-button primary" disabled={relapseBusy} type="button" onClick={() => void confirmRelapse()}>{relapseBusy ? 'Сохраняем…' : 'Получить план возвращения'}</button></div></PathDialog>
    <CopingFlow open={supportOpen} reason={dashboard.reasons} onClose={() => setSupportOpen(false)} onCompleted={(message, synced) => { setNotice(message); if (synced) void refresh(); }} />
  </main>;
}
