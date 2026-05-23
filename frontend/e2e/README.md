# End-to-end tests (Playwright)

[`happy_path.spec.ts`](./happy_path.spec.ts) walks the full user flow:
login → ask → click citation → submit thumbs-down feedback with reason →
reload → confirm feedback + citations persisted.

## Prerequisites

1. **Backend + frontend running.** From the repo root:
   ```bash
   docker compose up -d
   ```
   Wait until `curl http://localhost:8000/health` returns 200 and the frontend
   is reachable at `http://localhost:3000`.

2. **Corpus vectorized.** If you haven't already:
   ```bash
   docker compose exec backend python -m scripts.vectorize_only
   ```
   Without this, the SSE endpoint returns empty answers and the citation
   assertions will fail.

3. **Playwright browser binary** (one-time per machine):
   ```bash
   cd frontend
   npx playwright install chromium
   ```

## Running

```bash
cd frontend
npm run test:e2e          # headless
npm run test:e2e:ui       # opens Playwright's interactive runner
```

Override the URLs when pointing at a deployed instance:

```bash
PLAYWRIGHT_BASE_URL=https://mahiks.yourdomain.tr \
PLAYWRIGHT_API_URL=https://mahiks.yourdomain.tr/api \
npm run test:e2e
```

## What the suite covers

| Test | What it asserts |
|---|---|
| **Happy path** | Login form accepts seeded credentials. After asking a known-good question, the agent message receives a `data-message-id` (streaming + persistence complete). At least one `[N]` citation badge is rendered, clickable. Thumbs-down opens a reason form; submitting flips `aria-pressed`. After a page reload, both the feedback state and the citation badges still render. |
| **Low-confidence banner** | An out-of-scope Turkish question ("İstanbul'da bugün hava nasıl?") either triggers the amber "Düşük kaynak güveni" banner or a graceful refusal. |

## How the seeded user is created

`global.setup.ts` runs once before any tests and `POST`s to `/register` with
the fixture credentials. The endpoint returns 4xx on a duplicate, which we
swallow — so the setup is idempotent across runs.

If you need to wipe the user (e.g. resetting feedback state from scratch):

```bash
docker compose exec mysql \
  mysql -uroot -p"$MYSQL_PASSWORD" mahiks_db \
  -e "DELETE FROM users WHERE email='e2e@mahiks.local'"
```

## Reports

On a CI run, the HTML report is written to `frontend/playwright-report/` and
uploaded as a GitHub Actions artifact. Locally, run `npx playwright
show-report` after a test to open it.
