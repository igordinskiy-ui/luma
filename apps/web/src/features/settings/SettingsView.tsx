import { useEffect, useState } from 'react';
import { api, ApiError, clearSession, currentUserId } from '../../api';
import { clearQueued } from '../../offline';
import { PathDialog } from '../../ui/PathDialog';
import { onboardingDraftKey } from '../onboarding/Onboarding';

function vapidBytes(value: string) {
  const padded = value + '='.repeat((4 - value.length % 4) % 4);
  const raw = atob(padded.replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(raw, char => char.charCodeAt(0));
}

function localDateTimeValue(value: string | number | Date) {
  const date = new Date(value);
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

export function SettingsView({ onBack }: { onBack: () => void }) {
  const [preferences, setPreferences] = useState({ enabled: false, max_daily: 3, quiet_start: 22, quiet_end: 9 });
  const [channel, setChannel] = useState<Awaited<ReturnType<typeof api.notificationStatus>> | null>(null);
  const [plan, setPlan] = useState<Awaited<ReturnType<typeof api.quitPlan>> | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletePhrase, setDeletePhrase] = useState('');
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [logoutOpen, setLogoutOpen] = useState(false);
  const [logoutBusy, setLogoutBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [planError, setPlanError] = useState('');
  const [preferencesReady, setPreferencesReady] = useState(false);
  useEffect(() => {
    Promise.allSettled([api.preferences(), api.notificationStatus(), api.quitPlan()]).then(([nextPreferences, status, nextPlan]) => {
      if (nextPreferences.status === 'fulfilled') { setPreferences(nextPreferences.value); setPreferencesReady(true); }
      if (status.status === 'fulfilled') setChannel(status.value);
      if (nextPlan.status === 'fulfilled') setPlan(nextPlan.value);
      if ([nextPreferences, status, nextPlan].some(result => result.status === 'rejected')) setMessage('Не удалось загрузить часть настроек. Ничего не изменено — обнови экран и попробуй снова.');
    });
  }, []);

  const exportData = async () => {
    try {
      const data = await api.export();
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
      const link = document.createElement('a');
      link.href = url; link.download = 'kurilka-data.json'; link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setMessage('Экспорт подготовлен. Проверь загрузки браузера.');
    } catch { setMessage('Не удалось подготовить экспорт. Данные не изменены — попробуй ещё раз.'); }
  };

  const enablePush = async () => {
    let subscription: PushSubscription | null = null;
    try {
      if (!('Notification' in window) || !('serviceWorker' in navigator)) return setMessage('Push не поддерживаются этим браузером.');
      if (await Notification.requestPermission() !== 'granted') return setMessage('Разрешение не выдано. Его можно изменить в настройках браузера.');
      const key = (await api.pushKey()).public_key;
      if (!key) return setMessage('Web push ещё не настроены на сервере.');
      const registration = await navigator.serviceWorker.ready;
      subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: vapidBytes(key) });
      const json = subscription.toJSON();
      await api.savePush({ endpoint: subscription.endpoint, p256dh: json.keys?.p256dh || '', auth: json.keys?.auth || '' });
      setChannel(await api.notificationStatus()); setMessage('Web push подключены. Отправь тест, чтобы проверить доставку.');
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        try { await subscription?.unsubscribe(); } catch { /* retry still remains safe because the server rejected ownership */ }
        setMessage('Подписка этого браузера была связана с другим профилем и очищена. Нажми «Подключить web push» ещё раз.');
      } else {
        setMessage('Не удалось подключить web push. Настройки сообщений не изменены.');
      }
    }
  };

  const disablePush = async () => {
    try {
      const registration = 'serviceWorker' in navigator ? await navigator.serviceWorker.ready : null;
      const subscription = await registration?.pushManager.getSubscription();
      await subscription?.unsubscribe();
      await api.deletePush(); setChannel(await api.notificationStatus()); setMessage('Web push отключены и подписка удалена.');
    } catch { setMessage('Не удалось полностью отключить web push. Попробуй ещё раз.'); }
  };

  const sendTest = async () => {
    try { await api.testNotification(); setMessage('Тест поставлен в очередь. Обычно он приходит в течение минуты.'); }
    catch (error) { setMessage(error instanceof ApiError && error.status === 409 ? 'Сейчас тест недоступен: проверь opt-in, тихие часы и подключённый канал.' : 'Не удалось отправить тест.'); }
  };

  const saveNotificationPreferences = async () => {
    try {
      await api.savePreferences(preferences);
      const status = await api.notificationStatus();
      setChannel(status);
      setMessage(!preferences.enabled
        ? 'Настройки сохранены. Рассылка выключена — новые сообщения не планируются.'
        : status.can_send_now
          ? 'Настройки сохранены. Сообщения могут приходить по расписанию.'
          : 'Настройки сохранены. Сейчас сообщения не планируются: действуют тихие часы или дневной лимит.');
    } catch { setMessage('Не удалось сохранить настройки.'); }
  };

  const savePlan = async () => {
    if (!plan) return;
    if (!Number.isInteger(plan.cigarettes_per_pack) || plan.cigarettes_per_pack < 1 || plan.cigarettes_per_pack > 100 || !Number.isFinite(plan.pack_price) || plan.pack_price < 0 || plan.pack_price > 1_000_000) {
      setMessage('');
      setPlanError('Проверь параметры пачки: количество — от 1 до 100, цена — от 0 до 1 000 000 ₽. Введённые данные остались на экране.');
      return;
    }
    if (plan.phase === 'preparation' && (!plan.target_quit_at || new Date(plan.target_quit_at).getTime() <= Date.now())) {
      setMessage('');
      setPlanError('Выбери дату и время в будущем. Введённые данные остались на экране.');
      return;
    }
    try {
      await api.plan({ reasons: plan.reasons, cigarettes_per_pack: plan.cigarettes_per_pack, pack_price: plan.pack_price, ...(plan.phase === 'preparation' ? { target_quit_at: plan.target_quit_at } : {}) });
      setPlanError('');
      setMessage('План обновлён. История осталась на месте.');
    } catch (error) {
      setPlanError(error instanceof ApiError && error.status === 422
        ? 'Проверь дату и параметры пачки. Введённые данные остались на экране.'
        : 'Не удалось обновить план. Введённые данные остались на экране.');
    }
  };

  const clearLocalDevice = async () => {
    try {
      const registration = 'serviceWorker' in navigator ? await navigator.serviceWorker.ready : null;
      await (await registration?.pushManager.getSubscription())?.unsubscribe();
    } catch { /* server-side logout/erasure remains the durable cleanup boundary */ }
    const userId = currentUserId();
    clearQueued(userId); clearSession(); localStorage.removeItem(onboardingDraftKey);
  };

  const logout = async () => {
    if (logoutBusy) return;
    setLogoutBusy(true);
    try {
      await api.logout();
      await clearLocalDevice();
      location.assign('/');
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        await clearLocalDevice();
        location.assign('/');
        return;
      }
      setLogoutBusy(false);
      setMessage('Не удалось выйти со всех устройств. Этот сеанс оставлен на месте — проверь соединение и повтори.');
    }
  };
  const eraseAccount = async () => {
    if (deletePhrase !== 'УДАЛИТЬ' || deleteBusy) return;
    setDeleteBusy(true);
    try { await api.erase(); await clearLocalDevice(); location.assign('/'); }
    catch { setDeleteBusy(false); setMessage('Не удалось удалить аккаунт. Данные не изменены — попробуй ещё раз.'); }
  };

  return <main className="path-app-shell path-settings-page">
    <header className="path-app-header"><button type="button" aria-label="Вернуться на главный экран" onClick={onBack}>←</button><div className="path-wordmark"><span>П</span><b>Мой профиль</b></div><i /></header>
    <section className="path-screen-title"><span className="path-kicker">Твой темп</span><h1>Настройки</h1><p>Поддержка должна приходить тогда, когда она уместна.</p></section>
    {plan && <section className="path-settings-card"><header><div><span>План</span><h2>Твоя опора</h2></div></header><label>Почему это важно<textarea maxLength={2000} value={plan.reasons} onChange={event => setPlan({ ...plan, reasons: event.target.value })} /></label><div className="path-field-grid"><label>Сигарет в пачке<input type="number" required min="1" max="100" aria-describedby="plan-number-help" aria-invalid={Boolean(planError)} value={plan.cigarettes_per_pack} onChange={event => { setPlanError(''); setPlan({ ...plan, cigarettes_per_pack: Number(event.target.value) }); }} /></label><label>Цена пачки, ₽<input type="number" required min="0" max="1000000" step="0.01" aria-describedby="plan-number-help" aria-invalid={Boolean(planError)} value={plan.pack_price} onChange={event => { setPlanError(''); setPlan({ ...plan, pack_price: Number(event.target.value) }); }} /></label></div><p className="path-setting-explainer" id="plan-number-help">Эти значения меняют только будущие приблизительные расчёты. События и лучший период остаются на месте.</p>{plan.phase === 'preparation' && <label>Дата старта<input type="datetime-local" required min={localDateTimeValue(Date.now() + 5 * 60_000)} aria-describedby="plan-date-help" aria-invalid={Boolean(planError)} value={plan.target_quit_at ? localDateTimeValue(plan.target_quit_at) : ''} onChange={event => { setPlanError(''); setPlan({ ...plan, target_quit_at: event.target.value ? new Date(event.target.value).toISOString() : null }); }} /><small className="path-helper" id="plan-date-help">Время указано по часовому поясу этого устройства. Его можно изменить до начала пути.</small></label>}{planError && <p className="path-alert error" role="alert">{planError}</p>}<button className="path-button primary" type="button" onClick={() => void savePlan()}>Сохранить план <span>→</span></button></section>}
    <section className="path-settings-card" aria-busy={!preferencesReady}><header><div><span>Напоминания</span><h2>Поддерживающие сообщения</h2></div><label className="path-switch"><span className="sr-only">Разрешить поддерживающие сообщения</span><input type="checkbox" disabled={!preferencesReady} checked={preferences.enabled} onChange={event => setPreferences({ ...preferences, enabled: event.target.checked })} /><i /></label></header>{!preferencesReady && <p className="path-setting-loading" role="status">Загружаем сохранённое расписание…</p>}<p className="path-setting-explainer">Если включить сообщения, мы напомним о выбранном шаге — без заметок, причин и других личных подробностей. Сначала сохрани расписание, затем выбери канал.</p><label>Максимум сообщений в день<select disabled={!preferencesReady} value={preferences.max_daily} onChange={event => setPreferences({ ...preferences, max_daily: Number(event.target.value) })}>{[0, 1, 2, 3, 4, 5, 6].map(value => <option key={value} value={value}>{value === 0 ? 'Не отправлять' : value}</option>)}</select></label><div className="path-field-grid"><label>Не беспокоить с<input type="number" disabled={!preferencesReady} min="0" max="23" value={preferences.quiet_start} onChange={event => setPreferences({ ...preferences, quiet_start: Number(event.target.value) })} /></label><label>до<input type="number" disabled={!preferencesReady} min="0" max="23" value={preferences.quiet_end} onChange={event => setPreferences({ ...preferences, quiet_end: Number(event.target.value) })} /></label></div><button type="button" disabled={!preferencesReady} className="path-button primary" onClick={saveNotificationPreferences}>Сохранить расписание <span>→</span></button><div className="path-channel-card"><div><span>Telegram</span><b>{channel?.telegram === 'available' ? 'Доступен' : 'Не настроен'}</b></div><div><span>Web push</span><b>{channel?.web_push === 'subscribed' ? 'Подключён' : 'Не подключён'}</b></div></div><div className="path-notification-actions"><button type="button" disabled={!preferencesReady} className="path-button ghost" onClick={enablePush}>Подключить web push</button>{channel?.web_push === 'subscribed' && <button type="button" className="path-button ghost" onClick={disablePush}>Отключить web push</button>}<button type="button" className="path-button quiet" disabled={!preferencesReady || !preferences.enabled} onClick={sendTest}>Отправить тест</button></div></section>
    {message && <p className="path-alert" role="status">{message}</p>}
    <section className="path-settings-card path-settings-list"><header><div><span>Данные и помощь</span><h2>Управление</h2></div></header><button type="button" onClick={exportData}><span><b>Экспортировать данные</b><small>Скачать полную копию в JSON</small></span><strong>→</strong></button><a href="/feedback"><span><b>Обратная связь</b><small>Идея, проблема или вопрос</small></span><strong>→</strong></a><a href="/privacy.html"><span><b>Конфиденциальность</b><small>Как мы работаем с данными</small></span><strong>→</strong></a><a href="/terms.html"><span><b>Условия использования</b></span><strong>→</strong></a><button type="button" onClick={() => { setLogoutBusy(false); setLogoutOpen(true); }}><span><b>Выйти со всех устройств</b><small>Закрыть все сеансы и удалить web-push подписки</small></span><strong>→</strong></button></section>
    <section className="path-danger-zone"><h2>Удаление аккаунта</h2><p>Активные данные, очереди и подписки будут удалены. Ротация резервных копий описана в политике хранения.</p><button type="button" onClick={() => { setDeletePhrase(''); setDeleteBusy(false); setDeleteOpen(true); }}>Удалить аккаунт</button></section>
    <PathDialog open={logoutOpen} onClose={() => { if (!logoutBusy) setLogoutOpen(false); }} labelledBy="logout-title"><div aria-busy={logoutBusy}><header><div><span className="path-kicker">Без потери данных</span><h2 id="logout-title">Выйти со всех устройств?</h2></div><button type="button" disabled={logoutBusy} aria-label="Закрыть" onClick={() => setLogoutOpen(false)}>×</button></header><p>Все текущие сеансы будут закрыты, а web-push подписки удалены. План и журнал останутся на месте. Расписание Telegram можно отключить выше.</p><div className="path-state-actions"><button data-autofocus className="path-button ghost" disabled={logoutBusy} type="button" onClick={() => setLogoutOpen(false)}>Остаться</button><button className="path-button primary" disabled={logoutBusy} type="button" onClick={() => void logout()}>{logoutBusy ? 'Закрываем сеансы…' : 'Выйти со всех устройств'}</button></div></div></PathDialog>
    <PathDialog open={deleteOpen} onClose={() => { if (!deleteBusy) setDeleteOpen(false); }} labelledBy="delete-title"><div aria-busy={deleteBusy}><header><div><span className="path-kicker">Необратимое действие</span><h2 id="delete-title">Удалить весь путь?</h2></div><button type="button" disabled={deleteBusy} aria-label="Закрыть" onClick={() => setDeleteOpen(false)}>×</button></header><p>Экспортируй данные заранее, если хочешь сохранить копию. Для подтверждения введи <b>УДАЛИТЬ</b>.</p><label>Подтверждение<input data-autofocus disabled={deleteBusy} autoComplete="off" value={deletePhrase} onChange={event => setDeletePhrase(event.target.value)} /></label><button className="path-button danger" disabled={deletePhrase !== 'УДАЛИТЬ' || deleteBusy} type="button" onClick={eraseAccount}>{deleteBusy ? 'Удаляем аккаунт…' : 'Удалить аккаунт безвозвратно'}</button></div></PathDialog>
    <p className="path-medical-note">Если тебе плохо — обратись к врачу или в экстренную службу.</p>
  </main>;
}
