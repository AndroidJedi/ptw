import { readdir, readFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const appRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const assetsRoot = join(appRoot, 'dist', 'assets')
const files = (await readdir(assetsRoot)).filter((name) => name.endsWith('.js'))
const bundle = (await Promise.all(files.map((name) => readFile(join(assetsRoot, name), 'utf8')))).join('\n')
const worker = await readFile(join(appRoot, 'dist', 'sw.js'), 'utf8')

const requiredMarkers = {
  'Commander production API origin': 'https://commander.proove-them-wrong.com',
  'Firebase App Check request header': 'X-Firebase-AppCheck',
  'PTW reCAPTCHA Enterprise site key': '6LfFjYstAAAAAJaFuUPZYS9U17vROLcN7Fx6iOQL',
  'Safari-safe Auth persistence': 'ptw-auth-local-storage-v1',
}

const missing = Object.entries(requiredMarkers)
  .filter(([, marker]) => !bundle.includes(marker))
  .map(([label]) => label)

if (missing.length) {
  throw new Error(`Unsafe Commander web build; missing: ${missing.join(', ')}`)
}

if (!worker.includes("url.pathname.startsWith('/__/auth/')")) {
  throw new Error('Unsafe Commander service worker; Firebase Auth helper traffic is not bypassed')
}

process.stdout.write('Verified Commander API, App Check, Safari Auth, and service-worker markers in production build.\n')
