import { readdir, readFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const appRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const assetsRoot = join(appRoot, 'dist', 'assets')
const files = (await readdir(assetsRoot)).filter((name) => name.endsWith('.js'))
const bundle = (await Promise.all(files.map((name) => readFile(join(assetsRoot, name), 'utf8')))).join('\n')
const worker = await readFile(join(appRoot, 'dist', 'sw.js'), 'utf8')
const monochromeSources = await Promise.all([
  join(appRoot, 'index.html'),
  join(appRoot, 'public', 'manifest.webmanifest'),
  join(appRoot, 'public', 'ptw.svg'),
  join(appRoot, 'src', 'styles.css'),
].map(async (path) => [path, await readFile(path, 'utf8')]))

const requiredMarkers = {
  'Commander production API origin': 'https://commander.proove-them-wrong.com',
  'Firebase App Check request header': 'X-Firebase-AppCheck',
  'PTW reCAPTCHA Enterprise site key': '6LfFjYstAAAAAJaFuUPZYS9U17vROLcN7Fx6iOQL',
  'Safari-safe Auth persistence': 'ptw-auth-local-storage-v1',
  'Validation Project workspace': 'PROJECT WORKSPACE',
  'one-click Instagram workspace': 'NATAL · ONE FINAL POST',
  'automatic Natal identity': 'Natal branding is applied automatically. Nothing else is required.',
  'Bounded initial stage': 'Creating five directions',
  'Bounded improvement stage': 'Improving the strongest direction',
  'Bounded final stage': 'Final review',
  'Single public explanation': 'WHY THIS DIRECTION',
}

const missing = Object.entries(requiredMarkers)
  .filter(([, marker]) => !bundle.includes(marker))
  .map(([label]) => label)

if (missing.length) {
  throw new Error(`Unsafe Commander web build; missing: ${missing.join(', ')}`)
}

const forbiddenMarkers = {
  'batch UI': 'Ad batch',
  'Studio UI': 'Ad Studio',
  'publication control': 'Publish',
  'campaign control': 'Campaign',
  'Landing UI': 'Landing',
  'manual template controls': 'Template controls',
  'manual brand-kit setup': 'PROJECT BRAND KIT',
  'text-profile chooser': 'Result type',
  'owner task field': 'Describe the one result you need',
}
const exposed = Object.entries(forbiddenMarkers)
  .filter(([, marker]) => bundle.includes(marker))
  .map(([label]) => label)
if (exposed.length) {
  throw new Error(`Unsafe Result web build; forbidden surfaces exposed: ${exposed.join(', ')}`)
}

if (!worker.includes("url.pathname.startsWith('/__/auth/')")) {
  throw new Error('Unsafe Commander service worker; Firebase Auth helper traffic is not bypassed')
}
if (!worker.includes("ptw-result-v1")) {
  throw new Error('Unsafe Result service worker; cache version is stale')
}

const expandHex = (value) => {
  const raw = value.slice(1)
  if (raw.length === 3 || raw.length === 4) return raw.slice(0, 3).split('').map((part) => parseInt(part + part, 16))
  return [raw.slice(0, 2), raw.slice(2, 4), raw.slice(4, 6)].map((part) => parseInt(part, 16))
}
const chromatic = []
for (const [path, source] of monochromeSources) {
  for (const match of source.matchAll(/#[0-9a-fA-F]{3,8}\b/g)) {
    const [red, green, blue] = expandHex(match[0])
    if (red !== green || green !== blue) chromatic.push(`${path}: ${match[0]}`)
  }
  for (const match of source.matchAll(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/g)) {
    const [, red, green, blue] = match.map(Number)
    if (red !== green || green !== blue) chromatic.push(`${path}: ${match[0]}`)
  }
}
if (chromatic.length) {
  throw new Error(`Commander chrome must remain monochrome; found: ${chromatic.join(', ')}`)
}

process.stdout.write('Verified one-click Natal Instagram flow, App Check, Safari Auth, monochrome chrome, and service-worker markers in production build.\n')
