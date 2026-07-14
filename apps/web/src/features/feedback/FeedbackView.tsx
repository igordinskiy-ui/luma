import { FormEvent, useState } from 'react';
import { api, ApiError } from '../../api';

export function FeedbackView() {
  const [category, setCategory] = useState<'bug' | 'idea' | 'support' | 'content'>('idea');
  const [body, setBody] = useState('');
  const [message, setMessage] = useState('');
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    try { await api.feedback({ category, body }); setBody(''); setMessage('Спасибо, сообщение отправлено.'); }
    catch (error) { setMessage(error instanceof ApiError && error.status === 401 ? 'Сначала войди в приложение через Telegram.' : 'Не удалось отправить сообщение. Попробуй ещё раз.'); }
  };
  return <main className="path-page path-form-page">
    <header className="path-compact-header"><a href="/" aria-label="Вернуться">←</a><span>Обратная связь</span></header>
    <section className="path-form-intro"><span className="path-kicker">Помоги сделать путь лучше</span><h1>Расскажи,<br />что думаешь</h1><p>Не указывай диагнозы или экстренные медицинские ситуации. Для срочной помощи обратись в местные службы.</p></section>
    <form className="path-form-card" onSubmit={submit}>
      <label>Тема<select value={category} onChange={event => setCategory(event.target.value as typeof category)}><option value="idea">Идея</option><option value="bug">Проблема в приложении</option><option value="content">Контент</option><option value="support">Поддержка</option></select></label>
      <label>Сообщение<textarea required minLength={3} maxLength={2000} value={body} onChange={event => setBody(event.target.value)} placeholder="Опиши ситуацию или предложение" /></label>
      <button className="path-button primary">Отправить <span>→</span></button>
    </form>
    {message && <p className="path-alert" role="status">{message}</p>}
  </main>;
}
