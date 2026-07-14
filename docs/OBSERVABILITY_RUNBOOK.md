# Observability and alert contract

`/internal/metrics` доступен только внутреннему scraper с `X-Proxy-Secret` и не
проксируется публичным Caddy. Метрики не содержат Telegram ID, URL запроса,
заметок, причин, push endpoints или provider payload.

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

## Alert test

Перед пилотом владелец monitoring временно снижает один безопасный threshold,
подтверждает доставку в реальный incident channel, записывает время, получателя
и ссылку на alert, затем возвращает production-порог. Нельзя считать наличие
PromQL доказательством фактической доставки алерта.

При срабатывании запрещено добавлять в labels/log context пользовательский текст,
Telegram ID, bearer, push endpoint или тело provider-ошибки. Для корреляции
используется только безопасный `request_id`.
