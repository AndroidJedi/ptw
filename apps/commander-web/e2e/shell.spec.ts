import { expect, test } from '@playwright/test'

test('shows owner login on mobile and desktop', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /Керуйте всією системою/ })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Увійти через Google' })).toBeVisible()
  await expect(page.locator('body')).not.toHaveCSS('overflow-x', 'scroll')
})
