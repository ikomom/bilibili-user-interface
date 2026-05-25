import { expect, test } from "@playwright/test"

test("Bilibili home route renders landing page", async ({ page }) => {
  await page.goto("/bilibili")

  await expect(
    page.getByRole("heading", { name: "Bilibili 内容同步", exact: true }),
  ).toBeVisible()
})

test("Bilibili account child route renders account page", async ({ page }) => {
  await page.goto("/bilibili/accounts")

  await expect(
    page.getByRole("heading", { name: "B站账户", exact: true }),
  ).toBeVisible()
  await expect(page.getByText("管理用于同步的 B站登录凭证。")).toBeVisible()
})

test("Bilibili subscription child route renders subscriptions page", async ({
  page,
}) => {
  await page.goto("/bilibili/subscriptions")

  await expect(
    page.getByRole("heading", { name: "UP 主订阅", exact: true }),
  ).toBeVisible()
  await expect(page.getByText("创建订阅并同步 UP 主内容。")).toBeVisible()
})

test("Bilibili subscription detail child route renders detail page", async ({
  page,
}) => {
  await page.goto("/bilibili/subscriptions/test-subscription")

  await expect(
    page.getByRole("heading", { name: "订阅详情", exact: true }),
  ).toBeVisible()
  await expect(page.getByText("UID test-subscription")).toBeVisible()
})
