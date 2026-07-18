import { useEffect, useState } from 'react';
import { api, ApiError, authenticate, authToken, beginOidcLogin, consumeOidcCompletion, currentUserId, Dashboard, OidcCompletionError } from '../../api';
import { syncQueued } from '../../offline';
import { initialiseTelegram } from '../../telegram';
import { DashboardView } from '../journey/DashboardView';
import { ConsentRenewal, Onboarding } from '../onboarding/Onboarding';
import { Landing } from '../public/PublicPages';

export type AppScreen = 'home' | 'journal' | 'settings';
const clientSessionKey = 'kurilka-client-session-id';
const clientCrashKey = 'kurilka-client-crash-reported';

function clientSessionId() {
  let value = sessionStorage.getItem(clientSessionKey);
  if (!value) { value = crypto.randomUUID(); sessionStorage.setItem(clientSessionKey, value); }
  return value;
}

export function App({ initialScreen = 'home', initialSupport = false }: { initialScreen?: AppScreen; initialSupport?: boolean }) {
  const [state, setState] = useState<'loading' | 'landing' | 'auth' | 'consent' | 'onboarding' | 'dashboard' | 'offline' | 'rate' | 'maintenance' | 'service' | 'error'>('loading');
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [errorRequestId, setErrorRequestId] = useState<string | null>(null);
  const [authIssue, setAuthIssue] = useState<'session' | 'expired' | 'temporary'>('session');
  const [legalIdentity, setLegalIdentity] = useState({ version: '', digest: '' });
  const refresh = async () => {
    setErrorRequestId(null);
    if (authToken()) void api.clientTelemetry('session_started', clientSessionId()).catch(() => undefined);
    await syncQueued(currentUserId());
    try {
      const bootstrap = await api.bootstrap();
      setLegalIdentity({ version: bootstrap.legal_documents_version || '', digest: bootstrap.legal_documents_digest || '' });
      if (!bootstrap.onboarded) { setState('onboarding'); return; }
      if (!bootstrap.age_confirmed || !bootstrap.consent_current) { setState('consent'); return; }
      setDashboard(await api.dashboard()); setState('dashboard');
    } catch (error) {
      if (error instanceof ApiError) setErrorRequestId(error.requestId || null);
      if (!navigator.onLine || error instanceof TypeError) setState('offline');
      else if (error instanceof ApiError && error.status === 401) { setAuthIssue('session'); setState('auth'); }
      else if (error instanceof ApiError && error.status === 429) setState('rate');
      else if (error instanceof ApiError && error.status === 503 && error.code === 'public_launch_disabled') setState('maintenance');
      else if (error instanceof ApiError && error.status === 503) setState('service');
      else setState('error');
    }
  };

  useEffect(() => {
    document.body.dataset.design = 'path';
    localStorage.removeItem('design-direction');
    const telegram = initialiseTelegram();
    const bootstrap = async () => {
      try { await consumeOidcCompletion(); }
      catch (error) {
        setAuthIssue(error instanceof OidcCompletionError && error.retryable ? 'temporary' : 'expired');
        setState('auth'); return;
      }
      if (authToken()) { await refresh(); return; }
      if (!telegram?.initData) { setState('landing'); return; }
      authenticate(telegram.initData).then(refresh).catch(async () => {
        try { setState((await api.launchStatus()).public_launch_enabled ? 'auth' : 'maintenance'); }
        catch { setState('auth'); }
      });
    };
    void bootstrap();
    const reportCrash = () => {
      if (!authToken() || sessionStorage.getItem(clientCrashKey)) return;
      sessionStorage.setItem(clientCrashKey, '1');
      void api.clientTelemetry('crash', clientSessionId()).catch(() => undefined);
    };
    window.addEventListener('error', reportCrash);
    window.addEventListener('unhandledrejection', reportCrash);
    window.addEventListener('online', refresh);
    return () => {
      window.removeEventListener('error', reportCrash);
      window.removeEventListener('unhandledrejection', reportCrash);
      window.removeEventListener('online', refresh);
    };
  }, []);

  const retryOidcCompletion = async () => {
    setState('loading');
    try {
      const consumed = await consumeOidcCompletion();
      if (!consumed) { setAuthIssue('expired'); setState('auth'); return; }
      await refresh();
    } catch (error) {
      setAuthIssue(error instanceof OidcCompletionError && error.retryable ? 'temporary' : 'expired');
      setState('auth');
    }
  };

  if (state === 'loading') return <main className="path-page path-loading" role="status"><span className="path-logo-large">П</span><i className="path-loader" /><p>Открываем твой путь…</p></main>;
  if (state === 'landing') return <Landing />;
  const supportCode = errorRequestId && <p className="path-request-id">Код обращения: <code>{errorRequestId}</code></p>;
  if (state === 'auth') return <main className="path-page path-state-page" aria-live="assertive"><span className="path-logo-large">П</span><span className="path-kicker">Без потери прогресса</span><h1>{authIssue === 'temporary' ? 'Связь прервалась' : authIssue === 'expired' ? 'Время входа истекло' : 'Нужно войти снова'}</h1><p>{authIssue === 'temporary' ? 'Telegram уже подтвердил вход. Повтори завершение — сохранённый план и текущий экран останутся на месте.' : authIssue === 'expired' ? 'Одноразовое подтверждение больше не действует. Начни вход заново — мы вернём тебя на этот экран.' : 'Сессия завершилась. Войди через Telegram, чтобы безопасно продолжить с этого места.'}</p>{supportCode}<div className="path-state-actions">{authIssue === 'temporary' && <button className="path-button primary" type="button" onClick={retryOidcCompletion}>Повторить завершение</button>}<button className={authIssue === 'temporary' ? 'path-button ghost' : 'path-button primary'} type="button" onClick={beginOidcLogin}>{authIssue === 'temporary' ? 'Начать вход заново' : 'Войти через Telegram'}</button></div><a href="/">На главную</a></main>;
  if (state === 'offline') return <main className="path-page path-state-page" aria-live="polite"><span className="path-logo-large">П</span><h1>Сейчас нет сети</h1><p>Честные отметки и начатые паузы останутся на устройстве. Подключись к сети и продолжи.</p><button className="path-button primary" type="button" onClick={refresh}>Проверить соединение</button></main>;
  if (state === 'rate') return <main className="path-page path-state-page" aria-live="polite"><span className="path-logo-large">П</span><h1>Нужна короткая пауза</h1><p>Запросов было слишком много. Подожди минуту — введённые данные не очищены.</p>{supportCode}<button className="path-button primary" type="button" onClick={refresh}>Повторить</button></main>;
  if (state === 'maintenance') return <main className="path-page path-state-page" aria-live="polite"><span className="path-logo-large">П</span><h1>Готовим запуск</h1><p>Сервис уже развёрнут, но вход пока закрыт. Мы откроем его после завершения проверок контента и документов.</p>{supportCode}<a className="path-button primary" href="/">На главную</a></main>;
  if (state === 'service') return <main className="path-page path-state-page" aria-live="assertive"><span className="path-logo-large">П</span><h1>Сервис временно недоступен</h1><p>Твой путь и сохранённые отметки не потеряны. Подожди немного и попробуй подключиться снова.</p>{supportCode}<button className="path-button primary" type="button" onClick={refresh}>Попробовать снова</button><a href="/feedback">Сообщить о проблеме</a></main>;
  if (state === 'error') return <main className="path-page path-state-page" aria-live="assertive"><span className="path-logo-large">П</span><h1>Не получилось открыть путь</h1><p>Попробуй ещё раз. Если ошибка повторяется, отправь обращение без медицинских и личных подробностей.</p>{supportCode}<button className="path-button primary" type="button" onClick={refresh}>Повторить</button><a href="/feedback">Обратная связь</a></main>;
  if (state === 'consent') return <ConsentRenewal onDone={refresh} legalVersion={legalIdentity.version} legalDigest={legalIdentity.digest} />;
  if (state === 'onboarding') return <Onboarding onDone={refresh} legalVersion={legalIdentity.version} legalDigest={legalIdentity.digest} />;
  return dashboard ? <DashboardView dashboard={dashboard} refresh={refresh} initialScreen={initialScreen} initialSupport={initialSupport} /> : null;
}
