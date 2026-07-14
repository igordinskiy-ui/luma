# Kurilka — «Последняя пачка»

MVP сервиса поддержки отказа от сигарет: Telegram-бот для коммуникации и единый React-клиент, работающий как Telegram Mini App и PWA.

## Быстрый запуск

1. Скопируйте `.env.example` в `.env`; для production заполните `SESSION_SECRET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `PROXY_SHARED_SECRET` и `REDIS_PASSWORD` уникальными случайными значениями, а затем укажите пароль в URL-кодированном виде в `REDIS_URL`.
2. Выполните `docker compose up --build`.
3. API доступен по `http://localhost:8000/docs`, веб-клиент — по `http://localhost:5173`.

Для локальной разработки без Docker используйте Python 3.12 (версия зафиксирована в `.python-version`): в `apps/api` установите зависимости `python -m pip install -r requirements.txt pytest` и примените `alembic upgrade head`; в `apps/web` — `npm ci`. Полная проверка клиента: `npm test && npm run test:e2e`.

## Production deployment

Задайте `DOMAIN`, production secrets и допуски `CONTENT_REVIEW_STATUS=approved` и `LEGAL_DOCUMENTS_STATUS=approved` (только после реального согласования контента и документов), затем запустите `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`. Production override публикует только Caddy с HTTPS; PostgreSQL, Redis и API остаются во внутренней Docker-сети. Полный перечень переменных — в [production contract](docs/PRODUCTION_ENVIRONMENT.md), порядок запуска — в [runbook](docs/OPERATIONS_RUNBOOK.md).

При деплое на VPS через GitHub храните SSH-ключи и production-секреты только в GitHub Environments/Secrets или в защищённом `.env` на сервере. Файл `.env` и приватные ключи не должны попадать в Git; в репозитории хранится только шаблон `.env.example`.

## UX/UI: «Путь»

Основным и единственным интерфейсным стилем выбран **«Путь»**: тёплый редакционный визуальный язык, видимый прогресс без обнуления и короткие поддерживающие действия. Альтернативные UI-концепты удалены из пользовательского интерфейса и не должны возвращаться как темы или переключатели оформления.

Правила визуального языка, UX-паттерны, токены, компоненты и требования accessibility зафиксированы в [ADR-002](docs/ADR-002-path-design-system.md). После `npm run dev` текущий интерактивный прототип доступен по `/?designs` до удаления галереи из реализации.

## Границы продукта

Сервис является немедицинским помощником: он помогает отслеживать привычки и применять короткие поведенческие техники, но не ставит диагнозов и не назначает лечение. Сервис носит исключительно информационно-поддерживающий характер и не обещает и не гарантирует результата, включая отказ от курения в какой-либо срок или отсутствие срывов.
