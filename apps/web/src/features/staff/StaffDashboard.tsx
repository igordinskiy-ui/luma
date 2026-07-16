import { useEffect, useState } from 'react';
import { api, AdminFeedback, AdminOverview, ApiError, authenticate, authToken, beginOidcLogin, consumeOidcCompletion } from '../../api';
import { initialiseTelegram } from '../../telegram';

export function StaffDashboard() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [feedback, setFeedback] = useState<AdminFeedback[]>([]);
  const [feedbackStatus, setFeedbackStatus] = useState<'open' | 'resolved'>('open');
  const [staffPeriod, setStaffPeriod] = useState<'7d' | '30d' | '90d' | 'all'>('30d');
  const [staffSource, setStaffSource] = useState('');
  const [message, setMessage] = useState('Загружаем staff-панель…');

  const load = async (status: 'open' | 'resolved' = feedbackStatus, period = staffPeriod, source = staffSource) => {
    try {
      const [nextOverview, nextFeedback] = await Promise.all([api.adminOverview(period, source), api.adminFeedback(status)]);
      setOverview(nextOverview); setFeedback(nextFeedback); setMessage('');
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) setMessage('Войди через Telegram, чтобы открыть staff-панель.');
      else if (error instanceof ApiError && error.status === 403) setMessage('Этот Telegram-аккаунт не добавлен в ADMIN_TELEGRAM_IDS.');
      else setMessage('Не удалось загрузить staff-панель.');
    }
  };

  useEffect(() => {
    document.body.dataset.design = 'path';
    const telegram = initialiseTelegram();
    const bootstrap = async () => {
      try { await consumeOidcCompletion(); }
      catch { setMessage('Не удалось завершить вход через Telegram.'); return; }
      if (authToken()) { await load(); return; }
      if (telegram?.initData) authenticate(telegram.initData).then(() => load()).catch(() => setMessage('Не удалось авторизоваться через Telegram.'));
      else setMessage('Открой staff-панель внутри Telegram или войди через Telegram Login.');
    };
    void bootstrap();
  }, []);

  const resolve = async (id: number) => {
    try { await api.updateAdminFeedback(id, 'resolved'); await load(); }
    catch { setMessage('Не удалось изменить статус обращения. Ничего не потеряно.'); }
  };

  return <main className="path-app-shell path-staff-page">
    <header className="path-app-header"><a className="path-staff-back" href="/" aria-label="Вернуться в приложение">←</a><div className="path-wordmark"><span>П</span><b>Команда продукта</b></div><i /></header>
    <section className="path-screen-title"><span className="path-kicker">Без медицинской интерпретации</span><h1>Пилот</h1><p>Операционные метрики и очередь обращений. В панели нет Telegram ID и пользовательских причин.</p></section>
    <section className="path-staff-filters" aria-label="Фильтры метрик"><label>Период<select value={staffPeriod} onChange={event => { const value = event.target.value as typeof staffPeriod; setStaffPeriod(value); void load(feedbackStatus, value, staffSource); }}><option value="7d">7 дней</option><option value="30d">30 дней</option><option value="90d">90 дней</option><option value="all">Всё время</option></select></label><label>Источник<select value={staffSource} onChange={event => { const value = event.target.value; setStaffSource(value); void load(feedbackStatus, staffPeriod, value); }}><option value="">Все allowlisted</option><option value="direct">Прямой</option>{Object.keys(overview?.users_by_acquisition_source || {}).filter(value => value !== 'direct').map(value => <option value={value} key={value}>{value}</option>)}</select></label></section>
    {message && <div className="path-alert" role="status"><p>{message}</p>{!authToken() && <button className="path-button primary" type="button" onClick={beginOidcLogin}>Войти через Telegram <span>→</span></button>}</div>}
    {overview && <>
      <div className="metrics"><div><b>{overview.users_total}</b><span>всего пользователей</span></div><div><b>{overview.events_last_24h}</b><span>событий за 24 часа</span></div><div><b>{overview.open_feedback}</b><span>открытых feedback</span></div><div><b>{Object.values(overview.deliveries_last_24h).reduce((sum, value) => sum + value, 0)}</b><span>доставок за 24 часа</span></div></div>
      <p className="path-metric-note">D1, D7 и D14 — действие в соответствующие 24 часа пути. В знаменатель входят только полностью завершённые окна; поздний возврат не меняет прошлую retention. Delivery failure считается только по завершённым попыткам: sent + failed, без очереди. Crash-free: <b>{(overview.client_health.crash_free_rate * 100).toFixed(2)}%</b> ({overview.client_health.crashed} из {overview.client_health.sessions} сессий).</p>
      <section className="card"><h2>Операционный статус</h2><p>Контент: <b>{overview.content_review_status}</b> · версия <code>{overview.content_version}</code> · отпечаток <code>{overview.content_digest.slice(0, 12)}</code> · режим общих подсказок: <b>{overview.risk_engine_version}</b></p><p>Activation: <b>{overview.activation.onboarded}</b> ({Math.round(overview.activation.rate * 100)}%) · mute rate: <b>{Math.round(overview.notification_health.mute_rate * 100)}%</b></p><p>Первое действие ≤24 ч: <b>{overview.funnel.first_action_24h}/{overview.funnel.onboarded}</b> ({Math.round(overview.funnel.first_action_rate * 100)}%)</p><p>D1: {overview.retention.d1.retained}/{overview.retention.d1.eligible} · D7: {overview.retention.d7.retained}/{overview.retention.d7.eligible} · D14: {overview.retention.d14.retained}/{overview.retention.d14.eligible}</p><p>Delivery failures за 24 часа: <b>{overview.notification_health.delivery_failures_last_24h}</b> ({Math.round(overview.notification_health.delivery_failure_rate * 100)}%)</p><p>Планы: {Object.entries(overview.plans_by_phase).map(([phase, count]) => `${phase}: ${count}`).join(' · ') || 'нет'}</p><p>Outbox: {Object.entries(overview.outbox_by_status).map(([status, count]) => `${status}: ${count}`).join(' · ') || 'нет'}</p></section>
      <section className="card"><header className="path-staff-section-header"><div><span className="path-kicker">Без чувствительных идентификаторов</span><h2>Обратная связь</h2></div><div className="path-filter-row" aria-label="Статус обращения"><button aria-pressed={feedbackStatus === 'open'} className={feedbackStatus === 'open' ? 'active' : ''} type="button" onClick={() => { setFeedbackStatus('open'); void load('open'); }}>Открытые</button><button aria-pressed={feedbackStatus === 'resolved'} className={feedbackStatus === 'resolved' ? 'active' : ''} type="button" onClick={() => { setFeedbackStatus('resolved'); void load('resolved'); }}>Закрытые</button></div></header>{feedback.length ? feedback.map(item => <article className="feedback-item" key={item.id}><span className="eyebrow">{item.category} · #{item.id}</span><p>{item.body}</p><small>{new Date(item.created_at).toLocaleString('ru-RU')}</small>{item.status === 'open' && <button type="button" className="path-button quiet" onClick={() => resolve(item.id)}>Закрыть обращение</button>}</article>) : <p>В этой очереди сообщений нет.</p>}</section>
    </>}
  </main>;
}
