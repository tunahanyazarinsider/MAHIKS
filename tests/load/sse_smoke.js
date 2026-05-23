// MAHIKS-TR SSE load test.
//
// Drives POST /api/ask/stream with concurrent VUs (virtual users), measures
// full-response duration and counts SSE chunks per request. The endpoint is
// unauthenticated, so no login step is needed.
//
// Run with:
//   docker run --rm -i --network host \
//     -v "$PWD/tests/load:/scripts" \
//     -e MAHIKS_API_URL=http://localhost:8000 \
//     grafana/k6 run /scripts/sse_smoke.js
//
// On non-Linux hosts (--network host doesn't work on Mac/Windows), use
// MAHIKS_API_URL=http://host.docker.internal:8000 and drop --network host.

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Counter } from 'k6/metrics';
import { SharedArray } from 'k6/data';

const fullDuration = new Trend('mahiks_full_duration_ms', true);
const chunkCount = new Trend('mahiks_chunk_count');
const failedRequests = new Counter('mahiks_failed_requests');

const QUESTIONS = new SharedArray('questions', function () {
  return [
    'Jeneralize lipodistrofi tedavisinde, başlangıç HbA1c düzeyinde en az ne kadar düşüş olması gerekir?',
    'Ortez, protez, tıbbî araç ve gereç, kişi kullanımına mahsus tıbbî cihaz, tıbbî sarf, basit sıhhi sarf ve iyileştirici nitelikteki tıbbî sarf malzemeleri hangi kategoriye dahil edilir?',
    'Yurt dışında yapılacak tetkikler için avans ödemesi nasıl yapılabilir?',
    'Kişilere sağlanan sağlık hizmetlerine ilişkin düzenlenen sağlık raporu bedelleri nasıl faturalandırılır?',
    'Etelkalsetid tedavisi hangi durumlarda sonlandırılır?',
    'Oral esansiyel aminoasit preperatları ve keto analogları tedavisi için hangi kriterlerde başlanır?',
    'Ortodontik tedaviler için düzenlenen sağlık kurulu raporunda imzası bulunan hekim, hastayı hangi durumlarda tedavi edemez?',
    'Hasta kabul işlemlerinde doğrudan veya sevkli müracaatlar hangi sağlık hizmeti sunucuları tarafından kabul edilir?',
    'Sıkışma tipi üriner inkontinans tedavisinde, antikolinerjik/antimuskarinik ilaçların kullanım süresi ve tedavinin tekrarlanma süresi nedir?',
    'Kanser tedavisinde endikasyon dışı ilaç kullanılması durumunda hangi raporun hazırlanması gerekmektedir?',
  ];
});

export const options = {
  // Ramp 0 → 5 VUs over 30 s, hold for 2 min, ramp down. ~3 min total.
  // 5 VUs is realistic for a capstone demo — anything higher is noise.
  stages: [
    { duration: '30s', target: 5 },
    { duration: '2m', target: 5 },
    { duration: '15s', target: 0 },
  ],
  thresholds: {
    // p95 of end-to-end response time. Anchored loosely above the baseline
    // generation latency from data/eval_api_report_20260510_171446.json
    // (gen p95 ~9 s on local Ollama). Tune after the first real run.
    mahiks_full_duration_ms: ['p(95)<15000'],
    // <5 % failed HTTP requests under load.
    http_req_failed: ['rate<0.05'],
  },
};

const BASE_URL = __ENV.MAHIKS_API_URL || 'http://localhost:8000';

export default function () {
  const q = QUESTIONS[Math.floor(Math.random() * QUESTIONS.length)];
  const payload = JSON.stringify({ question: q, include_citations: true });

  const start = Date.now();
  const res = http.post(`${BASE_URL}/api/ask/stream`, payload, {
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    timeout: '60s',
  });
  const elapsed = Date.now() - start;
  fullDuration.add(elapsed);

  // k6 buffers the entire SSE response into res.body. Count `data:` frames
  // to get the chunk count without parsing each one. Subtract 1 because
  // "data:" appears 0 times before the first frame.
  const frames = (res.body || '').split('\ndata:').length - 1;
  chunkCount.add(frames);

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
    'has done event': (r) => (r.body || '').includes('"type": "done"'),
    'at least one chunk': () => frames > 0,
  });
  if (!ok) failedRequests.add(1);

  // Realistic think-time between asks so we don't hammer faster than
  // a real user would. 0–2 s uniform.
  sleep(Math.random() * 2);
}
