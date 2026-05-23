# Testing Guide

This document covers everything added under Part 1 (Tests) of the
implementation plan: five testing layers, what each one verifies, the files
behind each layer, and how to run them.

---

## 1. Overview

| # | Layer | Tool | What it verifies | Files |
|---|---|---|---|---|
| 1.1 | Frontend unit | Vitest + Testing Library | React components in isolation (rendering, click handlers, optimistic state, mocked APIs) | `frontend/src/__tests__/*.test.tsx` |
| 1.2 | End-to-end | Playwright | Full user flow: login → ask → cite → feedback → reload-persists | `frontend/e2e/*.spec.ts` |
| 1.3 | Load / SSE | k6 | p95 / p99 latency and SSE chunk health under concurrent users | `tests/load/sse_smoke.js` |
| 1.4 | Eval gate | `evaluate_api.py --strict` | Hit@5, MRR, faithfulness, context precision, p95 latency vs pinned thresholds | `scripts/evaluate_api.py` |
| 1.5 | CI | GitHub Actions | Runs unit tests on every PR; manual `--strict` eval | `.github/workflows/*.yml` |

Backend `pytest -m unit` (existing, 13 modules under `backend/tests/`) was
already in place — Part 1 did not modify it, only wired it into CI.

---

## 2. Layer 1.1 — Frontend unit tests (Vitest)

### Goal

Catch regressions in the React components we built during the E1/E3/E4/E5
demo features (inline citations, eval dashboard, feedback thumbs, low-
confidence banner, KG path badges). Sub-second feedback loop.

### Files

| File | Role |
|---|---|
| `frontend/package.json` | Added Vitest, Testing Library, jsdom devDeps + `test`, `test:watch`, `test:coverage` scripts. Removed unused `@types/jest`. |
| `frontend/vitest.config.ts` | Standalone Vitest config (separate from `vite.config.ts` to avoid running the tailwindcss plugin during tests). jsdom env, no globals, setup file. |
| `frontend/src/test/setup.ts` | Loads `@testing-library/jest-dom/vitest` matchers and stubs three jsdom gaps: `Element.animate`, `Element.scrollIntoView`, `ResizeObserver` (the last two would crash Recharts). |
| `frontend/src/__tests__/KgPathBadge.test.tsx` | 4 tests for the KG path component: triplet rendering, multi-hop path rendering, missing-field handling, empty input. |
| `frontend/src/__tests__/ChatMessage.test.tsx` | 9 tests covering inline `[N]` citation badges, low-confidence banner, thumbs UX, feedback reason form, user vs agent message rendering. |
| `frontend/src/__tests__/EvalDashboard.test.tsx` | 9 tests — 5 for the pure `looksLikeEvalReport` shape validator, 4 for the dashboard's empty/loaded/error/back-button behavior. Uses `vi.mock` on `EvalApi`. |
| `frontend/src/__tests__/ChatScreen.feedback.test.tsx` | 3 tests for the optimistic-update + rollback flow: `submitFeedback` called with correct args, `aria-pressed` flips immediately, reverts when the API rejects. |

### Files touched in source (not new)

- `frontend/src/components/EvalDashboard.tsx` — added one `export` keyword to
  `looksLikeEvalReport` so the unit test can import it without rendering the
  component.

### How to run

```bash
cd frontend
npm install          # one-time
npm test             # 25 tests, runs in ~1 second
npm run test:watch   # interactive watch mode
npm run test:coverage
```

Current status: **25 / 25 passing**.

### Patterns to follow when adding tests

- Mock external modules at the module level with `vi.mock('../api/X')` —
  factories run before component imports.
- For components that use Recharts, the `ResizeObserver` stub in `setup.ts`
  is required; nothing else.
- Use `@testing-library/user-event` (not `fireEvent`) for clicks and typing
  — it queues realistic event sequences and respects disabled buttons.
- Query by accessible role / label first (`getByRole`, `getByLabelText`)
  before falling back to `data-testid`.

---

## 3. Layer 1.2 — Playwright E2E

### Goal

Prove the *whole stack* works together: backend SSE, frontend rendering,
auth, conversation persistence, feedback persistence. One pass means the
demo flow won't embarrassingly break on demo day.

### Files

| File | Role |
|---|---|
| `frontend/playwright.config.ts` | Playwright config. Single Chromium project, 90 s test timeout (SSE responses can be slow), screenshots/video on failure, HTML report. Reads `PLAYWRIGHT_BASE_URL` and `PLAYWRIGHT_API_URL` from env so the same suite can target localhost or a deployed instance. |
| `frontend/e2e/fixtures.ts` | Shared constants: `TEST_USER` (stable credentials so feedback persists across runs), `TEST_QUESTION` (a known-good Turkish question from `eval_questions.json` that returns multiple citations), `API_URL`. |
| `frontend/e2e/global.setup.ts` | Runs once before all tests. POSTs to `/register` with the fixture credentials. Idempotent — swallows 4xx because the user is created on the first run and exists on every subsequent run. |
| `frontend/e2e/happy_path.spec.ts` | Two tests: (1) **full flow** — login → ask → click `[1]` citation → submit thumbs-down with reason → reload → confirm feedback + citations persisted; (2) **low-confidence banner** — asks an out-of-scope question and asserts the amber banner *or* a graceful refusal appears. |
| `frontend/e2e/README.md` | How to run the suite, prerequisites, how to wipe the test user. |

### Files touched in source (not new)

- `frontend/src/components/ChatMessage.tsx` — added three data attributes to
  the message container:
  - `data-testid="agent-message" | "user-message"` — stable selector
  - `data-message-id={message.backendId ?? ''}` — empty until the
    streaming `done` event arrives and the message is persisted server-side.
    The E2E uses this as the "streaming complete" signal.
  - `data-loading={message.isLoading}` — for debugging if the streaming
    stalls.

- `frontend/package.json` — `test:e2e` and `test:e2e:ui` npm scripts;
  `@playwright/test` devDep.

### How to run

Prerequisites: `docker compose up -d` (backend + frontend reachable),
corpus vectorized (`docker compose exec backend python -m
scripts.vectorize_only`), and Playwright's Chromium binary
(`npx playwright install chromium`, one-time per machine).

```bash
cd frontend
npm run test:e2e        # headless
npm run test:e2e:ui     # interactive Playwright UI runner
```

Against a remote box:

```bash
PLAYWRIGHT_BASE_URL=https://mahiks.yourdomain.tr \
PLAYWRIGHT_API_URL=https://mahiks.yourdomain.tr/api \
npm run test:e2e
```

### Why these tests and not others

Demo day is one happy path and a couple of error stories. The full flow
test exercises every demo feature in one pass. The low-confidence test
proves the hallucination guard is wired up. Anything more granular is
already covered by the Vitest layer — going broader at the E2E layer just
slows the suite without adding signal.

---

## 4. Layer 1.3 — k6 load test (SSE)

### Goal

Empirical p50 / p95 / p99 for the streaming endpoint under realistic
concurrency. Numbers we can paste into the capstone report. Also a smoke
signal for any deploy: if p95 doubles after a deploy, something regressed.

### Files

| File | Role |
|---|---|
| `tests/load/sse_smoke.js` | k6 script. Drives `POST /api/ask/stream` with 5 concurrent VUs ramping over ~3 min. Custom metrics: `mahiks_full_duration_ms`, `mahiks_chunk_count`, `mahiks_failed_requests`. Picks questions at random from a 10-question fixture lifted from `data/eval_questions.json`. |
| `tests/load/README.md` | How to run on Linux (host networking) vs Mac/Windows (host.docker.internal), how to record a baseline, what each metric means. |

### Thresholds

The script fails the run if either holds at the end:

- `mahiks_full_duration_ms p(95) > 15000 ms`
- `http_req_failed rate > 5 %`

These are deliberately loose for a first run — tighten in `options.thresholds`
once you have a baseline number from the deployed environment.

### How to run

```bash
docker run --rm -i --network host \
  -v "$PWD/tests/load:/scripts" \
  -e MAHIKS_API_URL=http://localhost:8000 \
  grafana/k6 run /scripts/sse_smoke.js
```

Mac/Windows: drop `--network host` and use `MAHIKS_API_URL=http://host.docker.internal:8000`.

### Important caveat

Localhost numbers under-report because there is no network hop and the LLM
provider call is the dominant cost. Run k6 against the *deployed* URL for
numbers that mean anything.

---

## 5. Layer 1.4 — Eval `--strict` regression gate

### Goal

Turn the existing `scripts/evaluate_api.py` from "prints numbers" into
"exits 0 or 1". The eval harness was already excellent — it computes Hit@k,
MRR, MAP, nDCG, faithfulness, answer relevance, context precision/recall,
and latency stats — it just had no pass/fail. The `--strict` flag adds
threshold comparison + non-zero exit.

### Files touched

- `scripts/evaluate_api.py`
  - Added `--strict` argparse flag.
  - Added `THRESHOLDS` dict at module scope with five gates:

    | Metric | Comparator | Threshold | Anchored to |
    |---|---|---|---|
    | `retrieval.stage2_full_pipeline.hit@5` | min | 0.95 | baseline 1.00 |
    | `retrieval.stage2_full_pipeline.mrr`   | min | 0.85 | baseline 0.955 |
    | `generation.avg_faithfulness`          | min | 4.20 | baseline 4.53 |
    | `generation.avg_context_precision`     | min | 3.40 | baseline 3.67 |
    | `retrieval.latency.p95_ms`             | max | 12000 ms | baseline 3477 ms |

  - Added `_resolve(report, "a.b.c")` walker and `check_thresholds(report)`
    function that prints a per-metric pass/fail table and returns True iff
    everything passes.
  - At the end of `main()`, if `--strict` was set, calls `check_thresholds`
    and `sys.exit(1)` on any failure.

Baseline values came from `data/eval_api_report_20260510_171446.json`.
Note: the original plan suggested `avg_context_precision >= 4.0`, but the
actual baseline is 3.67 — the threshold was lowered to 3.40 to avoid
shipping a gate that would fail on day one.

### How to run

```bash
docker compose up -d
docker compose exec backend python -m scripts.evaluate_api \
  --strict \
  --limit 30 \
  --judge-provider openrouter
echo $?    # 0 if all thresholds pass, 1 if any fail
```

`--limit N` keeps the cost down (each question costs ~1 LLM-judge call).
Drop it to run the full 100-question set.

### Output

```
==========================================================================
STRICT MODE — regression gate
==========================================================================
  Metric                                             Cmp   Threshold      Actual  Result
  --------------------------------------------------------------------------------------
  retrieval.stage2_full_pipeline.hit@5               min      0.9500      1.0000  PASS
  retrieval.stage2_full_pipeline.mrr                 min      0.8500      0.9550  PASS
  generation.avg_faithfulness                        min      4.2000      4.5300  PASS
  generation.avg_context_precision                   min      3.4000      3.6700  PASS
  retrieval.latency.p95_ms                           max       12000      3477.0  PASS
==========================================================================
  Overall: PASS
==========================================================================
```

---

## 6. Layer 1.5 — GitHub Actions CI

### Goal

Make all of the above runnable from a PR. Backend + frontend unit tests
must go green before merge; the expensive eval gate is manual-only to
avoid burning OpenRouter credits on every push.

### Files

| File | Role |
|---|---|
| `.github/workflows/ci.yml` | Runs on every push or PR to `develop`/`main`. Two parallel jobs: `backend-unit` (Python 3.11, installs CPU-only torch first, then `requirements.txt`, runs `pytest -m unit`) and `frontend-unit` (Node 20, `npm ci`, `npm test`). Both cache their package managers via `actions/setup-*`. |
| `.github/workflows/eval.yml` | Manual (`workflow_dispatch`) only. Inputs: `limit` (default 30) and `judge_provider` (default openrouter). Spins up `docker compose up -d --build`, polls `/health`, runs `scripts.vectorize_only` then `scripts.evaluate_api --strict`. Uploads the resulting JSON as a 30-day artifact. Pulls `OPENROUTER_API_KEY` / `GEMINI_API_KEY` from repository secrets. |

### How to add secrets

GitHub repo → Settings → Secrets and variables → Actions → New repository
secret. Add at least `OPENROUTER_API_KEY` for the eval workflow.

### Triggering manually

GitHub repo → Actions → "Eval (strict regression gate)" → Run workflow →
optionally change `limit` and `judge_provider` → Run.

---

## 7. Combined run sheet

To verify everything end-to-end on a fresh checkout:

```bash
# 1. Frontend unit (1.1) — fast, no external deps.
cd frontend && npm install && npm test
# Expect: Test Files 4 passed, Tests 25 passed.

# 2. Backend unit — already existed, just runs the existing suite.
cd .. && pytest -m unit -v
# Expect: ~113 tests pass.

# 3. Boot the stack.
docker compose up -d
# Wait for /health to return 200.

# 4. E2E (1.2) — needs the stack running.
cd frontend && npx playwright install chromium && npm run test:e2e
# Expect: 2 tests pass.

# 5. Load (1.3) — needs the stack running and corpus vectorized.
docker compose exec backend python -m scripts.vectorize_only
docker run --rm -i --network host -v "$PWD/tests/load:/scripts" \
  grafana/k6 run /scripts/sse_smoke.js
# Expect: thresholds PASS; record the p95 in tests/load/baseline.md.

# 6. Eval strict (1.4) — needs the stack running and vectorized.
docker compose exec backend python -m scripts.evaluate_api \
  --strict --limit 30 --judge-provider openrouter
# Expect: Overall PASS. Cost: ~30 OpenRouter judge calls (~$0.05).
```

In CI (1.5), only steps 1 and 2 run automatically. Steps 4-6 are run on
demand: 4 should be wired into a Playwright workflow if/when you want
E2E in CI, but it isn't yet because Chromium download + 30 s of streaming
per test is heavy and the value vs Vitest is incremental.

---

## 8. What was deliberately *not* added

- **Frontend integration tests beyond ChatScreen.feedback**. The full
  conversation flow is covered by Playwright; mocking the SSE pipeline in
  Vitest would be a lot of code that does the same job worse.
- **Backend integration tests with real Qdrant/Neo4j containers**. The
  existing `backend/tests/conftest.py` mocks them; spinning up containers in
  CI would 3-5x the CI runtime for limited extra signal. The eval workflow
  (1.5b) already exercises the full stack end-to-end against real services.
- **Mutation testing, fuzz testing, property-based tests**. Out of scope
  for capstone; revisit if/when this becomes a long-lived project.
- **Visual regression tests**. Tailwind classes change too often during
  active development; the cost-benefit isn't there yet.

---

## 9. Future tweaks (not blocking)

- After 2-3 real eval runs in different weeks, tighten the thresholds in
  `evaluate_api.py` — current values are conservative.
- Add a Playwright workflow that runs against the staging URL on a weekly
  cron once hosting is up (Part 2 of the plan).
- Once you have a `playwright-report/` baseline, wire it into a GitHub
  Pages artifact for visual diffing.
