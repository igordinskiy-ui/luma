import { useEffect, useState } from 'react';
import { api, beginOidcLogin } from '../../api';

const guideContent = {
  craving: { title: 'Что делать в момент тяги', kicker: 'Короткая пауза вместо приказа', intro: 'Тягу не нужно оценивать или побеждать идеально. Зафиксируй её силу, назови триггер и выбери одно короткое действие.', steps: ['Оцени силу тяги от 1 до 10.', 'Назови контекст без длинной заметки.', 'Выбери воду, прогулку или спокойный выдох.', 'После паузы честно отметь, что изменилось.'] },
  coffee: { title: 'Если триггер — кофе', kicker: 'Меняем связку, а не себя', intro: 'Кофе может быть частью привычного сценария. Попробуй изменить только один элемент: место, напиток после чашки или первые минуты после неё.', steps: ['Заранее поставь рядом воду.', 'После кофе смени место на несколько минут.', 'Отметь тягу, если она появилась.', 'Сравни только реальные записи за несколько дней.'] },
  recovery: { title: 'Как вернуться после срыва', kicker: 'История не обнуляется', intro: 'Один сложный момент не стирает пройденное. Сервис сохранит лучший период и начнёт новую попытку без красных наказаний.', steps: ['Зафиксируй событие без самообвинения.', 'Убери оставшиеся сигареты из быстрого доступа.', 'Выбери короткую опору на ближайшие минуты.', 'Вернись к плану в своём темпе.'] },
} as const;

export type GuideName = keyof typeof guideContent;

function setMetadata(title: string, descriptionText: string) {
  document.title = title;
  const description = document.querySelector('meta[name=description]') ?? document.head.appendChild(document.createElement('meta'));
  description.setAttribute('name', 'description');
  description.setAttribute('content', descriptionText);
}

export function GuidePage({ guide }: { guide: GuideName }) {
  const content = guideContent[guide];
  useEffect(() => setMetadata(`${content.title} — Luma`, content.intro), [content]);
  return <main className="path-page path-guide"><header className="path-public-header"><a className="path-wordmark" href="/"><img className="path-brand-mark" src="/brand/luma-mark.svg" alt="" /><b>Luma</b></a><a href="/">О продукте</a></header><article><span className="path-kicker">{content.kicker}</span><h1>{content.title}</h1><p className="path-guide-intro">{content.intro}</p><ol>{content.steps.map((step, index) => <li key={step}><i>{index + 1}</i><span>{step}</span></li>)}</ol><aside>Это немедицинский помощник. При плохом самочувствии или экстренной ситуации обратись к врачу или местной службе помощи.</aside><a className="path-button primary" href="/app">Открыть помощника <span>→</span></a></article></main>;
}

export function Landing() {
  const [publicLaunch, setPublicLaunch] = useState<boolean | null>(null);
  useEffect(() => {
    setMetadata('Luma', 'Немедицинский помощник на пути от последней пачки к жизни без сигарет — без стыда и обещаний невозможного.');
    void api.launchStatus().then(status => setPublicLaunch(status.public_launch_enabled)).catch(() => setPublicLaunch(null));
  }, []);
  return <main className="path-page path-landing">
    <header className="path-public-header"><a className="path-wordmark" href="/"><img className="path-brand-mark" src="/brand/luma-mark.svg" alt="" /><b>Luma</b></a>{import.meta.env.DEV && <a href="/dev/designs">Интерактивный интерфейс</a>}</header>
    <section className="path-landing-hero">
      <div className="path-landing-copy"><span className="path-kicker">Немедицинский помощник</span><h1>Не идеальная жизнь.<br /><em>Следующий честный шаг.</em></h1><p>Поддержка на пути от последней пачки к жизни без сигарет — без стыда, давления и обещаний невозможного.</p><div className="path-landing-actions">{publicLaunch === false ? <button className="path-button primary" type="button" disabled>Готовим запуск</button> : <a className="path-button primary login" href="/api/v1/auth/oidc/start" onClick={event => { event.preventDefault(); beginOidcLogin(); }}>Войти через Telegram <span>→</span></a>}<a className="path-button ghost" href="#how">Как это работает</a></div><small>{publicLaunch === false ? 'Закрытый production preview: вход пока отключён.' : 'Работает как Telegram Mini App и обычное PWA.'}</small></div>
      <div className="path-landing-visual" aria-hidden="true"><div className="path-door"><span>8</span><small>дней пути</small></div><p>«Одна тяга —<br />не приказ»</p></div>
    </section>
    <section id="how" className="path-how"><header><span>Как это работает</span><h2>Опора на каждом отрезке</h2></header><div><article><i>01</i><h3>Отмечай честно</h3><p>Фиксируй сигареты и триггеры без оценки себя.</p></article><article><i>02</i><h3>Пережди волну</h3><p>Получи одно короткое действие на ближайшие минуты.</p></article><article><i>03</i><h3>Видь свой путь</h3><p>Накопленный прогресс не исчезает из-за сложного дня.</p></article></div></section>
    <footer className="path-public-footer"><p>Сервис не заменяет медицинскую помощь и не гарантирует результат.</p><nav><a href="/terms.html">Условия</a><a href="/privacy.html">Конфиденциальность</a><a href="/consent.html">Согласие</a><a href="/feedback">Обратная связь</a></nav></footer>
  </main>;
}
