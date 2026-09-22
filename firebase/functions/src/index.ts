import { HttpsError } from 'firebase-functions/v2/https'
import { beforeUserCreated, beforeUserSignedIn } from 'firebase-functions/v2/identity'

const OWNER_EMAILS = new Set([
  'sgolovaschuk@gmail.com',
  'svitlanabilan23@gmail.com',
  'befree833@gmail.com',
])

function enforceOwner(event: { data?: { email?: string; emailVerified?: boolean; providerData?: Array<{ providerId?: string }> } }) {
  const user = event.data
  const email = user?.email?.trim().toLowerCase()
  const google = user?.providerData?.some((provider) => provider.providerId === 'google.com')
  if (!email || !OWNER_EMAILS.has(email) || !user?.emailVerified || !google) {
    throw new HttpsError('permission-denied', 'PTW Commander is restricted to verified approved accounts.')
  }
  return {}
}

export const ownerBeforeCreated = beforeUserCreated({ region: 'europe-west3' }, enforceOwner)
export const ownerBeforeSignedIn = beforeUserSignedIn({ region: 'europe-west3' }, enforceOwner)
