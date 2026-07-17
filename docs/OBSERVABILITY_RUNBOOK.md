# Observability and alert contract

`/internal/metrics` доступен только внутреннему scraper с `X-Proxy-Secret` и не
проксируется публичным Caddy. Метрики не содержат Telegram ID, URL запроса,
заметок, причин, push endpoints или provider payload.

## Исполняемый контракт

Production thresholds находятся в `ops/prometheus/luma-alerts.yml`, а
детерминированные временные ряды и проверки `for`-окон — в
`ops/prometheus/luma-alerts.test.yml`. CI выполняет обе официальные проверки
Prometheus:

```sh
promtool check rules ops/prometheus/luma-alerts.yml
promtool test rules ops/prometheus/luma-alerts.test.yml
```

Используется immutable Prometheus `3.12.0`. Синтаксически корректный файл и
зелёный synthetic test доказывают выражения и таймеры, но не доказывают, что
production scraper загрузил правила или incident channel получил сообщение.

## Обязательные панели

| Сигнал | PromQL / источник | Порог пилота |
| --- | --- | --- |
| API p95 | `histogram_quantile(0.95, sum(rate(kurilka_api_request_duration_ms_bucket[5m])) by (le))` | warning >500 ms 10 минут; write p95 дополнительно проверяется load-smoke до релиза |
| API error rate | `sum(rate(kurilka_api_requests_total{status=~"5.."}[5m])) / sum(rate(kurilka_api_requests_total[5m]))` | warning >1% 10 минут; critical >5% 5 минут |
| Worker heartbeat | `kurilka_worker_heartbeat_age_seconds` | critical при `<0` или `>90` секунд 5 минут |
| Outbox backlog | `kurilka_outbox_pending` | warning >100 10 минут; critical при росте 20 минут |
| Failed outbox | `kurilka_outbox_failed` | warning >0; triage по request/delivery id без payload |
| Delivery failures | `kurilka_deliveries_failed` и staff 24h rate | go/no-go <2% терминальных попыток |
| Database | `kurilka_database_up` и `/ready` | critical при `0` или readiness failure |

### API latency

`LumaApiLatencyHigh` использует histogram p95 за пять минут и срабатывает после
устойчивого превышения 500 ms в течение десяти минут. Write p95 отдельно
проверяется release load-smoke, потому что текущая метрика намеренно не содержит
route/method labels и не увеличивает чувствительную кардинальность.

### API errors

Warning соответствует 5xx ratio `>1%` за десять минут, critical — `>5%` за пять
минут. Знаменатель защищён от деления на ноль; отсутствие трафика не создаёт
ложный error-rate alert.

### Database and scrape

`LumaDatabaseUnavailable` объединяет приватный `kurilka_database_up` и
Prometheus `up{job="luma-api"}`. `LumaMetricsMissing` отдельно ловит исчезновение
обязательной серии. Scraper должен находиться во внутренней сети и читать
`X-Proxy-Secret` из secret file через `http_headers`; секрет нельзя хранить в
rule labels, Git или dashboard URL.

### Worker and outbox

Worker heartbeat считается недоступным при `-1` или stale после 90 секунд.
Outbox имеет отдельные sustained warning, growing critical и terminal-failure
alerts. Triage использует только внутренний event/delivery ID из защищённых
операционных инструментов и никогда не переносит payload в alert labels.

### Delivery

API экспортирует terminal/failed counts и отношение за скользящие 24 часа:
`kurilka_deliveries_terminal_24h`, `kurilka_deliveries_failed_24h` и
`kurilka_delivery_failure_ratio_24h`. При пустом окне ratio равен `0`; alert
срабатывает при устойчивом превышении pilot go/no-go `2%` в течение десяти минут.
Долгоживущий retention gauge `kurilka_deliveries_failed` остаётся диагностикой,
но больше не используется как proxy для 24-часового процента.

## Alert test

Перед пилотом владелец monitoring временно снижает один безопасный threshold,
подтверждает доставку в реальный incident channel, записывает время, получателя
и ссылку на alert, затем возвращает production-порог. Нельзя считать наличие
PromQL доказательством фактической доставки алерта.

Минимальное production-доказательство содержит:

- commit и digest загруженного rule-файла;
- URL Prometheus rule/status без query с секретами;
- имя тестового alert, время `pending`, `firing` и `resolved`;
- подтверждение получения назначенным owner в реальном incident channel;
- время возврата production threshold и итог проверки normal-state;
- ссылку на incident/drill record без пользовательских payload.

Synthetic CI нельзя подставлять вместо этого списка. До появления фактического
scraper/Alertmanager/receiver evidence Stage 8 остаётся `in_progress`.

При срабатывании запрещено добавлять в labels/log context пользовательский текст,
Telegram ID, bearer, push endpoint или тело provider-ошибки. Для корреляции
используется только безопасный `request_id`.

Основа формата: официальные инструкции Prometheus по
[проверке rule-файлов](https://prometheus.io/docs/prometheus/latest/configuration/recording_rules/)
и [unit testing rules](https://prometheus.io/docs/prometheus/latest/configuration/unit_testing_rules/).
