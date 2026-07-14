import { useEffect, useMemo, useRef, useState } from 'react';
import { api, CopingCreateInput, CopingPatchInput, CopingTechnique } from '../../api';
import { currentUserId } from '../../api';
import { enqueueCopingPatch, enqueueCopingStart } from '../../offline';
import { PathDialog } from '../../ui/PathDialog';

const triggerOptions = [
  ['stress', 'Стресс'], ['coffee', 'Кофе'], ['after_meal', 'После еды'],
  ['driving', 'За рулём'], ['friends', 'С друзьями'], ['alcohol', 'Алкоголь'], ['habit', 'По привычке'],
] as const;

type Props = { open: boolean; reason?: string; onClose: () => void; onCompleted: (message: string, synced: boolean) => void; initialTechniques?: CopingTechnique[]; demo?: boolean };

function formatTimer(seconds: number) {
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

export function CopingFlow({ open, reason, onClose, onCompleted, initialTechniques, demo = false }: Props) {
  const [step, setStep] = useState(0);
  const [intensity, setIntensity] = useState(6);
  const [after, setAfter] = useState(3);
  const [trigger, setTrigger] = useState<string>('stress');
  const [techniques, setTechniques] = useState<CopingTechnique[]>([]);
  const [technique, setTechnique] = useState<CopingTechnique['id']>('breathing');
  const [remaining, setRemaining] = useState(0);
  const [running, setRunning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const serverId = useRef<number | null>(null);
  const clientId = useRef('');
  const createPayload = useRef<CopingCreateInput | null>(null);
  const selected = useMemo(() => techniques.find(item => item.id === technique), [techniques, technique]);

  useEffect(() => {
    if (!open) return;
    if (initialTechniques?.length) { setTechniques(initialTechniques); setTechnique(initialTechniques[0].id); return; }
    api.copingTechniques().then(result => {
      setTechniques(result.techniques);
      if (result.techniques[0]) setTechnique(result.techniques[0].id);
    }).catch(() => setError('Не удалось загрузить способы поддержки. Проверь соединение и попробуй ещё раз.'));
  }, [open, initialTechniques]);

  useEffect(() => {
    if (!running || step !== 2) return;
    const timer = window.setInterval(() => setRemaining(value => {
      if (value <= 1) { setRunning(false); return 0; }
      return value - 1;
    }), 1000);
    return () => window.clearInterval(timer);
  }, [running, step]);

  useEffect(() => {
    if (!open) return;
    const heading = document.getElementById('coping-title');
    if (heading) { heading.tabIndex = -1; heading.focus(); }
  }, [open, step]);

  const resetAndClose = () => {
    setStep(0); setError(''); setRunning(false); setRemaining(0);
    serverId.current = null; clientId.current = ''; createPayload.current = null;
    onClose();
  };

  const patchSession = async (patch: CopingPatchInput) => {
    if (demo) return true;
    if (serverId.current) {
      try { await api.updateCoping(serverId.current, patch); return true; }
      catch (caught) { if (navigator.onLine && !(caught instanceof TypeError)) throw caught; }
    }
    const userId = currentUserId();
    if (createPayload.current) enqueueCopingStart(userId, createPayload.current);
    enqueueCopingPatch(userId, clientId.current, patch);
    return false;
  };

  const begin = async () => {
    setBusy(true); setError('');
    clientId.current ||= crypto.randomUUID();
    if (demo) { setStep(1); setBusy(false); return; }
    const payload: CopingCreateInput = { client_session_id: clientId.current, source: navigator.onLine ? 'dashboard' : 'offline', trigger, intensity_before: intensity };
    createPayload.current = payload;
    try {
      const session = await api.startCoping(payload);
      serverId.current = session.id;
      setStep(1);
    } catch (caught) {
      if (!navigator.onLine || caught instanceof TypeError) {
        enqueueCopingStart(currentUserId(), payload);
        setStep(1);
      } else setError('Не удалось сохранить начало. Ничего не потеряно — попробуй ещё раз.');
    } finally { setBusy(false); }
  };

  const startTechnique = async () => {
    if (!selected) return;
    setBusy(true); setError('');
    try {
      await patchSession({ technique });
      setRemaining(selected.duration_seconds); setRunning(true); setStep(2);
    } catch { setError('Не удалось сохранить выбор. Попробуй ещё раз.'); }
    finally { setBusy(false); }
  };

  const togglePause = async () => {
    const nextRunning = !running;
    setRunning(nextRunning);
    try { await patchSession({ status: nextRunning ? 'active' : 'paused' }); }
    catch { setError('Статус сохранится после восстановления сети.'); }
  };

  const complete = async () => {
    setBusy(true); setError('');
    try {
      const online = await patchSession({ status: 'completed', intensity_after: after });
      onCompleted(online ? 'Сессия сохранена в журнале.' : 'Сессия сохранена на устройстве и синхронизируется позже.', online);
      resetAndClose();
    } catch { setError('Не удалось завершить сессию. Выбранные ответы сохранены на экране.'); }
    finally { setBusy(false); }
  };

  const abandon = async () => {
    if (clientId.current) { try { await patchSession({ status: 'abandoned' }); } catch { /* safe local exit */ } }
    resetAndClose();
  };

  return <PathDialog open={open} onClose={abandon} labelledBy="coping-title">
    <header className="path-flow-header"><button type="button" aria-label="Назад" disabled={step === 0} onClick={() => setStep(value => Math.max(0, value - 1))}>←</button><div><span>Поддержка</span><i>{step + 1} из 4</i></div><button type="button" aria-label="Закрыть и сохранить выход" onClick={abandon}>×</button></header>
    {step === 0 && <section className="path-coping-step"><span className="path-kicker">Без оценки · только факт</span><h2 id="coping-title">Насколько сильно тянет сейчас?</h2><label className="path-range">Сила тяги <b>{intensity} из 10</b><input aria-label="Сила тяги" type="range" min="1" max="10" value={intensity} onChange={event => setIntensity(Number(event.target.value))} /></label><fieldset className="path-trigger-field"><legend>Что стало триггером?</legend><div className="path-trigger-list">{triggerOptions.map(([id, label]) => <button aria-pressed={trigger === id} className={trigger === id ? 'active' : ''} key={id} type="button" onClick={() => setTrigger(id)}>{label}</button>)}</div></fieldset>{reason && <blockquote>«{reason}»</blockquote>}<button className="path-button primary" disabled={busy || !techniques.length} type="button" onClick={begin}>{busy ? 'Сохраняем…' : 'Продолжить'} <span>→</span></button></section>}
    {step === 1 && <section className="path-coping-step"><span className="path-kicker">Выбери то, что подходит сейчас</span><h2 id="coping-title">Как переждём эту волну?</h2><div className="path-technique-list">{techniques.map(item => <button aria-pressed={technique === item.id} className={technique === item.id ? 'active' : ''} key={item.id} type="button" onClick={() => setTechnique(item.id)}><b>{item.title}</b><span>{Math.ceil(item.duration_seconds / 60)} мин.</span><small>{item.instruction}</small></button>)}</div><button className="path-button primary" disabled={busy || !selected} type="button" onClick={startTechnique}>{busy ? 'Сохраняем…' : `Начать · ${Math.ceil((selected?.duration_seconds || 0) / 60)} мин.`} <span>→</span></button></section>}
    {step === 2 && <section className="path-coping-step path-coping-active"><span className="path-kicker">{selected?.title}</span><h2 id="coping-title">Ты уже внутри паузы</h2><div className="path-coping-timer" role="timer" aria-label={`Осталось ${Math.ceil(remaining / 60)} минут`}><b>{formatTimer(remaining)}</b><span>{running ? 'идёт' : remaining ? 'пауза' : 'время прошло'}</span></div><p>{selected?.instruction}</p><button className="path-button primary" type="button" onClick={() => { setRunning(false); setStep(3); }}>Мне уже легче <span>→</span></button><div className="path-flow-secondary"><button type="button" onClick={togglePause}>{running ? 'Пауза' : 'Продолжить'}</button><button type="button" onClick={() => { setRunning(false); setStep(1); }}>Сменить способ</button></div></section>}
    {step === 3 && <section className="path-coping-step path-coping-complete"><span className="path-kicker">Честное наблюдение</span><h2 id="coping-title">Как тянет сейчас?</h2><label className="path-range">Сила тяги после паузы <b>{after} из 10</b><input aria-label="Сила тяги после паузы" type="range" min="1" max="10" value={after} onChange={event => setAfter(Number(event.target.value))} /></label><p>Любой ответ подходит. Он нужен только для твоей истории, а не для оценки результата.</p><button className="path-button primary" disabled={busy} type="button" onClick={complete}>{busy ? 'Сохраняем…' : 'Сохранить в журнал'} <span>✓</span></button></section>}
    {error && <p className="path-alert error" role="alert">{error}</p>}
  </PathDialog>;
}
