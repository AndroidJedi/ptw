import { HttpsError } from 'firebase-functions/v2/https'
import { beforeUserCreated, beforeUserSignedIn } from 'firebase-functions/v2/identity'

const OWNER_EMAIL = 'sgolovaschuk@gmail.com'

function enforceOwner(event: { data?: { email?: string; emailVerified?: boolean; providerData?: Array<{ providerId?: string }> } }) {
  const user = event.data
  const email = user?.email?.trim().toLowerCase()
  const google = user?.providerData?.some((provider) => provider.providerId === 'google.com')
  if (email !== OWNER_EMAIL || !user?.emailVerified || !google) {
    throw new HttpsError('permission-denied', 'PTW Commander is restricted to its verified owner.')
  }
  return {}
}

export const ownerBeforeCreated = beforeUserCreated({ region: 'europe-west3' }, enforceOwner)
export const ownerBeforeSignedIn = beforeUserSignedIn({ region: 'europe-west3' }, enforceOwner)
