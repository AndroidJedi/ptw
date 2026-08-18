const CACHE = 'ptw-shell-v3'
const SHELL = ['/', '/index.html', '/manifest.webmanifest', '/ptw.svg']

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => Promise.all(SHELL.map(async (path) => {
    const response = await fetch(new Request(path, { cache: 'reload' }))
    if (!response.ok) throw new Error(`Unable to cache ${path}`)
    await cache.put(path, response)
  }))))
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys()
    await Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))
    await self.clients.claim()
    const windows = await self.clients.matchAll({ type: 'window' })
    await Promise.all(windows.map((client) => client.navigate(client.url)))
  })())
})

self.addEventListener('fetch', (event) => {
  const request = event.request
  const url = new URL(request.url)
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return
  if (!['document', 'script', 'style', 'font', 'manifest'].includes(request.destination)) return

  if (request.destination === 'document') {
    event.respondWith((async () => {
      try {
        const response = await fetch(request, { cache: 'no-cache' })
        if (response.ok) await (await caches.open(CACHE)).put(request, response.clone())
        return response
      } catch {
        return (await caches.match(request)) || (await caches.match('/index.html')) || Response.error()
      }
    })())
    return
  }

  event.respondWith(caches.match(request).then((cached) => cached || fetch(request).then((response) => {
    if (response.ok) caches.open(CACHE).then((cache) => cache.put(request, response.clone()))
    return response
  })))
})
