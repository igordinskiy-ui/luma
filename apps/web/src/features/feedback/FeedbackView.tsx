import { FormEvent, useEffect, useState } from 'react';
import { api, ApiError, authenticate, authToken, beginOidcLogin, consumeOidcCompletion, OidcCompletionError } from '../../api';
import { initialiseTelegram } from '../../telegram';

export function FeedbackView() {
  const [category, setCategory] = useState<'bug' | 'idea' | 'support' | 'content'>('idea');
  const [body, setBody] = useState('');
  const [message, setMessage] = useState('');
  const [authState, setAuthState] = useState<'loading' | 'ready' | 'auth' | 'temporary' | 'expired'>('loading');

  const finishAuthentication = async () => {
    try {
      await consumeOidcCompletion();
      setAuthState(authToken() ? 'ready' : 'auth');
    } catch (error) {
      setAuthState(error instanceof OidcCompletionError && error.retryable ? 'temporary' : 'expired');
    }
  };

  useEffect(() => {
    const bootstrap = async () => {
      await finishAuthentication();
      if (authToken()) return;
      const telegram = initialiseTelegram();
      if (!telegram?.initData) return;
      try { await authenticate(telegram.initData); setAuthState('ready'); }
      catch { setAuthState('auth'); }
    };
    void bootstrap();
  }, []);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    try { await api.feedback({ category, body }); setBody(''); setMessage('Спасибо, сообщение отправлено.'); }
    catch (error) {
      if (error instanceof ApiError && error.status === 401) { setAuthState('auth'); setMessage('Сессия завершилась. Войди снова — сообщение останется на экране.'); }
      else setMessage('Не удалось отправить сообщение. Попробуй ещё раз.');
    }
  };
  return <main className="path-page path-form-page">
    <header className="path-compact-header"><a href="/" aria-label="Вернуться">←</a><span>Обратная связь</span></header>
    <section className="path-form-intro"><span className="path-kicker">Помоги сделать путь лучше</span><h1>Расскажи,<br />что думаешь</h1><p>Не указывай диагнозы или экстренные медицинские ситуации. Для срочной помощи обратись в местные службы.</p></section>
    {authState === 'loading' && <div className="path-alert" role="status">Проверяем безопасный вход…</div>}
    {authState !== 'loading' && authState !== 'ready' && <div className="path-alert" role="status"><p>{authState === 'temporary' ? 'Связь прервалась при завершении входа. Можно повторить обмен без потери маршрута.' : authState === 'expired' ? 'Время подтверждения истекло. Начни вход заново — мы вернём тебя сюда.' : 'Войди через Telegram, чтобы отправить сообщение безопасно.'}</p><div className="path-state-actions">{authState === 'temporary' && <button className="path-button primary" type="button" onClick={finishAuthentication}>Повторить завершение</button>}<button className={authState === 'temporary' ? 'path-button ghost' : 'path-button primary'} type="button" onClick={beginOidcLogin}>{authState === 'temporary' ? 'Начать вход заново' : 'Войти через Telegram'}</button></div></div>}
    {authState === 'ready' && <form className="path-form-card" onSubmit={submit}>
      <label>Тема<select value={category} onChange={event => setCategory(event.target.value as typeof category)}><option value="idea">Идея</option><option value="bug">Проблема в приложении</option><option value="content">Контент</option><option value="support">Поддержка</option></select></label>
      <label>Сообщение<textarea required minLength={3} maxLength={2000} value={body} onChange={event => setBody(event.target.value)} placeholder="Опиши ситуацию или предложение" /></label>
      <button className="path-button primary">Отправить <span>→</span></button>
    </form>}
    {message && <p className="path-alert" role="status">{message}</p>}
  </main>;
}
