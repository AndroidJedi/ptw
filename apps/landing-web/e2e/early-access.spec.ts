import { expect, test } from '@playwright/test'
import defaults from '../../commander-web/src/landing/marketing-defaults.json' with { type: 'json' }

// Public snapshot and submission responses are mocked for responsive UI checks.
const snapshot = {
  canonical_url: 'https://natal-service.com/water-quality', project_name: 'Water fixture', version_sha256: 'a'.repeat(64),
  configuration: {
    schema: 'ptw.landing.configuration.v1', marketing: { ...defaults.configuration, reference_reviews_enabled: true },
    presentation: { language: 'uk', cta_target: 'contacts', heading_scale: 1, spacing: 'comfortable', hero_focus: { x: 50, y: 50 }, visual_break_focus: { x: 50, y: 50 } },
    theme: { background_color: '#ffffff', surface_color: '#ffffff', text_color: '#17263c', accent_color: '#3489ed', font_family: 'Manrope', heading_font_family: 'Manrope', corner_radius: 24 },
    hero: { alignment: 'left', image_position: 'right' }, features: { layout: 'three_columns' }, social_proof: { layout: 'cards' }, visual_break: { height: 'medium' }, contacts: { alignment: 'left' }, faq: { style: 'divided' },
    showcase: { gradient_end: '#08cbb5', screen_scale: 1, screen_offset: 32 },
  },
  content: {
    schema: 'ptw.landing.content.v1', hero: { title: 'Порівняйте воду', supporting_text: 'Тестовий опис продукту.', cta_label: 'Спробувати', visual_direction: '' },
    features: [1,2,3].map(i => ({ title: `Можливість ${i}`, description: 'Опис можливості.' })),
    social_proof: { heading: 'Відгуки', items: [] }, visual_break: { visual_direction: '' },
    contacts: { heading: 'Зв’язок', supporting_text: 'Поставте запитання.', email: '', phone: '', url: '', instagram: '' },
    faq: [{ question: 'Що це?', answer: 'Тестовий макет.' }], marketing: { ...defaults.content, store_label: 'Застосунок Natal' },
    app_screens: [1,2,3].map(i => ({ title: `Екран ${i}`, description: 'Тестовий екран.', visual_direction: '' })),
  }, assets: {}, asset_variants: {},
}
test('all five early-stage buttons collect questions or contacts, retain uncertain requests and never track form text', async ({ page }, info) => {
  const inquiries: Array<Record<string, unknown>> = [], events: Array<Record<string, unknown>> = []
  let fail = true
  await page.route('**/api/v1/public/landings/water-quality', route => route.fulfill({ json: { ...snapshot, assets: {}, asset_variants: {} } }))
  await page.route(/https:\/\/(connect\.facebook\.net|www\.facebook\.com)\/.*/, route => route.fulfill({ status: 204 }))
  await page.route('**/api/v1/public/landing-analytics/events', route => { events.push(route.request().postDataJSON()); return route.fulfill({ status: 202, json: { accepted: true } }) })
  await page.route('**/api/v1/public/landings/water-quality/inquiries', route => {
    const body = route.request().postDataJSON(); inquiries.push(body)
    return fail ? route.fulfill({ status: 503 }) : route.fulfill({ status: 202, json: { accepted: true, request_id: body.request_id } })
  })
  await page.goto('/water-quality')
  await expect.poll(() => events.length).toBe(1)
  await expect(page.getByText('Микита, Івано-Франківськ')).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Політика cookie', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Налаштування cookie', exact: true })).toHaveCount(0)
  for (const name of ['App Store', 'Google Play', 'Telegram', 'Instagram', 'Threads']) {
    const opener = name.includes('Store') || name.includes('Play') ? page.getByRole('link', { name: new RegExp(name) }).first() : page.getByRole('button', { name, exact: true })
    await opener.click()
    const dialog = page.getByRole('dialog', { name: 'Готуємо першу версію' })
    await expect(dialog).toBeVisible()
    await expect(dialog).toContainText('Альфа-версія ще недоступна')
    expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
    await dialog.getByRole('button', { name: 'Закрити', exact: true }).click()
    await expect(opener).toBeFocused()
  }
  await page.getByRole('button', { name: 'Threads', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Готуємо першу версію' })
  await dialog.getByLabel('Ваше запитання (необов’язково)').fill('Чи можу я запропонувати джерело даних?')
  await dialog.getByLabel('Куди сповістити').selectOption('telegram')
  await dialog.getByLabel('Контакт (необов’язково)').fill('@alpha_water_test')
  await dialog.getByRole('button', { name: 'Надіслати', exact: true }).click()
  await expect(dialog.getByRole('alert')).toBeVisible()
  await expect(dialog.getByLabel('Контакт (необов’язково)')).toHaveValue('@alpha_water_test')
  fail = false
  await dialog.getByRole('button', { name: 'Надіслати', exact: true }).click()
  await expect(dialog.getByRole('status')).toContainText('зберегли ваше звернення та контакт')
  expect(inquiries).toHaveLength(2)
  expect(inquiries[0].request_id).toBe(inquiries[1].request_id)
  expect(inquiries[1]).toMatchObject({ source: 'threads', contact_channel: 'telegram', contact: '@alpha_water_test', landing_version_sha256: snapshot.version_sha256 })
  expect(JSON.stringify(events)).not.toContain('alpha_water_test')
  expect(JSON.stringify(events)).not.toContain('запропонувати джерело')
  await dialog.screenshot({ path: info.outputPath('early-access-confirmation.png') })
  await dialog.getByRole('button', { name: 'Закрити', exact: true }).click()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
