const APPCHECK_DEBUG_TOKEN_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export function validateProductionBackendMode(env: Record<string, string>, command: string) {
  if (env.VITE_PRODUCTION_BACKEND !== 'true') return
  if (command !== 'serve') {
    throw new Error('VITE_PRODUCTION_BACKEND is a dev-server-only mode and must never be included in a production build.')
  }
  if (!APPCHECK_DEBUG_TOKEN_PATTERN.test(env.VITE_APPCHECK_DEBUG_TOKEN || '')) {
    throw new Error(
      'VITE_PRODUCTION_BACKEND requires one registered UUIDv4 VITE_APPCHECK_DEBUG_TOKEN. '
      + 'Keep it in the local environment only; do not allowlist localhost in reCAPTCHA or commit the token.',
    )
  }
}
