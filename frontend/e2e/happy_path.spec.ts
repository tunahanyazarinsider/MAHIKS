import { test, expect, Page } from '@playwright/test';
import { TEST_USER, TEST_QUESTION } from './fixtures';

async function login(page: Page) {
  await page.goto('/');
  await page.locator('#email').fill(TEST_USER.email);
  await page.locator('#password').fill(TEST_USER.password);
  await page.getByRole('button', { name: 'Giriş Yap' }).click();
  await expect(page.getByRole('button', { name: /Yeni Sohbet/i })).toBeVisible();
}

test.describe('Happy path: login → ask → cite → feedback → reload-persists', () => {
  test('full flow', async ({ page }) => {
    await login(page);

    // Start fresh so this test never collides with whatever the user did
    // in the seeded conversation.
    await page.getByRole('button', { name: /Yeni Sohbet/i }).click();

    // Type the question and submit via Enter.
    const input = page.getByPlaceholder(/Sağlık sigortanızla ilgili sorunuzu yazın/);
    await input.fill(TEST_QUESTION);
    await input.press('Enter');

    // Wait until the agent message has a backend ID — that's our signal
    // that streaming completed AND the message was persisted server-side.
    const agentMsg = page
      .locator('[data-testid="agent-message"][data-message-id]:not([data-message-id=""])')
      .last();
    await expect(agentMsg).toBeVisible({ timeout: 60_000 });

    // The answer should contain at least one [1] citation badge.
    const cite1 = page.getByRole('button', { name: 'Kaynak 1' });
    await expect(cite1).toBeVisible();

    // Clicking a citation badge keeps the citation panel visible (it
    // auto-opens because the answer contains [N]).
    await cite1.click();

    // Thumbs UI is rendered and the down-thumb opens the reason form.
    const thumbDown = page.getByRole('button', { name: 'Bu yanıtı beğenme' });
    await expect(thumbDown).toBeEnabled();
    await thumbDown.click();

    const reasonTextarea = page.getByPlaceholder(/kaynak eksik/i);
    await expect(reasonTextarea).toBeVisible();
    await reasonTextarea.fill('E2E test — kaynak eksik gibi geldi');
    await page.getByRole('button', { name: 'Gönder' }).click();

    // After submission the down-thumb should now show aria-pressed="true".
    await expect(thumbDown).toHaveAttribute('aria-pressed', 'true');

    // Reload the page and confirm the feedback state is persisted.
    await page.reload();
    await expect(page.getByRole('button', { name: /Yeni Sohbet/i })).toBeVisible();

    // The same agent message should reload with the same feedback state.
    const reloadedThumbDown = page.getByRole('button', { name: 'Bu yanıtı beğenme' }).first();
    await expect(reloadedThumbDown).toBeVisible({ timeout: 30_000 });
    await expect(reloadedThumbDown).toHaveAttribute('aria-pressed', 'true');

    // The citations from the previous answer should also be persisted —
    // the [1] badge in the markdown re-renders.
    await expect(page.getByRole('button', { name: 'Kaynak 1' }).first()).toBeVisible();
  });

  test('low-confidence banner appears for out-of-scope question', async ({ page }) => {
    await login(page);
    await page.getByRole('button', { name: /Yeni Sohbet/i }).click();

    const input = page.getByPlaceholder(/Sağlık sigortanızla ilgili sorunuzu yazın/);
    // Deliberately out-of-scope — the corpus is Turkish health insurance,
    // not Istanbul weather. Should trigger the low-confidence gate.
    await input.fill('İstanbul\'da bugün hava nasıl?');
    await input.press('Enter');

    const agentMsg = page
      .locator('[data-testid="agent-message"][data-message-id]:not([data-message-id=""])')
      .last();
    await expect(agentMsg).toBeVisible({ timeout: 60_000 });

    // Either the amber banner appears, or the model refuses gracefully —
    // both are acceptable behaviors. Assert at least one of them.
    const banner = page.getByText(/Düşük kaynak güveni/);
    const refusal = page.getByText(/yeterli bilgim yok/i);
    await expect(banner.or(refusal)).toBeVisible({ timeout: 5_000 });
  });
});
