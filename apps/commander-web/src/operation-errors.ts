import type { Language } from './i18n'

function compact(value: string | null | undefined): string {
  return String(value || '').replace(/[\u0000-\u001f\u007f]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 300)
}

export function operationFailureMessage({
  operation, detail, code, reference,
}: {
  operation: 'brief' | 'studio' | 'phone_image' | 'landing' | 'learning'
  detail?: string | null
  code?: string | null
  reference?: string | null
}, language: Language): string {
  const uk = language === 'uk'
  const bridgeJob = compact(detail).match(/structured bridge request (\d+) failed/i)?.[1]
  const labels = {
    brief: uk ? 'Не вдалося згенерувати продуктовий бриф.' : 'The Product Brief could not be generated.',
    studio: uk ? 'Не вдалося створити креатив.' : 'The creative could not be composed.',
    phone_image: uk ? 'Не вдалося згенерувати зображення.' : 'The image could not be generated.',
    landing: uk ? 'Не вдалося створити лендінг.' : 'The Landing could not be generated.',
    learning: uk ? 'Не вдалося завершити навчання.' : 'Learning could not be completed.',
  }
  const explanation = bridgeJob
    ? (uk
        ? 'Сервіс ChatGPT/Codex не завершив структурований запит. Ваші вхідні дані та проєкт збережено.'
        : 'The ChatGPT/Codex service did not complete the structured request. Your input and Project remain saved.')
    : (uk
        ? 'Фонова операція завершилася помилкою, але вже збережені дані не видалено.'
        : 'The background operation failed, but previously saved data was not deleted.')
  const instruction = bridgeJob
    ? (uk
        ? 'У Налаштуваннях перевірте статус «Авторизовано й перевірено», поверніться сюди та натисніть «Повторити».'
        : 'In Settings, confirm “Authorized and verified”, return here, and select Retry.')
    : (uk ? 'Оновіть екран, перевірте поточний стан і натисніть «Повторити».' : 'Refresh the screen, review the current state, and select Retry.')
  const technical = [code ? `code ${compact(code)}` : '', bridgeJob ? `bridge job ${bridgeJob}` : '', reference ? `ID ${compact(reference)}` : ''].filter(Boolean).join(' · ') || (uk ? 'немає' : 'none')
  return [
    labels[operation],
    `${uk ? 'Пояснення' : 'Explanation'}: ${explanation}`,
    `${uk ? 'Що робити' : 'What to do'}: ${instruction}`,
    `${uk ? 'Технічні дані' : 'Technical details'}: ${technical}.`,
  ].join('\n')
}
