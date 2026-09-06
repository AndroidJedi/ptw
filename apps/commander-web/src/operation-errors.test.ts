import { describe, expect, it } from 'vitest'
import { operationFailureMessage } from './operation-errors'

describe('background operation errors', () => {
  it('turns a bridge failure into an explanation, recovery instruction, and explicit IDs', () => {
    const message = operationFailureMessage({
      operation: 'brief', detail: 'structured bridge request 437 failed',
      code: 'RuntimeError', reference: 'brief-1',
    }, 'uk')

    expect(message).toContain('Не вдалося згенерувати продуктовий бриф.')
    expect(message).toContain('Пояснення: Сервіс ChatGPT/Codex')
    expect(message).toContain('Що робити: У Налаштуваннях')
    expect(message).toContain('code RuntimeError · bridge job 437 · ID brief-1')
    expect(message).not.toContain('structured bridge request')
  })
})
