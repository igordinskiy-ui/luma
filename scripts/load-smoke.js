import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  scenarios: { beta_capacity: { executor: 'constant-vus', vus: 50, duration: '2m' } },
  thresholds: {
    'http_req_duration{endpoint:dashboard}': ['p(95)<500'],
    'http_req_duration{endpoint:event}': ['p(95)<700'],
    http_req_failed: ['rate<0.01'],
  },
};

const base = __ENV.LOAD_BASE_URL;
const tokens = (__ENV.LOAD_ACCESS_TOKENS || '').split(',').map(value => value.trim()).filter(Boolean);

export function setup() {
  if (!base?.startsWith('https://')) throw new Error('LOAD_BASE_URL must be HTTPS');
  if (tokens.length < 50) throw new Error('LOAD_ACCESS_TOKENS must contain 50 dedicated synthetic-account tokens');
}

export default function () {
  const headers = { Authorization: `Bearer ${tokens[(__VU - 1) % tokens.length]}`, 'Content-Type': 'application/json' };
  const dashboard = http.get(`${base}/api/v1/dashboard`, { headers, tags: { endpoint: 'dashboard' } });
  check(dashboard, { 'dashboard 200': response => response.status === 200 });
  const payload = JSON.stringify({ kind: 'craving', trigger: 'habit', intensity: 3, note: '', client_event_id: `load-${__VU}-${__ITER}-${Date.now()}` });
  const event = http.post(`${base}/api/v1/events`, payload, { headers, tags: { endpoint: 'event' } });
  check(event, { 'event 200': response => response.status === 200 });
  sleep(1);
}
