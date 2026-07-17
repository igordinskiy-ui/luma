import http from 'k6/http';
import { check, sleep } from 'k6';

const EXPECTED_VUS = 50;
const TEST_DURATION = '2m';
const PRODUCTION_CONFIRMATION = 'owner-approved-production-load';

export const options = {
  scenarios: { beta_capacity: { executor: 'constant-vus', vus: EXPECTED_VUS, duration: TEST_DURATION } },
  thresholds: {
    'http_req_duration{endpoint:dashboard}': ['p(95)<500'],
    'http_req_duration{endpoint:event}': ['p(95)<700'],
    http_req_failed: ['rate<0.01'],
    checks: ['rate==1'],
  },
};

const base = (__ENV.LOAD_BASE_URL || '').replace(/\/$/, '');
const tokens = (__ENV.LOAD_ACCESS_TOKENS || '').split(',').map(value => value.trim()).filter(Boolean);
const targetKind = __ENV.LOAD_TARGET_KIND || 'staging';
const evidencePath = __ENV.LOAD_EVIDENCE_PATH || 'load-smoke-evidence.json';

function validateOrigin(value) {
  let parsed;
  try { parsed = new URL(value); } catch (_) { throw new Error('LOAD_BASE_URL must be a valid HTTPS origin'); }
  if (parsed.protocol !== 'https:' || parsed.username || parsed.password || parsed.pathname !== '/' || parsed.search || parsed.hash) {
    throw new Error('LOAD_BASE_URL must be a credential-free HTTPS origin');
  }
  return parsed.origin;
}

function metricValue(data, metric, value) {
  return data.metrics?.[metric]?.values?.[value] ?? null;
}

function thresholdStatus(data) {
  const statuses = [];
  for (const metric of Object.values(data.metrics || {})) {
    for (const threshold of Object.values(metric.thresholds || {})) statuses.push(threshold.ok === true);
  }
  return statuses.length === 4 && statuses.every(Boolean);
}

export function setup() {
  const origin = validateOrigin(base);
  if (!['staging', 'production'].includes(targetKind)) throw new Error('LOAD_TARGET_KIND must be staging or production');
  if (targetKind === 'production' && __ENV.LOAD_PRODUCTION_CONFIRMATION !== PRODUCTION_CONFIRMATION) {
    throw new Error(`Production load requires LOAD_PRODUCTION_CONFIRMATION=${PRODUCTION_CONFIRMATION}`);
  }
  if (tokens.length !== EXPECTED_VUS || new Set(tokens).size !== EXPECTED_VUS) {
    throw new Error(`LOAD_ACCESS_TOKENS must contain exactly ${EXPECTED_VUS} unique dedicated synthetic-account tokens`);
  }
  return { origin, targetKind };
}

export default function (context) {
  const headers = { Authorization: `Bearer ${tokens[(__VU - 1) % tokens.length]}`, 'Content-Type': 'application/json' };
  const dashboard = http.get(`${context.origin}/api/v1/dashboard`, { headers, tags: { endpoint: 'dashboard' } });
  check(dashboard, { 'dashboard 200': response => response.status === 200 });
  const payload = JSON.stringify({ kind: 'craving', trigger: 'habit', intensity: 3, note: '', client_event_id: `load-${__VU}-${__ITER}-${Date.now()}` });
  const event = http.post(`${context.origin}/api/v1/events`, payload, { headers, tags: { endpoint: 'event' } });
  check(event, { 'event 200': response => response.status === 200 });
  sleep(1);
}

export function handleSummary(data) {
  const evidence = {
    schema: 'luma-load-smoke/v1',
    generated_at: new Date().toISOString(),
    target_kind: targetKind,
    target_origin: (() => { try { return validateOrigin(base); } catch (_) { return null; } })(),
    workload: { virtual_users: EXPECTED_VUS, duration: TEST_DURATION, accounts: EXPECTED_VUS },
    thresholds: { read_p95_ms: 500, write_p95_ms: 700, error_rate: 0.01, checks_rate: 1 },
    observed: {
      read_p95_ms: metricValue(data, 'http_req_duration{endpoint:dashboard}', 'p(95)'),
      write_p95_ms: metricValue(data, 'http_req_duration{endpoint:event}', 'p(95)'),
      error_rate: metricValue(data, 'http_req_failed', 'rate'),
      checks_rate: metricValue(data, 'checks', 'rate'),
    },
    passed: thresholdStatus(data),
  };
  return {
    [evidencePath]: `${JSON.stringify(evidence, null, 2)}\n`,
    stdout: `Load smoke ${evidence.passed ? 'passed' : 'failed'}; sanitized evidence: ${evidencePath}\n`,
  };
}
