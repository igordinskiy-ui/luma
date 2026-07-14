# Аналитические события беты

Отдельная таблица `analytics_events` не дублирует продуктовые действия, триггеры,
интенсивность, техники, заметки, Telegram ID или причины отказа. Она хранит только
минимальную техническую телеметрию здоровья клиента.

| Событие | Свойства |
| --- | --- |
| `client_session_started` | server-side SHA-256 случайного session UUID; без URL, stack trace и текста ошибки |
| `client_crash` | тот же session hash; не более одного сигнала на вкладку, без error payload |

Activation и безопасная воронка считаются напрямую по `users`, `quit_plans`,
`behavior_events` и `coping_sessions`; доставка — по `notification_deliveries`.
`acquisition_source` хранится только как server-side allowlisted first-touch поле
пользователя. Отдельные аналитические копии для этих действий не создаются.

Первое действие ≤24 ч считается по первой записи `behavior_events` или
`coping_sessions` после создания пользователя. Retention D1/D7/D14 считается по такому действию
в соответствующее окно; пользователи, ещё не достигшие возраста когорты, не
попадают в знаменатель. Это продуктовые, а не клинические метрики.
# Pilot cohort metrics

`/v1/admin/overview` reports the operational definitions used during the beta:

- **Activation** — a user has a `quit_plan` (completed onboarding).
- **D1/D7/D14 retention** — users whose complete 24-hour observation window is
  available and who recorded at least one behaviour or coping event inside
  `[created_at + N days, created_at + N + 1 days)`. A late return does not
  retroactively count as earlier retention.
- **Mute rate** — notification preferences with `enabled=false` divided by all
  saved notification preferences.
- **Delivery failure rate** — failed terminal provider attempts divided by
  `sent + failed` during the last 24 hours. `queued` and `scheduled` records do
  not dilute the go/no-go safety metric.
- **Crash-free sessions** — unique `client_session_started` hashes without a
  matching `client_crash` hash in the selected period. The browser reports at
  most one crash marker per tab and never sends exception text or stack data.

These are directional pilot metrics, not clinical abstinence outcomes.
