import { expect, test } from "@playwright/test";

/**
 * Full operator happy-path smoke.
 *
 * Opt-in locally — only runs when `RUN_FULL_SMOKE=1`. In CI, this is intended
 * for nightly/manual dispatch only because it needs seeded DB fixtures plus a
 * live ingest invocation during the source-detail step.
 *
 * Pre-requisites (set up manually before running):
 *   - Postgres running and migrated (`make up && make migrate`).
 *   - `apps/web/.env.local` contains a hash of `test-password-123`. Generate
 *     via `node apps/web/scripts/hash-password.mjs`.
 *   - `make ingest CMD="seed-sources --path ../../config/sources.yaml"` ran.
 *   - `node apps/web/scripts/seed-happy-path-smoke.mjs` seeded ADA plus the
 *     smoke review/event fixtures this test expects.
 *
 * Covers one serial user loop:
 *   login -> dashboard -> sources list -> source detail
 *   -> Run Now -> Toggle Active -> review list -> review resolve
 *   -> events list -> event detail -> save edit -> unpublish
 *   -> logout -> re-auth redirect
 *
 * Uses generous per-assertion timeouts because Next.js dev-mode compiles each
 * admin route on first hit (10-30s each), which would otherwise trip the
 * default 5s toHaveURL timeout.
 */

const ROUTE_TIMEOUT = 60_000;

test.skip(
  process.env.RUN_FULL_SMOKE !== "1",
  "opt-in smoke — set RUN_FULL_SMOKE=1 with seeded fixtures in place",
);

test("operator happy path", async ({ page }) => {
  test.setTimeout(600_000);

  // 1. Unauthenticated /admin redirects to login.
  await page.goto("/admin");
  await page.waitForURL(/\/admin\/login/, { timeout: ROUTE_TIMEOUT });

  // 2. Submit correct password → dashboard.
  await page.fill('input[name="password"]', "test-password-123"); // pragma: allowlist secret
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForURL("/admin", { timeout: ROUTE_TIMEOUT });
  await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible({
    timeout: ROUTE_TIMEOUT,
  });

  // 3. Navigate to sources list — ADA row visible.
  await page.getByRole("link", { name: "Sources", exact: true }).click();
  await page.waitForURL("/admin/sources", { timeout: ROUTE_TIMEOUT });
  const adaRow = page.locator("tr", {
    hasText: "American Dental Association",
  });
  await expect(adaRow).toBeVisible({
    timeout: ROUTE_TIMEOUT,
  });

  // 4. Open ADA source detail via the row's "Open" link.
  await adaRow.getByRole("link", { name: "Open" }).click();
  await page.waitForURL(/\/admin\/sources\/[0-9a-f-]{36}/, {
    timeout: ROUTE_TIMEOUT,
  });
  const sourceDetailUrl = page.url();
  await expect(page.getByRole("button", { name: /run now/i })).toBeVisible({
    timeout: ROUTE_TIMEOUT,
  });

  // 5. Click Run Now — expect redirect back to same detail page.
  await page.getByRole("button", { name: /run now/i }).click();
  await page.waitForURL(sourceDetailUrl, { timeout: ROUTE_TIMEOUT });

  // 6. Toggle Active — button label flips after redirect.
  const toggleLabelBefore = (
    await page.getByRole("button", { name: /pause|resume/i }).textContent()
  )?.trim();
  await page.getByRole("button", { name: /pause|resume/i }).click();
  await page.waitForURL(sourceDetailUrl, { timeout: ROUTE_TIMEOUT });
  const toggleLabelAfter = (
    await page.getByRole("button", { name: /pause|resume/i }).textContent()
  )?.trim();
  expect(toggleLabelAfter).not.toBe(toggleLabelBefore);

  // Restore the source to active for idempotency of future smokes.
  if ((toggleLabelAfter ?? "").toLowerCase().includes("resume")) {
    await page.getByRole("button", { name: /resume/i }).click();
    await page.waitForURL(sourceDetailUrl, { timeout: ROUTE_TIMEOUT });
  }

  // 7. Review list → open first item.
  await page.getByRole("link", { name: "Review", exact: true }).click();
  await page.waitForURL("/admin/review", { timeout: ROUTE_TIMEOUT });
  const openReviewsBefore = await page
    .getByRole("link", { name: "Open" })
    .count();
  expect(openReviewsBefore).toBeGreaterThan(0);
  await page.getByRole("link", { name: "Open" }).first().click();
  await page.waitForURL(/\/admin\/review\/[0-9a-f-]{36}/, {
    timeout: ROUTE_TIMEOUT,
  });

  // 8. Resolve the review item — handler redirects to /admin/review list.
  await page.fill('textarea[name="note"]', "smoke resolved");
  await page.getByRole("button", { name: /mark resolved/i }).click();
  await page.waitForURL("/admin/review", { timeout: ROUTE_TIMEOUT });
  const openReviewsAfter = await page
    .getByRole("link", { name: "Open" })
    .count();
  expect(openReviewsAfter).toBe(openReviewsBefore - 1);

  // 9. Events list → open first event.
  await page.getByRole("link", { name: "Events", exact: true }).click();
  await page.waitForURL(/\/admin\/events/, { timeout: ROUTE_TIMEOUT });
  await expect(page.getByText(/Smoke Test Event/)).toBeVisible({
    timeout: ROUTE_TIMEOUT,
  });
  await page.getByRole("link", { name: "Edit" }).first().click();
  await page.waitForURL(/\/admin\/events\/[0-9a-f-]{36}/, {
    timeout: ROUTE_TIMEOUT,
  });
  const eventDetailUrl = page.url();

  // 10. Edit title and Save.
  const titleInput = page.locator('input[name="title"]');
  const originalTitle = (await titleInput.inputValue()) ?? "";
  const editedTitle = `${originalTitle} (smoke-edited)`;
  await titleInput.fill(editedTitle);
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.waitForURL(eventDetailUrl, { timeout: ROUTE_TIMEOUT });
  await expect(titleInput).toHaveValue(editedTitle);

  // 11. Unpublish — redirects to events list.
  await page.getByRole("button", { name: /unpublish/i }).click();
  await page.waitForURL(/\/admin\/events(\?.*)?$/, {
    timeout: ROUTE_TIMEOUT,
  });
  // Filter to unpublished — edited event should appear.
  await page.locator('select[name="is_published"]').selectOption("false");
  await page.getByRole("button", { name: /filter/i }).click();
  await expect(page.getByText(editedTitle)).toBeVisible({
    timeout: ROUTE_TIMEOUT,
  });

  // 12. Sign out.
  await page.getByRole("button", { name: /sign out/i }).click();
  await page.waitForURL(/\/admin\/login/, { timeout: ROUTE_TIMEOUT });

  // 13. Protected route re-redirects to login.
  await page.goto("/admin/sources");
  await page.waitForURL(/\/admin\/login/, { timeout: ROUTE_TIMEOUT });
});
