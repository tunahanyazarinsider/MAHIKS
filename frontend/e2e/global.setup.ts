import type { FullConfig } from '@playwright/test';
import { API_URL, TEST_USER } from './fixtures';

/**
 * Registers the test user before the E2E run.
 *
 * Idempotent: if the user already exists, the backend returns a 4xx and we
 * swallow it. We use the same fixed credentials across runs so seeded
 * conversation state (feedback persistence) can be re-verified.
 */
export default async function globalSetup(_config: FullConfig) {
  const res = await fetch(`${API_URL}/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: TEST_USER.name,
      email: TEST_USER.email,
      password: TEST_USER.password,
    }),
  }).catch((err) => {
    throw new Error(
      `[e2e setup] Cannot reach backend at ${API_URL}. ` +
        `Is docker compose up? (${err.message})`,
    );
  });

  if (res.ok) {
    console.log(`[e2e setup] Registered test user ${TEST_USER.email}`);
  } else if (res.status >= 400 && res.status < 500) {
    // 400/409/422 — user almost certainly already exists. Swallow.
    console.log(`[e2e setup] Test user already exists (${res.status})`);
  } else {
    throw new Error(`[e2e setup] Register failed: ${res.status} ${await res.text()}`);
  }
}
