const API = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8000/v1' : '/api/v1');
const tokenKey = 'kurilka-access-token';
const userKey = 'kurilka-user-id';
const oidcStateKey = 'kurilka-oidc-state';
const oidcReturnKey = 'kurilka-oidc-return';
const oidcPendingKey = 'kurilka-oidc-pending';
const oidcPendingTtlMs = 90_000;
export const safeOidcReturnPath = (value: string | null) => value && /^\/(?:app(?:\/.*)?|journal|settings|feedback|staff)$/.test(value) ? value : '/app';

export type Dashboard = { phase: 'preparation' | 'last_pack' | 'quit' | 'paused'; paused_from?: 'preparation' | 'last_pack' | 'quit' | null; remaining: number; cigarettes_per_pack: number; pack_price: number; smoke_free_seconds: number; best_smoke_free_seconds: number; attempt_number: number; next_milestone_seconds: number | null; next_milestone_label: string | null; avoided_cigarettes: number; saved_money: number; /** Deprecated v1 compatibility value; never a personal assessment. */ risk: 'low'; intervention: string; reasons: string; recent_triggers: string[]; preparation_steps: string[]; recovery_until: string | null; recovery_steps: string[]; target_quit_at: string | null };
export type EventItem = { id: number; kind: 'smoked' | 'craving' | 'relapse'; trigger?: string; intensity?: number; note: string; created_at: string };
export type TriggerId = 'stress' | 'anger' | 'boredom' | 'coffee' | 'after_meal' | 'driving' | 'work_break' | 'social' | 'alcohol' | 'focus' | 'hands' | 'outside' | 'habit' | 'physical';
export type RelapseContext = 'one' | 'day' | 'days' | 'afraid' | 'angry' | 'hopeless';
export type Preferences = { enabled: boolean; max_daily: number; quiet_start: number; quiet_end: number };
export type NotificationStatus = { enabled: boolean; can_send_now: boolean; telegram: 'available' | 'unavailable'; web_push: 'subscribed' | 'not_subscribed'; subscriptions: number };
export type QuitPlan = { phase: Dashboard['phase']; paused_from?: Dashboard['paused_from']; remaining: number; cigarettes_per_pack: number; pack_price: number; reasons: string; quit_started_at: string | null; target_quit_at: string | null; recovery_until: string | null };
export type EventInput = { kind: EventItem['kind']; trigger?: TriggerId; intensity?: number; note?: string; client_event_id: string; relapse_context?: RelapseContext };
export type CopingTechniqueId = 'breathing' | 'delay' | 'change_place' | 'walk' | 'water' | 'hands' | 'mouth' | 'grounding' | 'focus_sprint' | 'social_exit' | 'urge_surf' | 'support_message';
export type CopingTechnique = { id: CopingTechniqueId; title: string; duration_seconds: number; instruction: string; steps?: string[]; best_for?: TriggerId[]; intensity?: [number, number]; previously_helped?: number; previously_not_helped?: number };
export type CopingCreateInput = { client_session_id: string; source: 'dashboard' | 'journal' | 'notification' | 'offline'; trigger?: TriggerId; intensity_before: number };
export type CopingPatchInput = { technique?: CopingTechnique['id']; status?: 'active' | 'paused' | 'completed' | 'abandoned'; intensity_after?: number; outcome?: 'helped' | 'same' | 'worse' };
export type CopingSession = CopingCreateInput & CopingPatchInput & { id: number; content_version: string; status: NonNullable<CopingPatchInput['status']>; started_at: string; updated_at: string; completed_at?: string };
export type JournalItem = { id: string; source: 'event' | 'coping'; type: EventItem['kind'] | 'coping'; created_at: string; trigger?: string; intensity_before?: number; intensity_after?: number; technique?: CopingTechnique['id']; status?: CopingSession['status']; outcome?: 'helped' | 'same' | 'worse' | null; relapse_context?: RelapseContext | null; note: string; editable_until?: string };
export type JournalResponse = { items: JournalItem[]; next_cursor: string | null; summary: { total: number; cravings: number; coping_completed: number; relapses: number; sufficient_data: boolean; top_trigger: string | null } };
export type CohortMetric = { eligible: number; retained: number; rate: number };
export type AdminOverview = { filters: { period: string; source: string | null }; users_total: number; users_by_acquisition_source: Record<string, number>; activation: { onboarded: number; rate: number }; funnel: { started: number; onboarded: number; first_action_24h: number; first_action_rate: number }; retention: { d1: CohortMetric; d7: CohortMetric; d14: CohortMetric }; notification_health: { muted: number; preferences_total: number; mute_rate: number; delivery_failures_last_24h: number; delivery_failure_rate: number }; client_health: { sessions: number; crashed: number; crash_free_rate: number }; plans_by_phase: Record<string, number>; events_last_24h: number; deliveries_last_24h: Record<string, number>; outbox_by_status: Record<string, number>; open_feedback: number; content_review_status: string; content_version: string; content_digest: string; risk_engine_version: string };
export type AdminFeedback = { id: number; category: 'bug' | 'idea' | 'support' | 'content'; body: string; status: 'open' | 'resolved'; created_at: string; resolved_at?: string };
type Session = { access_token: string; token_type: string; user_id: number };
export type Bootstrap = { age_confirmed: boolean; consent_current: boolean; onboarded: boolean; legal_documents_version?: string; legal_documents_digest?: string };
export type LaunchStatus = { public_launch_enabled: boolean };

export const eventId = () => crypto.randomUUID();
export const authToken = () => sessionStorage.getItem(tokenKey);
export const currentUserId = () => sessionStorage.getItem(userKey);

function storeSession(session: Session) {
  sessionStorage.setItem(tokenKey, session.access_token);
  sessionStorage.setItem(userKey, String(session.user_id));
}

export function clearSession() {
  sessionStorage.removeItem(tokenKey);
  sessionStorage.removeItem(userKey);
  sessionStorage.removeItem(oidcStateKey);
  sessionStorage.removeItem(oidcReturnKey);
  sessionStorage.removeItem(oidcPendingKey);
  sessionStorage.removeItem('kurilka-client-session-id');
  sessionStorage.removeItem('kurilka-client-crash-reported');
}

export async function authenticateDevelopment() {
  const response = await fetch(`${API}/auth/development`, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
  if (!response.ok) throw new ApiError(response.status, 'Development preview authentication is unavailable');
  storeSession(await response.json());
}

export function beginOidcLogin() {
  const clientState = crypto.randomUUID();
  sessionStorage.removeItem(oidcPendingKey);
  sessionStorage.setItem(oidcStateKey, clientState);
  sessionStorage.setItem(oidcReturnKey, safeOidcReturnPath(location.pathname));
  location.assign(`${API}/auth/oidc/start?client_state=${encodeURIComponent(clientState)}`);
}

export class OidcCompletionError extends Error {
  constructor(public reason: 'invalid' | 'expired' | 'temporary', public retryable: boolean) {
    super(reason);
  }
}

type PendingOidcCompletion = { code: string; state: string; createdAt: number };

function clearOidcCompletion() {
  sessionStorage.removeItem(oidcStateKey);
  sessionStorage.removeItem(oidcReturnKey);
  sessionStorage.removeItem(oidcPendingKey);
}

export async function consumeOidcCompletion(): Promise<boolean> {
  const values = new URLSearchParams(location.hash.slice(1));
  const callbackCode = values.get('oidc_code');
  const callbackState = values.get('state');
  let pending: PendingOidcCompletion | null = null;
  if (callbackCode || callbackState) {
    history.replaceState(null, '', location.pathname + location.search);
    const expected = sessionStorage.getItem(oidcStateKey);
    if (!callbackCode || !callbackState || !expected || callbackState !== expected) {
      clearOidcCompletion();
      throw new OidcCompletionError('invalid', false);
    }
    pending = { code: callbackCode, state: callbackState, createdAt: Date.now() };
    sessionStorage.setItem(oidcPendingKey, JSON.stringify(pending));
  } else {
    try { pending = JSON.parse(sessionStorage.getItem(oidcPendingKey) || 'null') as PendingOidcCompletion | null; }
    catch { clearOidcCompletion(); throw new OidcCompletionError('invalid', false); }
  }
  if (!pending) return false;
  const expected = sessionStorage.getItem(oidcStateKey);
  const returnPath = safeOidcReturnPath(sessionStorage.getItem(oidcReturnKey));
  if (!expected || pending.state !== expected) {
    clearOidcCompletion();
    throw new OidcCompletionError('invalid', false);
  }
  if (Date.now() - pending.createdAt > oidcPendingTtlMs) {
    clearOidcCompletion();
    throw new OidcCompletionError('expired', false);
  }
  let response: Response;
  try {
    response = await fetch(`${API}/auth/oidc/complete`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code: pending.code, client_state: pending.state }) });
  } catch {
    throw new OidcCompletionError('temporary', true);
  }
  if (!response.ok) {
    if (response.status < 500) clearOidcCompletion();
    throw new OidcCompletionError(response.status >= 500 ? 'temporary' : 'expired', response.status >= 500);
  }
  storeSession(await response.json());
  clearOidcCompletion();
  if (location.pathname !== returnPath) {
    history.replaceState(null, '', returnPath);
    window.dispatchEvent(new PopStateEvent('popstate'));
  }
  return true;
}

export async function authenticate(initData: string) {
  const response = await fetch(`${API}/auth/telegram`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ init_data: initData }) });
  if (!response.ok) throw new Error('Не удалось подтвердить Telegram');
  const session: Session = await response.json();
  storeSession(session);
  return session;
}

export class ApiError extends Error {
  constructor(public status: number, message: string, public code = `http_${status}`, public requestId?: string, public fieldErrors?: { field: string; message: string }[]) { super(message); }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = authToken();
  const response = await fetch(`${API}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) } });
  if (response.status === 401 && authToken() === token) clearSession();
  if (!response.ok) {
    const fallback = `Request failed with status ${response.status}`;
    try {
      const payload = await response.json();
      const error = payload?.error;
      throw new ApiError(response.status, error?.message || fallback, error?.code, error?.request_id, error?.field_errors);
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError(response.status, fallback);
    }
  }
  return response.status === 204 ? undefined as T : response.json();
}

export const api = {
  launchStatus: () => request<LaunchStatus>('/launch-status'),
  bootstrap: () => request<Bootstrap>('/bootstrap'),
  dashboard: () => request<Dashboard>('/dashboard'),
  quitPlan: () => request<QuitPlan>('/quit-plan'),
  onboard: (data: object) => request<{ phase: string }>('/onboarding', { method: 'POST', body: JSON.stringify(data) }),
  consent: () => request<{ consent_version: string; consent_digest: string; age_confirmed: boolean }>('/consent', { method: 'POST', body: JSON.stringify({ age_confirmed: true, consent: true }) }),
  event: (data: EventInput) => request<{ intervention: string }>('/events', { method: 'POST', body: JSON.stringify(data) }),
  events: () => request<EventItem[]>('/events'),
  updateEvent: (id: number, data: { trigger?: string | null; intensity?: number | null; note?: string }) => request<EventItem>(`/events/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteEvent: (id: number) => request<{ status: 'deleted'; phase: Dashboard['phase']; remaining: number }>(`/events/${id}`, { method: 'DELETE' }),
  journal: (filters: { period: '7d' | '30d' | 'all'; type: 'all' | EventItem['kind'] | 'coping'; trigger?: string; cursor?: string; limit?: number }) => { const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value !== undefined).map(([key, value]) => [key, String(value)])); return request<JournalResponse>(`/journal?${query}`); },
  copingTechniques: () => request<{ content_version: string; content_digest: string; techniques: CopingTechnique[]; personalized?: boolean }>('/coping-techniques'),
  startCoping: (data: CopingCreateInput) => request<CopingSession>('/coping-sessions', { method: 'POST', body: JSON.stringify(data) }),
  updateCoping: (id: number, data: CopingPatchInput) => request<CopingSession>(`/coping-sessions/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  plan: (data: object) => request<{ phase: string; remaining: number }>('/quit-plan', { method: 'PUT', body: JSON.stringify(data) }),
  preferences: () => request<Preferences>('/notification-preferences'),
  notificationStatus: () => request<NotificationStatus>('/notification-status'),
  savePreferences: (data: Preferences) => request<Preferences>('/notification-preferences', { method: 'PUT', body: JSON.stringify(data) }),
  testNotification: () => request<{ status: string; duplicate: boolean }>('/notifications/test', { method: 'POST' }),
  pushKey: () => request<{ public_key: string }>('/push-public-key'),
  savePush: (data: { endpoint: string; p256dh: string; auth: string }) => request<void>('/push-subscription', { method: 'PUT', body: JSON.stringify(data) }),
  deletePush: () => request<void>('/push-subscription', { method: 'DELETE' }),
  feedback: (data: { category: 'bug' | 'idea' | 'support' | 'content'; body: string }) => request<{ feedback_id: number; status: string }>('/feedback', { method: 'POST', body: JSON.stringify(data) }),
  clientTelemetry: (event: 'session_started' | 'crash', clientSessionId: string) => request<void>('/client-telemetry', { method: 'POST', body: JSON.stringify({ event, client_session_id: clientSessionId }) }),
  adminOverview: (period = '30d', source = '') => request<AdminOverview>(`/admin/overview?period=${encodeURIComponent(period)}${source ? `&source=${encodeURIComponent(source)}` : ''}`),
  adminFeedback: (status: 'open' | 'resolved' = 'open') => request<AdminFeedback[]>(`/admin/feedback?status=${status}`),
  updateAdminFeedback: (id: number, status: 'open' | 'resolved') => request<{ id: number; status: string }>(`/admin/feedback/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  logout: () => request<void>('/logout', { method: 'POST' }),
  export: () => request<object>('/privacy-export'),
  erase: () => request<void>('/account', { method: 'DELETE' }),
};
