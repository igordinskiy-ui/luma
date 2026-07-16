import { useEffect, useState } from 'react';
import { api, ApiError, authenticate, authToken, consumeOidcCompletion, currentUserId, Dashboard } from '../../api';
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

export function App({ initialScreen = 'home' }: { initialScreen?: AppScreen }) {
  const [state, setState] = useState<'loading' | 'landing' | 'auth' | 'consent' | 'onboarding' | 'dashboard' | 'offline' | 'rate' | 'maintenance' | 'service' | 'error'>('loading');
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [errorRequestId, setErrorRequestId] = useState<string | null>(null);
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
      else if (error instanceof ApiError && error.status === 401) setState('auth');
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
      catch { setState('auth'); return; }
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

  if (state === 'loading') return <main className="path-page path-loading" role="status"><span className="path-logo-large">П</span><i className="path-loader" /><p>Открываем твой путь…</p></main>;
  if (state === 'landing') return <Landing />;
  const supportCode = errorRequestId && <p className="path-request-id">Код обращения: <code>{errorRequestId}</code></p>;
  if (state === 'auth') return <main className="path-page path-state-page"><span className="path-logo-large">П</span><h1>Не удалось войти</h1><p>Открой помощника через Telegram-бота или обнови Mini App.</p>{supportCode}<a className="path-button primary" href="/">Попробовать ещё раз</a></main>;
  if (state === 'offline') return <main className="path-page path-state-page"><span className="path-logo-large">П</span><h1>Сейчас нет сети</h1><p>Честные отметки и начатые паузы останутся на устройстве. Подключись к сети и продолжи.</p><button className="path-button primary" type="button" onClick={refresh}>Проверить соединение</button></main>;
  if (state === 'rate') return <main className="path-page path-state-page"><span className="path-logo-large">П</span><h1>Нужна короткая пауза</h1><p>Запросов было слишком много. Подожди минуту — введённые данные не очищены.</p>{supportCode}<button className="path-button primary" type="button" onClick={refresh}>Повторить</button></main>;
  if (state === 'maintenance') return <main className="path-page path-state-page"><span className="path-logo-large">П</span><h1>Готовим запуск</h1><p>Сервис уже развёрнут, но вход пока закрыт. Мы откроем его после завершения проверок контента и документов.</p>{supportCode}<a className="path-button primary" href="/">На главную</a></main>;
  if (state === 'service') return <main className="path-page path-state-page"><span className="path-logo-large">П</span><h1>Сервис временно недоступен</h1><p>Твой путь и сохранённые отметки не потеряны. Подожди немного и попробуй подключиться снова.</p>{supportCode}<button className="path-button primary" type="button" onClick={refresh}>Попробовать снова</button><a href="/feedback">Сообщить о проблеме</a></main>;
  if (state === 'error') return <main className="path-page path-state-page"><span className="path-logo-large">П</span><h1>Не получилось открыть путь</h1><p>Попробуй ещё раз. Если ошибка повторяется, отправь обращение без медицинских и личных подробностей.</p>{supportCode}<button className="path-button primary" type="button" onClick={refresh}>Повторить</button><a href="/feedback">Обратная связь</a></main>;
  if (state === 'consent') return <ConsentRenewal onDone={refresh} legalVersion={legalIdentity.version} legalDigest={legalIdentity.digest} />;
  if (state === 'onboarding') return <Onboarding onDone={refresh} legalVersion={legalIdentity.version} legalDigest={legalIdentity.digest} />;
  return dashboard ? <DashboardView dashboard={dashboard} refresh={refresh} initialScreen={initialScreen} /> : null;
}
