# Load tests

[`sse_smoke.js`](./sse_smoke.js) drives the MAHIKS-TR streaming endpoint
(`POST /api/ask/stream`) with [k6](https://k6.io) and reports p50/p95/p99
end-to-end response time and SSE chunk counts.

## Running

The backend must be running and the corpus must be vectorized (otherwise the
endpoint just returns empty answers).

```bash
# Linux host (uses host networking — works against localhost:8000 directly).
docker run --rm -i --network host \
  -v "$PWD/tests/load:/scripts" \
  -e MAHIKS_API_URL=http://localhost:8000 \
  grafana/k6 run /scripts/sse_smoke.js

# macOS / Windows host (no --network host support).
docker run --rm -i \
  -v "$PWD/tests/load:/scripts" \
  -e MAHIKS_API_URL=http://host.docker.internal:8000 \
  grafana/k6 run /scripts/sse_smoke.js
```

For a real reading, point `MAHIKS_API_URL` at the deployed staging URL —
localhost numbers under-report because there is no network hop.

## What it measures

| Metric | What it means |
|---|---|
| `http_req_duration` (built-in) | Time from POST send to last byte of SSE body. |
| `mahiks_full_duration_ms` | Same, measured by the test for visibility. |
| `mahiks_chunk_count` | Number of `data:` frames per response — proxy for streaming health. |
| `http_req_failed` | Fraction of non-2xx responses. |
| `mahiks_failed_requests` | Count of responses that failed *any* check (status, done event, chunk count). |

## Thresholds

The script fails the run (k6 exits non-zero) when:

- `mahiks_full_duration_ms p(95)` exceeds **15 000 ms**
- `http_req_failed rate` exceeds **5 %**

Tune in [`sse_smoke.js`](./sse_smoke.js) under `options.thresholds` after a
first real run — the defaults are deliberately loose so a fresh box doesn't
flunk before it warms up.

## Load shape

3 minutes total:

- 30 s ramp from 0 → 5 virtual users
- 2 min steady at 5 VUs
- 15 s ramp down

5 VUs is realistic for a capstone demo. The single GCE `e2-standard-2`
target is happy at this load; pushing to 20+ VUs will queue requests at the
LLM (single-stream Ollama / serial OpenRouter requests) and the numbers
become network-dominated rather than informative.

## Recording a baseline

After the first successful run, save the k6 summary output:

```bash
docker run --rm -i --network host \
  -v "$PWD/tests/load:/scripts" \
  -e MAHIKS_API_URL=http://localhost:8000 \
  grafana/k6 run --summary-export=/scripts/baseline.json /scripts/sse_smoke.js
```

Future runs can diff against `baseline.json` to spot regressions before
they reach production.
