// frontend/e2e/landing.spec.ts
import { test, expect } from '@playwright/test';

test('has expected title and navigation works', async ({ page }) => {
  // 1. Go to the landing page
  await page.goto('/');

  // 2. Expect a title "to contain" a substring.
  await expect(page).toHaveTitle(/MyLeads AI/);

  // 3. Click the login button.
  await page.click('text=התחברות');

  // 4. Expects the URL to contain '/login'.
  await expect(page).toHaveURL(/.*\/login/);
});