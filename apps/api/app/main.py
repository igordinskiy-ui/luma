import json
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from fastapi import Depends, FastAPI, HTTPException, Header, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .auth import current_user, telegram_auth_context
from .config import approved_acquisition_sources, public_launch_open, settings, validate_security_settings
from .db import get_db
from .models import AnalyticsEvent, BehaviorEvent, ConsentRecord, CopingSession, Entitlement, Feedback, NotificationDelivery, NotificationPreference, OutboxEvent, PushSubscription, QuitAttempt, QuitPlan, User
from .journey import close_active_attempt, journey_stats, start_attempt
from .journal import decode_cursor, encode_cursor
from .session import issue_session, session_subject
from .oidc import consume_browser_exchange, create_browser_exchange, exchange_code, start_url
from .analytics import track
from .observability import RequestLogMiddleware, bounded_ratio, metrics_text, normalized_request_id
from .rate_limit import enforce
from .features import FREE_BETA_FEATURES, has_feature
from .risk import assess
from .content import CONTENT_DIGEST, CONTENT_VERSION, COPING_TECHNIQUES, PRE_QUIT_STEPS, RECOVERY_STEPS
from .notifications import can_send
from .schemas import AuthIn, ClientTelemetryIn, ConsentIn, CopingSessionCreateIn, CopingSessionPatchIn, DashboardOut, EventIn, EventOut, EventPatchIn, FeedbackIn, FeedbackStatusIn, OidcCompletionIn, OnboardingIn, PreferencesIn, PushSubscriptionIn, QuitPlanUpdateIn
from .bot import Bot, handle_update

app = FastAPI(title="Luma API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","), allow_credentials=True, allow_methods=["*"], allow_headers=["Authorization", "Content-Type"])
app.add_middleware(RequestLogMiddleware)
logger = logging.getLogger("kurilka.api")


def request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None) or normalized_request_id(request.headers.get("X-Request-ID"))
    request.state.request_id = value
    return value


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    identifier = request_id(request)
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    headers = dict(exc.headers or {})
    headers["X-Request-ID"] = identifier
    return JSONResponse(status_code=exc.status_code, headers=headers, content={"error": {"code": f"http_{exc.status_code}", "message": message, "request_id": identifier}})


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    identifier = request_id(request)
    fields = [{"field": ".".join(str(part) for part in error["loc"] if part != "body"), "message": error["msg"]} for error in exc.errors()]
    return JSONResponse(status_code=422, headers={"X-Request-ID": identifier}, content={"error": {"code": "validation_error", "message": "Request validation failed", "request_id": identifier, "field_errors": fields}})


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    identifier = request_id(request)
    logger.error(json.dumps({"event": "unhandled_request_error", "request_id": identifier, "path": request.url.path, "error_type": type(exc).__name__}, ensure_ascii=False))
    return JSONResponse(status_code=500, headers={"X-Request-ID": identifier}, content={"error": {"code": "internal_error", "message": "Internal server error", "request_id": identifier}})

@app.middleware("http")
async def limit_request_body(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > settings.max_request_body_bytes:
                identifier = request_id(request)
                return JSONResponse(status_code=413, headers={"X-Request-ID": identifier}, content={"error": {"code": "payload_too_large", "message": "Request body is too large", "request_id": identifier}})
        except ValueError:
            identifier = request_id(request)
            return JSONResponse(status_code=400, headers={"X-Request-ID": identifier}, content={"error": {"code": "invalid_content_length", "message": "Content-Length is invalid", "request_id": identifier}})
    # Content-Length is optional and attacker-controlled. Count bytes from the
    # ASGI stream so chunked requests cannot bypass the application boundary.
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > settings.max_request_body_bytes:
            identifier = request_id(request)
            return JSONResponse(status_code=413, headers={"X-Request-ID": identifier}, content={"error": {"code": "payload_too_large", "message": "Request body is too large", "request_id": identifier}})
        body.extend(chunk)
    request._body = bytes(body)
    return await call_next(request)


@app.middleware("http")
async def public_launch_gate(request: Request, call_next):
    if request.url.path.startswith("/v1/") and request.url.path != "/v1/launch-status" and not public_launch_open():
        identifier = request_id(request)
        return JSONResponse(
            status_code=503,
            headers={"X-Request-ID": identifier, "Retry-After": "3600"},
            content={"error": {"code": "public_launch_disabled", "message": "Luma is not open to users yet", "request_id": identifier}},
        )
    return await call_next(request)

@app.on_event("startup")
def check_configuration(): validate_security_settings()

def plan_for(db: Session, user: User, *, locked: bool = False) -> QuitPlan:
    query = select(QuitPlan).where(QuitPlan.user_id == user.id)
    if locked:
        # Event writes change the pack counter. Serialize them per user so two
        # rapid taps (or an online/offline replay) cannot lose a decrement.
        query = query.with_for_update()
    plan = db.scalar(query)
    if not plan: raise HTTPException(404, "Quit plan not found")
    return plan

def emit(db: Session, user: User, topic: str, payload: dict) -> None:
    db.add(OutboxEvent(user_id=user.id, topic=topic, payload=json.dumps(payload, ensure_ascii=False)))


def coping_session_out(item: CopingSession) -> dict:
    return {
        "id": item.id, "client_session_id": item.client_session_id, "source": item.source,
        "trigger": item.trigger, "intensity_before": item.intensity_before,
        "intensity_after": item.intensity_after, "technique": item.technique,
        "content_version": item.content_version, "status": item.status,
        "started_at": item.started_at, "updated_at": item.updated_at,
        "completed_at": item.completed_at,
    }

def staff_user(user: User = Depends(current_user)) -> User:
    allowed = {value.strip() for value in settings.admin_telegram_ids.split(",") if value.strip()}
    if not allowed or user.telegram_id not in allowed:
        raise HTTPException(403, "Staff access is required")
    return user


def current_consented_user(user: User = Depends(current_user)) -> User:
    if settings.legal_documents_version and (user.consent_version != settings.legal_documents_version or user.consent_digest != settings.legal_documents_digest):
        raise HTTPException(428, "Current legal documents must be accepted")
    if not user.age_confirmed_at:
        raise HTTPException(428, "Adult age confirmation is required")
    return user


def accept_current_consent(db: Session, user: User, source: str) -> User:
    """Record one immutable proof for the exact version+digest under a user lock."""
    locked = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if not locked: raise HTTPException(401, "Session user no longer exists")
    now = datetime.utcnow()
    locked.consent_version = settings.legal_documents_version
    locked.consent_digest = settings.legal_documents_digest
    locked.consented_at = now
    locked.age_confirmed_at = locked.age_confirmed_at or now
    existing = db.scalar(select(ConsentRecord.id).where(
        ConsentRecord.user_id == locked.id,
        ConsentRecord.document_version == settings.legal_documents_version,
        ConsentRecord.document_digest == settings.legal_documents_digest,
    ))
    if not existing:
        db.add(ConsentRecord(
            user_id=locked.id,
            document_version=settings.legal_documents_version,
            document_digest=settings.legal_documents_digest,
            source=source,
            age_confirmed=True,
            accepted_at=now,
        ))
    return locked

@app.get("/health")
def health(): return {"status": "ok"}


@app.get("/v1/launch-status")
def launch_status(): return {"public_launch_enabled": public_launch_open()}

@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    from sqlalchemy import text
    from redis import Redis
    try:
        db.execute(text("SELECT 1"))
        redis = Redis.from_url(settings.redis_url)
        try: redis.ping()
        finally: redis.close()
    except Exception as exc: raise HTTPException(503, "Dependencies are unavailable") from exc
    return {"status": "ready"}


@app.get("/internal/metrics", response_class=PlainTextResponse)
def internal_metrics(x_proxy_secret: str | None = Header(None, alias="X-Proxy-Secret"), db: Session = Depends(get_db)):
    if not settings.proxy_shared_secret or x_proxy_secret != settings.proxy_shared_secret:
        raise HTTPException(404, "Not found")
    from redis import Redis
    delivery_window = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
    deliveries_terminal_24h = db.scalar(select(func.count(NotificationDelivery.id)).where(NotificationDelivery.status.in_(["sent", "failed"]), NotificationDelivery.created_at >= delivery_window)) or 0
    deliveries_failed_24h = db.scalar(select(func.count(NotificationDelivery.id)).where(NotificationDelivery.status == "failed", NotificationDelivery.created_at >= delivery_window)) or 0
    gauges = {
        "kurilka_database_up": 1,
        "kurilka_outbox_pending": db.scalar(select(func.count(OutboxEvent.id)).where(OutboxEvent.status == "pending")) or 0,
        "kurilka_outbox_failed": db.scalar(select(func.count(OutboxEvent.id)).where(OutboxEvent.status == "failed")) or 0,
        "kurilka_deliveries_queued": db.scalar(select(func.count(NotificationDelivery.id)).where(NotificationDelivery.status == "queued")) or 0,
        "kurilka_deliveries_failed": db.scalar(select(func.count(NotificationDelivery.id)).where(NotificationDelivery.status == "failed")) or 0,
        "kurilka_deliveries_terminal_24h": deliveries_terminal_24h,
        "kurilka_deliveries_failed_24h": deliveries_failed_24h,
        "kurilka_delivery_failure_ratio_24h": bounded_ratio(deliveries_failed_24h, deliveries_terminal_24h),
        "kurilka_worker_heartbeat_age_seconds": -1,
    }
    redis = Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=1)
    try:
        heartbeat = redis.get("kurilka:worker:heartbeat")
        if heartbeat: gauges["kurilka_worker_heartbeat_age_seconds"] = max(0, int(datetime.utcnow().timestamp() - float(heartbeat)))
    except Exception:
        pass
    finally:
        redis.close()
    return metrics_text(gauges)

@app.get("/v1/push-public-key")
def push_public_key(): return {"public_key": settings.vapid_public_key}

@app.get("/v1/entitlements")
def entitlements(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = list(db.scalars(select(Entitlement).where(Entitlement.user_id == user.id)))
    return {"beta_free": sorted(FREE_BETA_FEATURES), "entitlements": [{"feature": row.feature, "source": row.source, "expires_at": row.expires_at} for row in rows]}


@app.get("/v1/bootstrap")
def bootstrap_state(user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan_exists = bool(db.scalar(select(QuitPlan.id).where(QuitPlan.user_id == user.id)))
    consent_current = not settings.legal_documents_version or (
        user.consent_version == settings.legal_documents_version and
        user.consent_digest == settings.legal_documents_digest
    )
    return {
        "age_confirmed": bool(user.age_confirmed_at),
        "consent_current": consent_current,
        "onboarded": plan_exists,
        "legal_documents_version": settings.legal_documents_version,
        "legal_documents_digest": settings.legal_documents_digest,
    }

@app.post("/v1/telegram/webhook", status_code=204)
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(default=None)):
    if not settings.telegram_bot_token or not settings.telegram_webhook_secret: raise HTTPException(503, "Webhook is not configured")
    if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret: raise HTTPException(401, "Invalid webhook secret")
    enforce(request, "telegram-webhook", 120)
    bot = Bot(settings.telegram_bot_token)
    try: await handle_update(bot, await request.json())
    finally: await bot.session.close()
    return Response(status_code=204)

@app.post("/v1/auth/telegram")
def telegram_auth(payload: AuthIn, request: Request, db: Session = Depends(get_db)):
    enforce(request, "telegram-auth", 15)
    telegram_id, start_param = telegram_auth_context(payload.init_data)
    acquisition_source = start_param if start_param in approved_acquisition_sources() else None
    user = db.scalar(select(User).where(User.telegram_id == telegram_id))
    if not user:
        user = User(telegram_id=telegram_id, acquisition_source=acquisition_source); db.add(user); db.commit()
    elif acquisition_source and not user.acquisition_source:
        user.acquisition_source = acquisition_source; db.commit()
    return {"access_token": issue_session(user.id, user.auth_version), "token_type": "bearer", "user_id": user.id}

@app.get("/v1/auth/oidc/start")
def oidc_start(client_state: str, request: Request):
    enforce(request, "oidc-start", 10)
    return RedirectResponse(start_url(client_state), status_code=302)

@app.get("/v1/auth/oidc/callback")
async def oidc_callback(code: str, state: str, request: Request, db: Session = Depends(get_db)):
    enforce(request, "oidc-callback", 30)
    telegram_id, client_state = await exchange_code(code, state)
    user = db.scalar(select(User).where(User.telegram_id == telegram_id))
    if not user:
        user = User(telegram_id=telegram_id); db.add(user); db.commit(); db.refresh(user)
    exchange_code_value = create_browser_exchange(issue_session(user.id, user.auth_version), client_state)
    return RedirectResponse(f"{settings.telegram_webapp_url}/#oidc_code={exchange_code_value}&state={client_state}", status_code=302)

@app.post("/v1/auth/oidc/complete")
def oidc_complete(payload: OidcCompletionIn, request: Request):
    enforce(request, "oidc-complete", 10)
    token = consume_browser_exchange(payload.code, payload.client_state)
    subject = session_subject(token)
    if not subject:
        raise HTTPException(400, "OIDC completion session is invalid")
    return {"access_token": token, "token_type": "bearer", "user_id": subject[0]}


@app.post("/v1/logout", status_code=204)
def logout(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Invalidate every bearer issued with the current auth version."""
    enforce(request, "logout", 10, subject=user.id)
    user.auth_version += 1
    db.commit()
    return Response(status_code=204)

@app.post("/v1/onboarding")
def onboarding(payload: OnboardingIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    enforce(request, "onboarding", 10, subject=user.id)
    plan = db.scalar(select(QuitPlan).where(QuitPlan.user_id == user.id)) or QuitPlan(user_id=user.id)
    if plan.id and plan.phase in {"preparation", "last_pack", "quit", "paused"}:
        # A document-version change must not reset an active quit plan. The
        # same checked onboarding form doubles as the explicit re-consent UI.
        accept_current_consent(db, user, "reconsent")
        db.commit()
        return {"phase": plan.phase}
    if not plan.id: db.add(plan)
    for field in ("cigarettes_per_pack", "remaining", "pack_price", "reasons"):
        setattr(plan, field, getattr(payload, field))
    user.timezone = payload.timezone
    accept_current_consent(db, user, "onboarding")
    plan.phase = payload.start_mode
    plan.target_quit_at = payload.target_quit_at.replace(tzinfo=None) if payload.start_mode == "preparation" and payload.target_quit_at else None
    if plan.phase == "quit" and not plan.quit_started_at:
        plan.quit_started_at = datetime.utcnow()
        start_attempt(db, user.id, plan.quit_started_at)
    if not db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user.id)):
        db.add(NotificationPreference(user_id=user.id))
    emit(db, user, "quit_plan.created", {"phase": plan.phase})
    db.commit(); return {"phase": plan.phase}


@app.post("/v1/consent")
def renew_consent(payload: ConsentIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Accept the current documents without mutating an existing quit plan."""
    enforce(request, "consent", 10, subject=user.id)
    user = accept_current_consent(db, user, "reconsent")
    db.commit()
    return {"consent_version": user.consent_version, "consent_digest": user.consent_digest, "age_confirmed": True}

@app.get("/v1/quit-plan")
def get_quit_plan(user: User = Depends(current_consented_user), db: Session = Depends(get_db)):
    plan = plan_for(db, user)
    return {"phase": plan.phase, "paused_from": plan.paused_from, "remaining": plan.remaining, "cigarettes_per_pack": plan.cigarettes_per_pack, "pack_price": plan.pack_price, "reasons": plan.reasons, "quit_started_at": plan.quit_started_at, "target_quit_at": plan.target_quit_at, "recovery_until": plan.recovery_until}

@app.put("/v1/quit-plan")
def update_quit_plan(payload: QuitPlanUpdateIn, request: Request, user: User = Depends(current_consented_user), db: Session = Depends(get_db)):
    enforce(request, "quit-plan-update", 30, subject=user.id)
    plan = plan_for(db, user, locked=True)
    if payload.phase:
        allowed = {"preparation": {"last_pack", "paused"}, "last_pack": {"quit", "paused"}, "quit": {"paused"}, "paused": {"preparation", "last_pack", "quit"}}
        if payload.phase != plan.phase and payload.phase not in allowed.get(plan.phase, set()): raise HTTPException(409, "Invalid quit plan transition")
        previous_phase = plan.phase
        if previous_phase == "paused" and payload.phase != "paused":
            expected = plan.paused_from or ("last_pack" if plan.remaining > 0 else "quit")
            if payload.phase != expected:
                raise HTTPException(409, "Quit plan must resume from its paused phase")
        plan.phase = payload.phase
        if payload.phase == "quit" and previous_phase != "quit":
            plan.remaining = 0
            plan.quit_started_at = datetime.utcnow()
            start_attempt(db, user.id, plan.quit_started_at)
        elif payload.phase == "paused" and previous_phase != "paused":
            plan.paused_from = previous_phase
            if previous_phase == "quit":
                close_active_attempt(db, user.id, datetime.utcnow(), "paused")
                plan.quit_started_at = None
        if previous_phase == "paused" and payload.phase != "paused":
            plan.paused_from = None
    if payload.remaining is not None:
        plan.remaining = payload.remaining
        if plan.remaining == 0 and plan.phase == "last_pack":
            plan.phase, plan.quit_started_at = "quit", datetime.utcnow()
            start_attempt(db, user.id, plan.quit_started_at)
    if payload.cigarettes_per_pack is not None: plan.cigarettes_per_pack = payload.cigarettes_per_pack
    if payload.pack_price is not None: plan.pack_price = payload.pack_price
    if payload.reasons is not None: plan.reasons = payload.reasons
    if "target_quit_at" in payload.model_fields_set:
        plan.target_quit_at = payload.target_quit_at.replace(tzinfo=None) if payload.target_quit_at else None
    if plan.phase == "preparation" and not plan.target_quit_at:
        raise HTTPException(422, "Preparation mode requires a target date")
    emit(db, user, "quit_plan.updated", {"phase": plan.phase})
    db.commit(); return {"phase": plan.phase, "remaining": plan.remaining}

@app.get("/v1/dashboard", response_model=DashboardOut)
def dashboard(user: User = Depends(current_consented_user), db: Session = Depends(get_db)):
    plan = plan_for(db, user); risk, intervention, triggers = assess(db, user.id)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    stats = journey_stats(db, user.id, now)
    seconds = stats.current_seconds if plan.phase == "quit" else 0
    avoided = max(0, int(seconds / 5400)) if plan.phase == "quit" else 0
    preparation_steps = PRE_QUIT_STEPS if plan.phase == "preparation" or (plan.phase == "last_pack" and plan.remaining <= 7) else []
    recovery_active = bool(plan.recovery_until and plan.recovery_until > datetime.utcnow())
    return DashboardOut(phase=plan.phase, paused_from=plan.paused_from, remaining=plan.remaining, cigarettes_per_pack=plan.cigarettes_per_pack, pack_price=plan.pack_price, smoke_free_seconds=max(0, seconds), best_smoke_free_seconds=stats.best_seconds, attempt_number=stats.attempt_number, next_milestone_seconds=stats.next_milestone_seconds, next_milestone_label=stats.next_milestone_label, avoided_cigarettes=avoided, saved_money=round(avoided * plan.pack_price / plan.cigarettes_per_pack, 2), risk=risk, intervention=intervention, reasons=plan.reasons, recent_triggers=triggers, preparation_steps=preparation_steps, recovery_until=plan.recovery_until if recovery_active else None, recovery_steps=RECOVERY_STEPS if recovery_active else [], updated_at=plan.quit_started_at, target_quit_at=plan.target_quit_at)

@app.post("/v1/events")
def create_event(payload: EventIn, request: Request, user: User = Depends(current_consented_user), db: Session = Depends(get_db)):
    enforce(request, "behavior-event-create", 60, subject=user.id)
    plan = plan_for(db, user, locked=True)
    existing = db.scalar(select(BehaviorEvent).where(BehaviorEvent.user_id == user.id, BehaviorEvent.client_event_id == payload.client_event_id))
    if existing:
        risk, intervention, _ = assess(db, user.id)
        return {"event_id": existing.id, "phase": plan.phase, "remaining": plan.remaining, "risk": risk, "intervention": intervention, "duplicate": True}
    event = BehaviorEvent(user_id=user.id, **payload.model_dump()); db.add(event)
    try:
        db.flush()
    except IntegrityError:
        # The event id is needed in outbox payloads, so the INSERT now happens
        # before side effects. Preserve idempotency when concurrent replay loses
        # this INSERT race.
        db.rollback()
        existing = db.scalar(select(BehaviorEvent).where(BehaviorEvent.user_id == user.id, BehaviorEvent.client_event_id == payload.client_event_id))
        if not existing: raise
        plan = plan_for(db, user)
        risk, intervention, _ = assess(db, user.id)
        return {"event_id": existing.id, "phase": plan.phase, "remaining": plan.remaining, "risk": risk, "intervention": intervention, "duplicate": True}
    if payload.kind == "smoked" and plan.phase == "last_pack":
        plan.remaining = max(0, plan.remaining - 1)
        if plan.remaining == 0:
            plan.phase, plan.quit_started_at = "quit", datetime.utcnow()
            start_attempt(db, user.id, plan.quit_started_at)
    elif payload.kind in {"relapse", "smoked"} and plan.phase == "quit":
        now = datetime.utcnow()
        close_active_attempt(db, user.id, now, "relapse")
        plan.quit_started_at = now
        start_attempt(db, user.id, now)
        plan.recovery_until = now + timedelta(hours=2)
        emit(db, user, "recovery.requested", {"event": "relapse", "event_id": event.id})
    emit(db, user, f"behavior.{payload.kind}", {"event_id": event.id, "kind": payload.kind, "trigger": payload.trigger, "intensity": payload.intensity})
    try:
        db.commit()
    except IntegrityError:
        # The row lock above is the normal protection. The unique index is the
        # durable second line of defence if a client or a future code path
        # bypasses it.
        db.rollback()
        existing = db.scalar(select(BehaviorEvent).where(BehaviorEvent.user_id == user.id, BehaviorEvent.client_event_id == payload.client_event_id))
        if not existing:
            raise
        plan = plan_for(db, user)
        risk, intervention, _ = assess(db, user.id)
        return {"event_id": existing.id, "phase": plan.phase, "remaining": plan.remaining, "risk": risk, "intervention": intervention, "duplicate": True}
    risk, intervention, _ = assess(db, user.id)
    return {"event_id": event.id, "phase": plan.phase, "remaining": plan.remaining, "risk": risk, "intervention": intervention, "duplicate": False}

@app.patch("/v1/events/{event_id}", response_model=EventOut)
def update_event(event_id: int, payload: EventPatchIn, request: Request, user: User = Depends(current_consented_user), db: Session = Depends(get_db)):
    enforce(request, "behavior-event-update", 30, subject=user.id)
    event = db.scalar(select(BehaviorEvent).where(BehaviorEvent.id == event_id, BehaviorEvent.user_id == user.id))
    if not event: raise HTTPException(404, "Event not found")
    if event.created_at < datetime.utcnow() - timedelta(minutes=15): raise HTTPException(409, "Event edit window has expired")
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(event, key, value)
    db.commit(); db.refresh(event); return event


@app.delete("/v1/events/{event_id}")
def delete_event(event_id: int, request: Request, user: User = Depends(current_consented_user), db: Session = Depends(get_db)):
    """Remove an accidental recent mark and reverse its journey-side effects."""
    enforce(request, "behavior-event-delete", 20, subject=user.id)
    event = db.scalar(select(BehaviorEvent).where(BehaviorEvent.id == event_id, BehaviorEvent.user_id == user.id).with_for_update())
    if not event: raise HTTPException(404, "Event not found")
    if event.created_at < datetime.utcnow() - timedelta(minutes=15): raise HTTPException(409, "Event edit window has expired")
    plan = plan_for(db, user, locked=True)

    if event.kind == "relapse" and plan.phase != "quit":
        raise HTTPException(409, "Journey state changed; this mark can no longer be removed safely")
    if event.kind == "smoked" and plan.phase == "last_pack":
        plan.remaining = min(100, plan.remaining + 1)
    elif event.kind in {"smoked", "relapse"} and plan.phase == "quit":
        active = db.scalar(select(QuitAttempt).where(QuitAttempt.user_id == user.id, QuitAttempt.ended_at.is_(None)).order_by(QuitAttempt.started_at.desc()).with_for_update())
        if not active or abs((event.created_at - active.started_at).total_seconds()) > 5:
            raise HTTPException(409, "A newer journey event prevents safe removal")
        prior = db.scalar(select(QuitAttempt).where(
            QuitAttempt.user_id == user.id,
            QuitAttempt.ended_at == active.started_at,
            QuitAttempt.end_reason == "relapse",
        ).order_by(QuitAttempt.started_at.desc()).with_for_update())
        db.delete(active)
        if prior:
            prior.ended_at = None
            prior.end_reason = None
            plan.quit_started_at = prior.started_at
        elif event.kind == "smoked":
            plan.phase = "last_pack"
            plan.remaining = 1
            plan.quit_started_at = None
        else:
            raise HTTPException(409, "The previous quit period cannot be restored")
        plan.recovery_until = None
    elif event.kind == "smoked" and plan.phase == "paused" and plan.paused_from == "last_pack":
        plan.remaining = min(100, plan.remaining + 1)
    elif event.kind in {"smoked", "relapse"} and plan.phase not in {"preparation", "paused"}:
        raise HTTPException(409, "Journey state changed; this mark can no longer be removed safely")

    # Cancel support that has not started delivery yet. New event payloads carry
    # the owning event id; old payloads remain untouched rather than guessed.
    pending = db.scalars(select(OutboxEvent).where(
        OutboxEvent.user_id == user.id,
        OutboxEvent.status == "pending",
        OutboxEvent.topic.in_([f"behavior.{event.kind}", "recovery.requested"]),
    ).with_for_update())
    for item in pending:
        try: payload_event_id = json.loads(item.payload).get("event_id")
        except (json.JSONDecodeError, AttributeError, TypeError): payload_event_id = None
        if payload_event_id == event.id: db.delete(item)
    db.delete(event)
    db.commit()
    return {"status": "deleted", "phase": plan.phase, "remaining": plan.remaining}

@app.get("/v1/events", response_model=list[EventOut])
def list_events(user: User = Depends(current_consented_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(BehaviorEvent).where(BehaviorEvent.user_id == user.id).order_by(BehaviorEvent.created_at.desc()).limit(100)))


@app.get("/v1/coping-techniques")
def coping_techniques(_: User = Depends(current_consented_user)):
    return {"content_version": CONTENT_VERSION, "content_digest": CONTENT_DIGEST, "techniques": [{"id": key, **value} for key, value in COPING_TECHNIQUES.items()]}


@app.post("/v1/coping-sessions", status_code=201)
def create_coping_session(payload: CopingSessionCreateIn, request: Request, user: User = Depends(current_consented_user), db: Session = Depends(get_db)):
    enforce(request, "coping-session-create", 30, subject=user.id)
    existing = db.scalar(select(CopingSession).where(CopingSession.user_id == user.id, CopingSession.client_session_id == payload.client_session_id))
    if existing:
        return coping_session_out(existing)
    item = CopingSession(user_id=user.id, content_version=CONTENT_VERSION, **payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(CopingSession).where(CopingSession.user_id == user.id, CopingSession.client_session_id == payload.client_session_id))
        if not existing:
            raise
        return coping_session_out(existing)
    db.refresh(item)
    return coping_session_out(item)


@app.patch("/v1/coping-sessions/{session_id}")
def update_coping_session(session_id: int, payload: CopingSessionPatchIn, request: Request, user: User = Depends(current_consented_user), db: Session = Depends(get_db)):
    enforce(request, "coping-session-update", 60, subject=user.id)
    item = db.scalar(select(CopingSession).where(CopingSession.id == session_id, CopingSession.user_id == user.id).with_for_update())
    if not item:
        raise HTTPException(404, "Coping session not found")
    changes = payload.model_dump(exclude_unset=True)
    if item.status in {"completed", "abandoned"}:
        if changes and all(getattr(item, key) == value for key, value in changes.items()):
            return coping_session_out(item)
        raise HTTPException(409, "Completed coping session cannot be changed")
    next_status = changes.get("status", item.status)
    next_technique = changes.get("technique", item.technique)
    if next_status == "completed" and not next_technique:
        raise HTTPException(422, "Completed coping session requires a technique")
    for key, value in changes.items():
        setattr(item, key, value)
    if next_status in {"completed", "abandoned"}:
        item.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return coping_session_out(item)


@app.get("/v1/journal")
def journal(
    period: str = Query("7d", pattern="^(7d|30d|all)$"),
    item_type: str = Query("all", alias="type", pattern="^(all|craving|smoked|relapse|coping)$"),
    trigger: str | None = Query(None, pattern="^(stress|coffee|after_meal|driving|friends|alcohol|habit)$"),
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(current_consented_user),
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()
    since = now - timedelta(days=7 if period == "7d" else 30) if period != "all" else None
    cursor_value = None
    if cursor:
        try:
            cursor_value = decode_cursor(cursor)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    event_conditions = [BehaviorEvent.user_id == user.id]
    coping_conditions = [CopingSession.user_id == user.id]
    if since:
        event_conditions.append(BehaviorEvent.created_at >= since)
        coping_conditions.append(CopingSession.started_at >= since)
    if trigger:
        event_conditions.append(BehaviorEvent.trigger == trigger)
        coping_conditions.append(CopingSession.trigger == trigger)
    if item_type in {"craving", "smoked", "relapse"}:
        event_conditions.append(BehaviorEvent.kind == item_type)

    summary_event_conditions = list(event_conditions)
    summary_coping_conditions = list(coping_conditions)
    include_events = item_type != "coping"
    include_coping = item_type in {"all", "coping"}

    def after_cursor(timestamp_column, id_column, source: str):
        if not cursor_value:
            return None
        cursor_at, cursor_source, cursor_id = cursor_value
        rank = {"coping": 1, "event": 2}[source]
        cursor_rank = {"coping": 1, "event": 2}[cursor_source]
        same_time = timestamp_column == cursor_at
        if rank < cursor_rank:
            tie = same_time
        elif rank == cursor_rank:
            tie = and_(same_time, id_column < cursor_id)
        else:
            tie = None
        return or_(timestamp_column < cursor_at, tie) if tie is not None else timestamp_column < cursor_at

    rows: list[tuple[datetime, int, int, str, object]] = []
    if include_events:
        condition = after_cursor(BehaviorEvent.created_at, BehaviorEvent.id, "event")
        query = select(BehaviorEvent).where(*event_conditions)
        if condition is not None: query = query.where(condition)
        for item in db.scalars(query.order_by(BehaviorEvent.created_at.desc(), BehaviorEvent.id.desc()).limit(limit + 1)):
            rows.append((item.created_at, 2, item.id, "event", item))
    if include_coping:
        condition = after_cursor(CopingSession.started_at, CopingSession.id, "coping")
        query = select(CopingSession).where(*coping_conditions)
        if condition is not None: query = query.where(condition)
        for item in db.scalars(query.order_by(CopingSession.started_at.desc(), CopingSession.id.desc()).limit(limit + 1)):
            rows.append((item.started_at, 1, item.id, "coping", item))
    rows.sort(key=lambda row: (row[0], row[1], row[2]), reverse=True)
    selected = rows[:limit]

    items = []
    for created_at, _, item_id, source, raw in selected:
        if source == "event":
            item = raw
            items.append({"id": f"event:{item_id}", "source": source, "type": item.kind, "created_at": created_at, "trigger": item.trigger, "intensity_before": item.intensity, "intensity_after": None, "technique": None, "status": None, "note": item.note, "editable_until": created_at + timedelta(minutes=15)})
        else:
            item = raw
            items.append({"id": f"coping:{item_id}", "source": source, "type": "coping", "created_at": created_at, "trigger": item.trigger, "intensity_before": item.intensity_before, "intensity_after": item.intensity_after, "technique": item.technique, "status": item.status, "note": "", "editable_until": None})

    event_total = db.scalar(select(func.count(BehaviorEvent.id)).where(*summary_event_conditions)) if include_events else 0
    coping_total = db.scalar(select(func.count(CopingSession.id)).where(*summary_coping_conditions)) if include_coping else 0
    trigger_counts: dict[str, int] = {}
    if include_events:
        for name, count in db.execute(select(BehaviorEvent.trigger, func.count(BehaviorEvent.id)).where(*summary_event_conditions, BehaviorEvent.trigger.is_not(None)).group_by(BehaviorEvent.trigger)):
            trigger_counts[name] = trigger_counts.get(name, 0) + count
    if include_coping:
        for name, count in db.execute(select(CopingSession.trigger, func.count(CopingSession.id)).where(*summary_coping_conditions, CopingSession.trigger.is_not(None)).group_by(CopingSession.trigger)):
            trigger_counts[name] = trigger_counts.get(name, 0) + count
    top_trigger = max(trigger_counts, key=trigger_counts.get) if trigger_counts else None
    total = int(event_total or 0) + int(coping_total or 0)
    summary = {
        "total": total,
        "cravings": int(db.scalar(select(func.count(BehaviorEvent.id)).where(*summary_event_conditions, BehaviorEvent.kind == "craving")) or 0) if include_events else 0,
        "coping_completed": int(db.scalar(select(func.count(CopingSession.id)).where(*summary_coping_conditions, CopingSession.status == "completed")) or 0) if include_coping else 0,
        "relapses": int(db.scalar(select(func.count(BehaviorEvent.id)).where(*summary_event_conditions, BehaviorEvent.kind == "relapse")) or 0) if include_events else 0,
        "sufficient_data": total >= 3,
        "top_trigger": top_trigger if total >= 3 and trigger_counts.get(top_trigger, 0) >= 2 else None,
    }
    next_cursor = encode_cursor(selected[-1][0], selected[-1][3], selected[-1][2]) if len(rows) > limit and selected else None
    return {"items": items, "next_cursor": next_cursor, "summary": summary}

@app.put("/v1/notification-preferences")
def preferences(payload: PreferencesIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    enforce(request, "notification-preferences", 20, subject=user.id)
    pref = db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user.id).with_for_update()) or NotificationPreference(user_id=user.id)
    if not pref.id: db.add(pref)
    for key, value in payload.model_dump().items(): setattr(pref, key, value)
    db.commit(); return payload

@app.get("/v1/notification-preferences", response_model=PreferencesIn)
def get_preferences(user: User = Depends(current_user), db: Session = Depends(get_db)):
    pref = db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user.id))
    return PreferencesIn.model_validate(pref, from_attributes=True) if pref else PreferencesIn()


@app.get("/v1/notification-status")
def notification_status(user: User = Depends(current_user), db: Session = Depends(get_db)):
    pref = db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user.id))
    subscriptions = db.scalar(select(func.count(PushSubscription.id)).where(PushSubscription.user_id == user.id)) or 0
    return {
        "enabled": bool(pref and pref.enabled),
        "can_send_now": can_send(db, user),
        "telegram": "available" if settings.telegram_bot_token and user.telegram_id.isdigit() else "unavailable",
        "web_push": "subscribed" if subscriptions else "not_subscribed",
        "subscriptions": subscriptions,
    }


@app.post("/v1/notifications/test", status_code=202)
def test_notification(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    enforce(request, "notification-test", 5, subject=user.id)
    if not can_send(db, user):
        raise HTTPException(409, "Notifications are muted, limited, or inside quiet hours")
    has_telegram = bool(settings.telegram_bot_token and user.telegram_id.isdigit())
    has_push = bool(settings.vapid_private_key and db.scalar(select(PushSubscription.id).where(PushSubscription.user_id == user.id)))
    if not has_telegram and not has_push:
        raise HTTPException(409, "No notification channel is configured")
    recent = db.scalar(select(OutboxEvent).where(OutboxEvent.user_id == user.id, OutboxEvent.topic == "notification.test", OutboxEvent.created_at >= datetime.utcnow() - timedelta(minutes=1), OutboxEvent.status.in_(["pending", "processing"])))
    if recent:
        return {"status": "queued", "request_id": recent.id, "duplicate": True}
    event = OutboxEvent(user_id=user.id, topic="notification.test", payload="{}")
    db.add(event); db.commit(); db.refresh(event)
    return {"status": "queued", "request_id": event.id, "duplicate": False}

@app.put("/v1/push-subscription", status_code=204)
def save_push_subscription(payload: PushSubscriptionIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    enforce(request, "push-subscription", 20, subject=user.id)
    subscription = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint))
    if not subscription:
        subscription = PushSubscription(user_id=user.id, **payload.model_dump()); db.add(subscription)
    elif subscription.user_id != user.id:
        raise HTTPException(409, "Push subscription belongs to another account")
    else:
        for key, value in payload.model_dump().items(): setattr(subscription, key, value)
    db.commit(); return Response(status_code=204)


@app.delete("/v1/push-subscription", status_code=204)
def delete_push_subscription(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    enforce(request, "push-subscription-delete", 20, subject=user.id)
    for subscription in db.scalars(select(PushSubscription).where(PushSubscription.user_id == user.id)):
        db.delete(subscription)
    db.commit()
    return Response(status_code=204)

@app.post("/v1/feedback", status_code=201)
def submit_feedback(payload: FeedbackIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    enforce(request, "feedback", 10, subject=user.id)
    item = Feedback(user_id=user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    return {"feedback_id": item.id, "status": item.status}


@app.post("/v1/client-telemetry", status_code=204)
def client_telemetry(payload: ClientTelemetryIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    enforce(request, "client-telemetry", 20, subject=user.id)
    session_hash = hashlib.sha256(payload.client_session_id.encode()).hexdigest()[:32]
    event_name = "client_session_started" if payload.event == "session_started" else "client_crash"
    properties = json.dumps({"session_hash": session_hash}, ensure_ascii=False)
    existing = db.scalar(select(AnalyticsEvent.id).where(AnalyticsEvent.user_id == user.id, AnalyticsEvent.event_name == event_name, AnalyticsEvent.properties == properties))
    if not existing:
        track(db, user, event_name, {"session_hash": session_hash})
        try: db.commit()
        except IntegrityError:
            # Concurrent tabs/retries may pass the read check together; the
            # partial unique index is the durable idempotency boundary.
            db.rollback()
    return Response(status_code=204)

@app.get("/v1/admin/overview")
def admin_overview(
    period: str = Query("30d", pattern="^(7d|30d|90d|all)$"),
    source: str | None = Query(None, min_length=1, max_length=64),
    _: User = Depends(staff_user),
    db: Session = Depends(get_db),
):
    if source and source != "direct" and source not in approved_acquisition_sources():
        raise HTTPException(422, "Acquisition source is not allowlisted")
    now = datetime.utcnow()
    since_24h = now - timedelta(hours=24)
    period_since = now - timedelta(days={"7d": 7, "30d": 30, "90d": 90}.get(period, 36500)) if period != "all" else None
    user_query = select(User)
    if period_since: user_query = user_query.where(User.created_at >= period_since)
    if source == "direct": user_query = user_query.where(User.acquisition_source.is_(None))
    elif source: user_query = user_query.where(User.acquisition_source == source)
    users = list(db.scalars(user_query))
    user_ids = [user.id for user in users]

    phases = dict(db.execute(select(QuitPlan.phase, func.count(QuitPlan.id)).where(QuitPlan.user_id.in_(user_ids)).group_by(QuitPlan.phase)).all())
    deliveries = dict(db.execute(select(NotificationDelivery.status, func.count(NotificationDelivery.id)).where(NotificationDelivery.user_id.in_(user_ids), NotificationDelivery.created_at >= since_24h).group_by(NotificationDelivery.status)).all())
    outbox = dict(db.execute(select(OutboxEvent.status, func.count(OutboxEvent.id)).where(OutboxEvent.user_id.in_(user_ids)).group_by(OutboxEvent.status)).all())
    activity: dict[int, list[datetime]] = {}
    dated_users = [user for user in users if user.created_at]
    if dated_users:
        # Only D1/D7/D14 windows are needed. Bound the database scan by the
        # selected cohort's earliest and latest possible window, then apply the
        # exact per-user window below. This remains correct for old cohorts and
        # avoids treating a late return as historical retention.
        activity_since = min(user.created_at for user in dated_users) + timedelta(days=1)
        activity_until = min(now, max(user.created_at for user in dated_users) + timedelta(days=15))
        for user_id, created_at in db.execute(select(BehaviorEvent.user_id, BehaviorEvent.created_at).where(BehaviorEvent.user_id.in_(user_ids), BehaviorEvent.created_at >= activity_since, BehaviorEvent.created_at < activity_until)):
            activity.setdefault(user_id, []).append(created_at)
        for user_id, started_at in db.execute(select(CopingSession.user_id, CopingSession.started_at).where(CopingSession.user_id.in_(user_ids), CopingSession.started_at >= activity_since, CopingSession.started_at < activity_until)):
            activity.setdefault(user_id, []).append(started_at)

    def retention(days: int) -> dict[str, int | float]:
        # Require the complete 24-hour observation window. For example, D7 is
        # activity in [created+7d, created+8d), not any activity after day 7.
        eligible = [user for user in users if user.created_at and user.created_at <= now - timedelta(days=days + 1)]
        retained = 0
        for user in eligible:
            window_start = user.created_at + timedelta(days=days)
            window_end = window_start + timedelta(days=1)
            retained += any(window_start <= timestamp < window_end for timestamp in activity.get(user.id, []))
        return {"eligible": len(eligible), "retained": retained, "rate": round(retained / len(eligible), 4) if eligible else 0}

    onboarded_ids = set(db.scalars(select(QuitPlan.user_id).where(QuitPlan.user_id.in_(user_ids))))
    first_action_24h = 0
    for user in users:
        if user.id not in onboarded_ids or not user.created_at: continue
        event_at = db.scalar(select(func.min(BehaviorEvent.created_at)).where(BehaviorEvent.user_id == user.id))
        coping_at = db.scalar(select(func.min(CopingSession.started_at)).where(CopingSession.user_id == user.id))
        first_at = min((value for value in (event_at, coping_at) if value), default=None)
        if first_at and first_at <= user.created_at + timedelta(hours=24): first_action_24h += 1

    preferences_total = db.scalar(select(func.count(NotificationPreference.id)).where(NotificationPreference.user_id.in_(user_ids))) or 0
    preferences_muted = db.scalar(select(func.count(NotificationPreference.id)).where(NotificationPreference.user_id.in_(user_ids), NotificationPreference.enabled.is_(False))) or 0
    delivery_attempted = deliveries.get("sent", 0) + deliveries.get("failed", 0)
    telemetry_query = select(AnalyticsEvent.event_name, AnalyticsEvent.properties).where(AnalyticsEvent.user_id.in_(user_ids), AnalyticsEvent.event_name.in_(["client_session_started", "client_crash"]))
    if period_since: telemetry_query = telemetry_query.where(AnalyticsEvent.created_at >= period_since)
    started_sessions: set[str] = set()
    crashed_sessions: set[str] = set()
    for event_name, properties in db.execute(telemetry_query):
        try: session_hash = json.loads(properties).get("session_hash")
        except (json.JSONDecodeError, AttributeError, TypeError): continue
        if not session_hash: continue
        (started_sessions if event_name == "client_session_started" else crashed_sessions).add(session_hash)
    crash_free = len(started_sessions - crashed_sessions)
    by_source_query = select(func.coalesce(User.acquisition_source, "direct"), func.count(User.id))
    if period_since: by_source_query = by_source_query.where(User.created_at >= period_since)
    return {
        "filters": {"period": period, "source": source},
        "users_total": len(users),
        "users_by_acquisition_source": dict(db.execute(by_source_query.group_by(func.coalesce(User.acquisition_source, "direct"))).all()),
        "activation": {"onboarded": len(onboarded_ids), "rate": round(len(onboarded_ids) / len(users), 4) if users else 0},
        "funnel": {"started": len(users), "onboarded": len(onboarded_ids), "first_action_24h": first_action_24h, "first_action_rate": round(first_action_24h / len(onboarded_ids), 4) if onboarded_ids else 0},
        "retention": {"d1": retention(1), "d7": retention(7), "d14": retention(14)},
        "notification_health": {"muted": preferences_muted, "preferences_total": preferences_total, "mute_rate": round(preferences_muted / preferences_total, 4) if preferences_total else 0, "delivery_failures_last_24h": deliveries.get("failed", 0), "delivery_failure_rate": round(deliveries.get("failed", 0) / delivery_attempted, 4) if delivery_attempted else 0},
        "client_health": {"sessions": len(started_sessions), "crashed": len(started_sessions & crashed_sessions), "crash_free_rate": round(crash_free / len(started_sessions), 4) if started_sessions else 0},
        "plans_by_phase": phases,
        "events_last_24h": db.scalar(select(func.count(BehaviorEvent.id)).where(BehaviorEvent.user_id.in_(user_ids), BehaviorEvent.created_at >= since_24h)) or 0,
        "deliveries_last_24h": deliveries,
        "outbox_by_status": outbox,
        "open_feedback": db.scalar(select(func.count(Feedback.id)).where(Feedback.user_id.in_(user_ids), Feedback.status == "open")) or 0,
        "content_review_status": settings.content_review_status,
        "content_version": CONTENT_VERSION,
        "content_digest": CONTENT_DIGEST,
        # Runtime selection is deliberately baseline even while a closed VPS
        # preview still carries the deprecated rules_v1 environment value.
        "risk_engine_version": "baseline",
    }

@app.get("/v1/admin/feedback")
def admin_feedback(status: str = "open", _: User = Depends(staff_user), db: Session = Depends(get_db)):
    if status not in {"open", "resolved"}:
        raise HTTPException(422, "Invalid feedback status")
    rows = db.scalars(select(Feedback).where(Feedback.status == status).order_by(Feedback.created_at.asc()).limit(200))
    return [{"id": item.id, "category": item.category, "body": item.body, "status": item.status, "created_at": item.created_at, "resolved_at": item.resolved_at} for item in rows]

@app.patch("/v1/admin/feedback/{feedback_id}")
def update_feedback(feedback_id: int, payload: FeedbackStatusIn, _: User = Depends(staff_user), db: Session = Depends(get_db)):
    item = db.get(Feedback, feedback_id)
    if not item:
        raise HTTPException(404, "Feedback not found")
    item.status = payload.status
    item.resolved_at = datetime.utcnow() if payload.status == "resolved" else None
    db.commit()
    return {"id": item.id, "status": item.status}

@app.get("/v1/privacy-export")
def export(user: User = Depends(current_user), db: Session = Depends(get_db)):
    events = list(db.scalars(select(BehaviorEvent).where(BehaviorEvent.user_id == user.id)))
    plan = db.scalar(select(QuitPlan).where(QuitPlan.user_id == user.id))
    preferences = db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user.id))
    deliveries = list(db.scalars(select(NotificationDelivery).where(NotificationDelivery.user_id == user.id)))
    feedback = list(db.scalars(select(Feedback).where(Feedback.user_id == user.id)))
    analytics = list(db.scalars(select(AnalyticsEvent).where(AnalyticsEvent.user_id == user.id)))
    entitlements = list(db.scalars(select(Entitlement).where(Entitlement.user_id == user.id)))
    outbox = list(db.scalars(select(OutboxEvent).where(OutboxEvent.user_id == user.id)))
    subscriptions = list(db.scalars(select(PushSubscription).where(PushSubscription.user_id == user.id)))
    attempts = list(db.scalars(select(QuitAttempt).where(QuitAttempt.user_id == user.id).order_by(QuitAttempt.started_at.asc())))
    coping_sessions = list(db.scalars(select(CopingSession).where(CopingSession.user_id == user.id).order_by(CopingSession.started_at.asc())))
    consent_history = list(db.scalars(select(ConsentRecord).where(ConsentRecord.user_id == user.id).order_by(ConsentRecord.accepted_at.asc())))
    return {
        "account": {
            "timezone": user.timezone,
            "age_confirmed_at": user.age_confirmed_at,
            "consent_version": user.consent_version,
            "consent_digest": user.consent_digest,
            "consented_at": user.consented_at,
            "acquisition_source": user.acquisition_source,
            "created_at": user.created_at,
        },
        "consent_history": [{
            "document_version": item.document_version,
            "document_digest": item.document_digest,
            "source": item.source,
            "age_confirmed": item.age_confirmed,
            "accepted_at": item.accepted_at,
        } for item in consent_history],
        "quit_plan": {
            "phase": plan.phase,
            "paused_from": plan.paused_from,
            "remaining": plan.remaining,
            "cigarettes_per_pack": plan.cigarettes_per_pack,
            "pack_price": plan.pack_price,
            "reasons": plan.reasons,
            "quit_started_at": plan.quit_started_at,
            "target_quit_at": plan.target_quit_at,
            "recovery_until": plan.recovery_until,
        } if plan else None,
        "quit_attempts": [{"started_at": item.started_at, "ended_at": item.ended_at, "end_reason": item.end_reason, "created_at": item.created_at} for item in attempts],
        "coping_sessions": [coping_session_out(item) for item in coping_sessions],
        "notification_preferences": {"enabled": preferences.enabled, "max_daily": preferences.max_daily, "quiet_start": preferences.quiet_start, "quiet_end": preferences.quiet_end} if preferences else None,
        "events": [{"kind": e.kind, "trigger": e.trigger, "intensity": e.intensity, "note": e.note, "created_at": e.created_at} for e in events],
        "notification_deliveries": [{"channel": d.channel, "template": d.template, "status": d.status, "attempts": d.attempts, "sent_at": d.sent_at, "created_at": d.created_at} for d in deliveries],
        "feedback": [{"category": item.category, "body": item.body, "status": item.status, "resolved_at": item.resolved_at, "created_at": item.created_at} for item in feedback],
        "analytics": [{"event_name": item.event_name, "properties": item.properties, "schema_version": item.schema_version, "created_at": item.created_at} for item in analytics],
        "entitlements": [{"feature": item.feature, "source": item.source, "expires_at": item.expires_at, "created_at": item.created_at} for item in entitlements],
        "outbox": [{"topic": item.topic, "payload": item.payload, "status": item.status, "attempts": item.attempts, "created_at": item.created_at} for item in outbox],
        "push_subscriptions": [{"endpoint": item.endpoint, "created_at": item.created_at} for item in subscriptions],
    }

@app.delete("/v1/account", status_code=204)
def delete_account(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    enforce(request, "account-delete", 3, subject=user.id)
    for model in (BehaviorEvent, ConsentRecord, CopingSession, NotificationDelivery, PushSubscription, OutboxEvent, QuitAttempt, QuitPlan, NotificationPreference, AnalyticsEvent, Entitlement, Feedback):
        for row in db.scalars(select(model).where(model.user_id == user.id)): db.delete(row)
    # Authentication may supply an ORM instance loaded by another session
    # (notably in test overrides and future external identity adapters). Delete
    # the row owned by this transaction instead of attaching that instance.
    account = db.get(User, user.id)
    if account:
        db.delete(account)
    db.commit(); return Response(status_code=204)
