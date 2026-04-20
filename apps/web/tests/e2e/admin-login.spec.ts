import { test, expect } from "@playwright/test";

const ADMIN_PASSWORD = "test-admin-password-w1"; // pragma: allowlist secret

test.describe("admin login", () => {
  test("rejects wrong password", async ({ page }) => {
    await page.goto("/admin");
    await expect(page).toHaveURL(/\/admin\/login/);

    await page.fill('input[name="password"]', "wrong");
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL(/\/admin\/login\?error=invalid/);
    await expect(page.getByText(/wrong password/i)).toBeVisible();
  });

  test("accepts correct password and lands on dashboard", async ({ page }) => {
    await page.goto("/admin");
    await page.fill('input[name="password"]', ADMIN_PASSWORD);
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL("/admin");
    await expect(
      page.getByRole("heading", { name: /dashboard/i }),
    ).toBeVisible();
  });

  test("middleware redirects unauthenticated /admin/sources to login", async ({
    page,
    context,
  }) => {
    await context.clearCookies();
    await page.goto("/admin/sources");
    await expect(page).toHaveURL(/\/admin\/login/);
  });
});
