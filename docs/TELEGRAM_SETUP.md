# Настройка Telegram для staging и production

## Mini App и бот

1. Создайте бота в BotFather и сохраните токен только в секретах окружения.
2. Укажите production HTTPS URL как Web App URL и menu button URL.
3. Вызовите `setWebhook` для `/v1/telegram/webhook`, передав случайный `secret_token`; сохраните его как `TELEGRAM_WEBHOOK_SECRET`.
4. Проверьте `getWebhookInfo` и тестовый `/start`.

## Автономный PWA login

1. В BotFather в разделе Login Widget зарегистрируйте точные Allowed URLs: production origin и `https://<domain>/api/v1/auth/oidc/callback`.
2. Сохраните выданные Client ID и Client Secret в secrets как `TELEGRAM_OIDC_CLIENT_ID` и `TELEGRAM_OIDC_CLIENT_SECRET`.
3. Задайте `TELEGRAM_OIDC_REDIRECT_URI` равным callback URL и `TELEGRAM_WEBAPP_URL` равным origin PWA.
4. OIDC использует Authorization Code + PKCE, одноразовый state хранится в Redis 10 минут, а ID token проверяется по Telegram JWKS, issuer и audience.

Не используйте localhost в production Allowed URLs и не передавайте bot token, OIDC secret или session secret в браузер.

## Web push

Сгенерируйте VAPID key pair вне репозитория. Задайте `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` и контролируемый `VAPID_SUBJECT` в deployment secrets. Браузер запросит разрешение только после явного выбора **Включить web push** в настройках; без публичного VAPID key эта возможность отключена.
