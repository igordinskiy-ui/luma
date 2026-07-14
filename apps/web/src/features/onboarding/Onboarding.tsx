import { FormEvent, useEffect, useState } from 'react';
import { api } from '../../api';

type StartMode = 'preparation' | 'last_pack' | 'quit';
type OnboardingDraft = {
  pack: number;
  remaining: number;
  price: number;
  startMode: StartMode;
  target: string;
  reasons: string;
  age: boolean;
  consent: boolean;
};

export const onboardingDraftKey = 'kurilka-onboarding-draft-v2';
type LegalIdentityProps = { legalVersion?: string; legalDigest?: string };
const startModeLabels: Record<StartMode, string> = {
  preparation: 'Готовлюсь',
  last_pack: 'Последняя пачка',
  quit: 'Уже не курю',
};

function localDateAfter(offsetMs: number) {
  const date = new Date(Date.now() + offsetMs);
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

function readOnboardingDraft(): OnboardingDraft {
  const fallback = { pack: 20, remaining: 20, price: 200, startMode: 'last_pack' as StartMode, target: localDateAfter(7 * 86400000) };
  try {
    const stored = JSON.parse(localStorage.getItem(onboardingDraftKey) || '{}') as Partial<OnboardingDraft>;
    const startMode = stored.startMode && ['preparation', 'last_pack', 'quit'].includes(stored.startMode) ? stored.startMode : fallback.startMode;
    return {
      pack: typeof stored.pack === 'number' ? stored.pack : fallback.pack,
      remaining: typeof stored.remaining === 'number' ? stored.remaining : fallback.remaining,
      price: typeof stored.price === 'number' ? stored.price : fallback.price,
      startMode,
      target: typeof stored.target === 'string' ? stored.target : fallback.target,
      reasons: '',
      age: false,
      consent: false,
    };
  } catch {
    return { ...fallback, reasons: '', age: false, consent: false };
  }
}

function ConsentProof({ legalVersion, legalDigest }: LegalIdentityProps) {
  const version = legalVersion || 'актуальная редакция';
  const shortDigest = legalDigest ? `${legalDigest.slice(0, 12)}…` : 'будет зафиксирован при публикации';
  return <aside className="path-consent-proof" aria-label="Редакция принимаемых документов">
    <span>Редакция документов</span>
    <b>{version}</b>
    <small>Отпечаток: <code aria-label={legalDigest ? `Полный отпечаток ${legalDigest}` : undefined} title={legalDigest || undefined}>{shortDigest}</code></small>
    <p>В истории согласий сохраняются редакция и отпечаток документов. План, заметки и прогресс к этой записи не добавляются.</p>
  </aside>;
}

export function ConsentRenewal({ onDone, legalVersion, legalDigest }: { onDone: () => void } & LegalIdentityProps) {
  const [error, setError] = useState('');
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      await api.consent();
      onDone();
    } catch {
      setError('Не удалось обновить согласие. Проверь соединение и попробуй ещё раз.');
    }
  };

  return <main className="path-page path-form-page">
    <header className="path-compact-header"><span className="path-logo-small">П</span><span>Последняя пачка</span></header>
    <section className="path-form-intro"><span className="path-kicker">Обновление документов</span><h1>Твой путь сохранён.<br />Подтверди условия.</h1><p>Мы обновили документы. План и все записи останутся на месте.</p></section>
    <form className="path-form-card" onSubmit={submit}>
      <ConsentProof legalVersion={legalVersion} legalDigest={legalDigest} />
      <label className="path-consent"><input name="age" type="checkbox" required /><span>Мне исполнилось 18 лет.</span></label>
      <label className="path-consent"><input name="consent" type="checkbox" required /><span>Я принимаю <a href="/terms.html" target="_blank" rel="noreferrer">условия использования</a> и <a href="/privacy.html" target="_blank" rel="noreferrer">политику конфиденциальности</a>.</span></label>
      <button className="path-button primary">Продолжить <span>→</span></button>
    </form>
    {error && <p className="path-alert error" role="alert">{error}</p>}
  </main>;
}

export function Onboarding({ onDone, legalVersion, legalDigest }: { onDone: () => void } & LegalIdentityProps) {
  const [error, setError] = useState('');
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState(readOnboardingDraft);

  useEffect(() => {
    localStorage.setItem(onboardingDraftKey, JSON.stringify({ pack: draft.pack, remaining: draft.remaining, price: draft.price, startMode: draft.startMode, target: draft.target }));
  }, [draft.pack, draft.remaining, draft.price, draft.startMode, draft.target]);

  const chooseMode = (startMode: StartMode) => setDraft(current => ({
    ...current,
    startMode,
    remaining: startMode === 'quit' ? 0 : Math.max(1, current.remaining || current.pack),
    target: startMode === 'preparation' ? current.target || localDateAfter(7 * 86400000) : current.target,
  }));

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    try {
      await api.onboard({
        cigarettes_per_pack: draft.pack,
        remaining: draft.remaining,
        pack_price: draft.price,
        reasons: draft.reasons,
        start_mode: draft.startMode,
        target_quit_at: draft.startMode === 'preparation' ? new Date(draft.target).toISOString() : null,
        age_confirmed: true,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        consent: true,
      });
      localStorage.removeItem(onboardingDraftKey);
      onDone();
    } catch {
      setError('Не удалось сохранить стартовый план. Несекретная часть черновика осталась на этом устройстве — проверь соединение и попробуй ещё раз.');
    }
  };

  const targetIsFuture = draft.startMode !== 'preparation' || (draft.target && new Date(draft.target).getTime() > Date.now());
  const canContinue = step === 0
    ? Boolean(draft.startMode && targetIsFuture)
    : step === 1
      ? draft.pack > 0 && draft.price >= 0 && (draft.startMode !== 'last_pack' || draft.remaining > 0)
      : step === 2
        ? true
        : draft.age && draft.consent;
  const modeSummary = draft.startMode === 'preparation' && draft.target
    ? `${startModeLabels[draft.startMode]} · ${new Date(draft.target).toLocaleString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })}`
    : startModeLabels[draft.startMode];

  return <main className="path-page path-form-page path-onboarding">
    <header className="path-compact-header"><span className="path-logo-small">П</span><span>Последняя пачка</span><small>Шаг {step + 1} из 4</small></header>
    <div className="path-stepper" aria-hidden="true">{[0, 1, 2, 3].map(item => <i key={item} className={item <= step ? 'active' : ''} />)}</div>
    <section className="path-form-intro"><span className="path-kicker">{['Точка старта', 'Твой контекст', 'Личная причина', 'Всё готово'][step]}</span><h1>{['Где начинается твой путь?', 'Добавим только нужные числа', 'Что делает этот путь твоим?', 'Первый шаг уже сделан'][step]}</h1><p>{['Выбери состояние, которое честно описывает сегодняшний день.', 'Они нужны для твоего плана и понятных расчётов.', 'Эту фразу можно будет увидеть в сложный момент. Поле необязательно.', 'Проверь данные и подтверди условия. Всё можно изменить позже.'][step]}</p></section>
    <form className="path-form-card" onSubmit={submit}>
      {step === 0 && <><div className="path-start-modes" aria-label="Точка старта">{(['preparation', 'last_pack', 'quit'] as const).map(mode => <button type="button" key={mode} className={draft.startMode === mode ? 'active' : ''} aria-pressed={draft.startMode === mode} onClick={() => chooseMode(mode)}><span>{mode === 'preparation' ? '○' : mode === 'last_pack' ? '◐' : '✓'}</span><b>{startModeLabels[mode]}</b><small>{mode === 'preparation' ? 'Выберу дату' : mode === 'last_pack' ? 'Завершу её осознанно' : 'Считаю текущий период'}</small></button>)}</div>{draft.startMode === 'preparation' && <label>Когда хочешь начать<input type="datetime-local" value={draft.target} min={localDateAfter(3600000)} onChange={event => setDraft({ ...draft, target: event.target.value })} required /></label>}</>}
      {step === 1 && <><div className="path-field-grid"><label>Сигарет в пачке<input name="pack" type="number" min="1" max="100" value={draft.pack} onChange={event => setDraft({ ...draft, pack: Number(event.target.value) })} required /></label>{draft.startMode !== 'quit' && <label>Осталось сейчас<input name="remaining" type="number" min={draft.startMode === 'last_pack' ? 1 : 0} max="100" value={draft.remaining} onChange={event => setDraft({ ...draft, remaining: Number(event.target.value) })} required /></label>}</div><label>Цена пачки, ₽<input name="price" type="number" min="0" value={draft.price} onChange={event => setDraft({ ...draft, price: Number(event.target.value) })} required /></label><div className="path-preview-metric"><span>Как используются числа</span><b>только для личного прогресса</b><small>Это приблизительные ориентиры, а не медицинские показатели.</small></div></>}
      {step === 2 && <><label>Моя причина<textarea name="reasons" value={draft.reasons} onChange={event => setDraft({ ...draft, reasons: event.target.value })} placeholder="Например: хочу легче начинать утро" maxLength={2000} /></label><small className="path-helper">Причина не сохраняется в черновике. Не указывай диагнозы, обследования или сведения о лечении.</small></>}
      {step === 3 && <><div className="path-review"><div><span>Старт</span><b>{modeSummary}</b></div><div><span>Пачка</span><b>{draft.pack} сигарет</b></div><div><span>Осталось</span><b>{draft.remaining}</b></div><div><span>Цена</span><b>{draft.price.toLocaleString('ru-RU')} ₽</b></div>{draft.reasons && <p>«{draft.reasons}»</p>}</div><ConsentProof legalVersion={legalVersion} legalDigest={legalDigest} /><label className="path-consent"><input name="age" type="checkbox" checked={draft.age} onChange={event => setDraft({ ...draft, age: event.target.checked })} required /><span>Мне исполнилось 18 лет.</span></label><label className="path-consent"><input name="consent" type="checkbox" checked={draft.consent} onChange={event => setDraft({ ...draft, consent: event.target.checked })} required /><span>Я принимаю <a href="/terms.html" target="_blank" rel="noreferrer">условия</a> и <a href="/privacy.html" target="_blank" rel="noreferrer">политику конфиденциальности</a>; понимаю, что сервис не заменяет медицинскую помощь и не гарантирует результат.</span></label></>}
      <div className="path-form-actions">{step > 0 && <button className="path-button ghost" type="button" onClick={() => setStep(value => value - 1)}>← Назад</button>}{step < 3 ? <button className="path-button primary" type="button" disabled={!canContinue} onClick={() => setStep(value => value + 1)}>Продолжить <span>→</span></button> : <button className="path-button primary" disabled={!canContinue}>Начать путь <span>→</span></button>}</div>
    </form>
    {error && <p className="path-alert error" role="alert">{error}</p>}
  </main>;
}
