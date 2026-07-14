import { useState } from 'react';
import { PathDialog } from '../../ui/PathDialog';
import { PathState } from '../../ui/PathState';

const phaseLinks = [
  ['/dev/dashboard/preparation', 'Подготовка', 'Дата старта, опоры и переход к последней пачке'],
  ['/dev/dashboard/last-pack', 'Последняя пачка', 'Остаток, честная отметка и ручной старт отказа'],
  ['/dev/dashboard', 'Без сигарет', 'Текущий и лучший период, веха и одно главное действие'],
  ['/dev/dashboard/paused', 'Пауза', 'Сохранённая точка и мягкое возвращение'],
  ['/dev/dashboard/recovery', 'Восстановление', 'История не обнуляется после сложного момента'],
] as const;

export function PathShowcase() {
  const [dialogOpen, setDialogOpen] = useState(false);
  return <main className="path-app-shell path-settings-page">
    <header className="path-app-header"><a href="/" aria-label="На главную">←</a><div className="path-wordmark"><span>П</span><b>Система «Путь»</b></div><i /></header>
    <section className="path-screen-title"><span className="path-kicker">Только development</span><h1>Состояния интерфейса</h1><p>Одна визуальная грамматика для функциональных экранов, ошибок и диалогов.</p></section>
    <section className="path-settings-card path-settings-list"><header><div><span>Жизненный цикл</span><h2>Пять композиций главного экрана</h2></div></header>{phaseLinks.map(([href, title, description]) => <a href={href} key={href}><span><b>{title}</b><small>{description}</small></span><strong>→</strong></a>)}</section>
    <section className="path-settings-card"><header><div><span>Библиотека состояний</span><h2>Спокойная обратная связь</h2></div></header><PathState title="Здесь пока тихо" description="Пустое состояние объясняет следующий доступный шаг." /><PathState tone="error" title="Не удалось загрузить" description="Введённые данные сохранены. Можно безопасно повторить." /><button className="path-button primary" type="button" onClick={() => setDialogOpen(true)}>Открыть диалог <span>→</span></button></section>
    <PathDialog open={dialogOpen} onClose={() => setDialogOpen(false)} labelledBy="showcase-dialog-title"><header><div><span className="path-kicker">Фокус и клавиатура</span><h2 id="showcase-dialog-title">Диалог «Путь»</h2></div><button type="button" aria-label="Закрыть" onClick={() => setDialogOpen(false)}>×</button></header><p>Фокус остаётся внутри, Escape закрывает окно и возвращает фокус к исходному действию.</p><button data-autofocus className="path-button primary" type="button" onClick={() => setDialogOpen(false)}>Понятно</button></PathDialog>
  </main>;
}
