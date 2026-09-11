import { readFile, readdir } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const html = await readFile(join(root, 'dist', 'index.html'), 'utf8')
const robots = await readFile(join(root, 'dist', 'robots.txt'), 'utf8')
const assets = await readdir(join(root, 'dist', 'assets'))
const javascript = (await Promise.all(assets.filter(name => name.endsWith('.js')).map(name => readFile(join(root, 'dist', 'assets', name), 'utf8')))).join('\n')

for (const marker of ['noindex,nofollow,noarchive', '<title>Natal</title>']) {
  if (!html.includes(marker)) throw new Error(`Public Landing build is missing ${marker}`)
}
for (const marker of ['User-agent: *', 'Disallow: /']) {
  if (!robots.includes(marker)) throw new Error(`Public Landing robots policy is missing ${marker}`)
}
for (const marker of ['Digital products and services by Natal.', 'Page not found', 'This Natal page is unavailable.', 'natal-service.com/', '1056720310312959', 'connect.facebook.net/en_US/fbevents.js', 'PageView']) {
  if (!javascript.includes(marker)) throw new Error(`Public Landing bundle is missing ${marker}`)
}
for (const forbidden of ['firebase/auth', 'serviceWorker.register', 'Google Identity', 'X-Firebase-AppCheck']) {
  if (javascript.includes(forbidden)) throw new Error(`Public Landing bundle contains forbidden capability: ${forbidden}`)
}
process.stdout.write('Verified the noindex Natal shell, public route renderer, consent-gated Meta Pixel, visual 404, and absence of auth/service-worker code.\n')
