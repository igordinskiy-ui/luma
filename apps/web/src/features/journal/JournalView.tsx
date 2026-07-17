import { useEffect, useRef, useState } from 'react';
import { api, CopingTechniqueId, JournalItem, JournalResponse } from '../../api';
import { PathDialog } from '../../ui/PathDialog';
import './journal.css';

const triggers = [
  ['', 'Все триггеры'], ['stress', 'Стресс'], ['anger', 'Злость'], ['boredom', 'Скука'], ['physical', 'Телесная тяга'],
  ['coffee', 'Кофе'], ['after_meal', 'После еды'], ['driving', 'За рулём'], ['work_break', 'Перерыв'],
  ['social', 'В компании'], ['friends', 'С друзьями'], ['alcohol', 'Алкоголь'], ['focus', 'Сосредоточиться'], ['hands', 'Занять руки'], ['outside', 'На улице'], ['habit', 'По привычке'],
] as const;
const triggerLabel = (value?: string | null) => triggers.find(([id]) => id === value)?.[1] || 'Не указан';
const itemLabels = { craving: 'Тяга', smoked: 'Сигарета', relapse: 'Момент восстановления', coping: 'Пауза поддержки' } as const;
const techniqueLabels: Record<CopingTechniqueId, string> = { breathing: 'длинный выдох', delay: 'отложить решение', change_place: 'сменить пространство', walk: 'короткая прогулка', water: 'холодная вода', hands: 'занять руки', mouth: 'сменить вкус', grounding: 'пять ориентиров', focus_sprint: 'маленький фрагмент', social_exit: 'выйти из сценария', urge_surf: 'наблюдать волну', support_message: 'связаться с человеком' };
const outcomeLabels = { helped: 'стало легче', same: 'без изменений', worse: 'стало сильнее' } as const;

type Props = { onBack: () => void; onSupport: () => void; loadJournal?: typeof api.journal; updateEvent?: typeof api.updateEvent; deleteEvent?: typeof api.deleteEvent };

export function JournalView({ onBack, onSupport, loadJournal = api.journal, updateEvent = api.updateEvent, deleteEvent = api.deleteEvent }: Props) {
  const [period, setPeriod] = useState<'7d' | '30d' | 'all'>('7d');
  const [type, setType] = useState<'all' | JournalItem['type']>('all');
  const [trigger, setTrigger] = useState('');
  const [items, setItems] = useState<JournalItem[]>([]);
  const [summary, setSummary] = useState<JournalResponse['summary'] | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error' | 'more'>('loading');
  const [editing, setEditing] = useState<JournalItem | null>(null);
  const [editTrigger, setEditTrigger] = useState('');
  const [editIntensity, setEditIntensity] = useState(3);
  const [editNote, setEditNote] = useState('');
  const [editStatus, setEditStatus] = useState<'idle' | 'saving' | 'error'>('idle');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteStatus, setDeleteStatus] = useState<'idle' | 'deleting' | 'error'>('idle');
  const deleteConfirmRef = useRef<HTMLButtonElement>(null);
  useEffect(() => { if (confirmDelete) deleteConfirmRef.current?.focus(); }, [confirmDelete]);

  const load = async (nextCursor?: string, append = false) => {
    setStatus(append ? 'more' : 'loading');
    try {
      const result = await loadJournal({ period, type, trigger: trigger || undefined, cursor: nextCursor, limit: 20 });
      setItems(current => append ? [...current, ...result.items.filter(item => !current.some(existing => existing.id === item.id))] : result.items);
      setSummary(result.summary); setCursor(result.next_cursor); setStatus('ready');
    } catch { setStatus('error'); }
  };

  useEffect(() => { void load(); }, [period, type, trigger]);

  const groups = items.reduce<Record<string, JournalItem[]>>((result, item) => {
    const date = new Date(item.created_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
    (result[date] ||= []).push(item); return result;
  }, {});

  const beginEdit = (item: JournalItem) => {
    setEditing(item);
    setEditTrigger(item.trigger || '');
    setEditIntensity(Math.min(5, Math.max(1, item.intensity_before || 3)));
    setEditNote(item.note || '');
    setEditStatus('idle');
    setConfirmDelete(false);
    setDeleteStatus('idle');
  };

  const removeEvent = async () => {
    if (!editing) return;
    setDeleteStatus('deleting');
    try {
      await deleteEvent(Number(editing.id.split(':')[1]));
      setEditing(null);
      setConfirmDelete(false);
      setDeleteStatus('idle');
      await load();
    } catch {
      setDeleteStatus('error');
    }
  };

  const saveEdit = async () => {
    if (!editing) return;
    setEditStatus('saving');
    try {
      const id = Number(editing.id.split(':')[1]);
      const updated = await updateEvent(id, { trigger: editTrigger || null, intensity: editIntensity, note: editNote });
      setItems(current => current.map(item => item.id === editing.id ? { ...item, trigger: updated.trigger, intensity_before: updated.intensity, note: updated.note } : item));
      setEditing(null);
      setEditStatus('idle');
    } catch {
      setEditStatus('error');
    }
  };

  return <main className="path-app-shell path-journal-page">
    <header className="path-app-header"><button type="button" aria-label="Вернуться на главный экран" onClick={onBack}>←</button><div className="path-wordmark"><span>П</span><b>Мой путь</b></div><i /></header>
    <section className="path-screen-title"><span className="path-kicker">История без оценок</span><h1>Журнал</h1><p>События и паузы поддержки собраны в одной хронологии. Наблюдения появляются только когда данных достаточно.</p></section>
    <div className="path-segmented" aria-label="Период журнала">{([['7d', '7 дней'], ['30d', '30 дней'], ['all', 'Всё время']] as const).map(([id, label]) => <button aria-pressed={period === id} className={period === id ? 'active' : ''} type="button" key={id} onClick={() => setPeriod(id)}>{label}</button>)}</div>
    <div className="path-journal-controls"><div className="path-filter-row" aria-label="Тип события">{([['all', 'Все'], ['craving', 'Тяга'], ['coping', 'Поддержка'], ['smoked', 'Сигареты'], ['relapse', 'Восстановление']] as const).map(([id, label]) => <button aria-pressed={type === id} className={type === id ? 'active' : ''} type="button" key={id} onClick={() => setType(id)}>{label}</button>)}</div><label>Триггер<select value={trigger} onChange={event => setTrigger(event.target.value)}>{triggers.map(([id, label]) => <option value={id} key={id}>{label}</option>)}</select></label></div>
    <p className="path-edit-policy">Недавнюю поведенческую запись можно исправить в течение 15 минут. После этого она остаётся частью хронологии.</p>
    {summary && <><section className="path-journal-real-summary" aria-label="Сводка журнала"><div><span>Всего событий</span><b>{summary.total}</b></div><div><span>Пройдено пауз</span><b>{summary.coping_completed}</b></div><div><span>Частый триггер</span><b>{summary.top_trigger ? triggerLabel(summary.top_trigger) : '—'}</b></div></section><p className="path-journal-observation">{summary.sufficient_data ? summary.top_trigger ? `Чаще других встречается триггер «${triggerLabel(summary.top_trigger)}». Это наблюдение, а не диагноз.` : 'Данных уже достаточно для истории, но устойчивого частого триггера пока нет.' : 'Пока данных мало для честного вывода. Продолжай отмечать только то, что действительно произошло.'}</p></>}
    {status === 'loading' && <div className="path-state" role="status"><i className="path-loader" /><h2>Загружаем записи</h2></div>}
    {status === 'error' && <div className="path-state error" role="alert"><i>!</i><h2>Не удалось загрузить журнал</h2><p>Проверь соединение. Выбранные фильтры сохранены.</p><button className="path-button primary" type="button" onClick={() => load()}>Повторить</button></div>}
    {status !== 'loading' && status !== 'error' && items.length === 0 && <div className="path-state"><i>✦</i><h2>Здесь пока тихо</h2><p>Первая честная отметка поможет собрать историю без оценок.</p><button className="path-button primary" type="button" onClick={onSupport}>Зафиксировать тягу <span>→</span></button></div>}
    {Object.entries(groups).map(([date, entries]) => <section className="path-event-group" key={date}><header><h2>{date}</h2><span>{entries.length}</span></header><ol className="path-event-list">{entries.map(item => { const editable = item.source === 'event' && Boolean(item.editable_until) && new Date(item.editable_until!).getTime() > Date.now(); return <li key={item.id}><article><i className={`kind-${item.type}`}>{item.type === 'coping' ? '✓' : item.type === 'craving' ? '≈' : item.type === 'relapse' ? '↻' : '•'}</i><div><b>{itemLabels[item.type]}</b><span>{triggerLabel(item.trigger)}{item.intensity_before ? ` · ${item.intensity_before} из ${item.source === 'coping' ? 10 : 5}` : ''}</span>{item.type === 'coping' && <p>{item.technique ? techniqueLabels[item.technique] : 'Способ не выбран'}{item.intensity_after ? ` · после ${item.intensity_after} из 10` : ` · ${item.status === 'paused' ? 'на паузе' : item.status === 'abandoned' ? 'завершено раньше' : item.status}`}{item.outcome ? ` · ${outcomeLabels[item.outcome]}` : ''}</p>}{item.note && <p>{item.note}</p>}</div><div className="path-event-meta"><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}</time>{editable && <button type="button" onClick={() => beginEdit(item)}>Исправить</button>}</div></article></li>; })}</ol></section>)}
    {cursor && status !== 'error' && <button className="path-button quiet path-load-more" disabled={status === 'more'} type="button" onClick={() => load(cursor, true)}>{status === 'more' ? 'Загружаем…' : 'Показать ещё'}</button>}
    <PathDialog open={Boolean(editing)} onClose={() => setEditing(null)} labelledBy="journal-edit-title" className="path-edit-dialog"><header><div><span className="path-kicker">До 15 минут после записи</span><h2 id="journal-edit-title">{confirmDelete ? 'Убрать ошибочную отметку?' : 'Исправить событие'}</h2></div><button type="button" aria-label="Закрыть" onClick={() => setEditing(null)}>×</button></header>{confirmDelete ? <div className="path-delete-confirm"><p>{editing?.type === 'smoked' ? 'Запись исчезнет из журнала, а счётчик сигарет и этап пути вернутся к состоянию до этой отметки.' : editing?.type === 'relapse' ? 'Запись исчезнет, а предыдущий период без курения будет восстановлен, если после отметки путь не менялся.' : 'Запись исчезнет из журнала. Остальная история останется без изменений.'}</p>{deleteStatus === 'error' && <p className="path-alert error" role="alert">Не удалось убрать отметку. Возможно, 15 минут уже прошли или состояние пути изменилось.</p>}<button ref={deleteConfirmRef} className="path-button danger" type="button" disabled={deleteStatus === 'deleting'} onClick={() => void removeEvent()}>{deleteStatus === 'deleting' ? 'Убираем…' : 'Да, убрать отметку'}</button><button className="path-button ghost" type="button" disabled={deleteStatus === 'deleting'} onClick={() => { setConfirmDelete(false); setDeleteStatus('idle'); }}>Оставить запись</button></div> : <><label>Триггер события<select data-autofocus value={editTrigger} onChange={event => setEditTrigger(event.target.value)}>{triggers.map(([id, label]) => <option value={id} key={id}>{id ? label : 'Не указан'}</option>)}</select></label><label>Интенсивность: <b>{editIntensity} из 5</b><input aria-label="Интенсивность" type="range" min="1" max="5" value={editIntensity} onChange={event => setEditIntensity(Number(event.target.value))} /></label><label>Заметка<textarea maxLength={1000} value={editNote} onChange={event => setEditNote(event.target.value)} /></label>{editStatus === 'error' && <p className="path-alert error" role="alert">Не удалось сохранить. Возможно, окно исправления уже закрылось.</p>}<button className="path-button primary" type="button" disabled={editStatus === 'saving'} onClick={() => void saveEdit()}>{editStatus === 'saving' ? 'Сохраняем…' : 'Сохранить исправление'} <span>→</span></button><button className="path-remove-event" type="button" onClick={() => setConfirmDelete(true)}>Убрать ошибочную отметку</button></>}</PathDialog>
    <nav className="path-bottom-nav" aria-label="Основная навигация"><button type="button" onClick={onBack}><span>⌂</span>Сегодня</button><button className="support" type="button" onClick={onSupport}><span>＋</span>Поддержка</button><button className="active" type="button"><span>≡</span>Журнал</button></nav>
  </main>;
}
