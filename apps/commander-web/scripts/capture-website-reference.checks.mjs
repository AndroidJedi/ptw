import assert from 'node:assert/strict'
import { test } from 'node:test'
import { publicAddress, publicUrl } from './capture-website-reference.mjs'

test('capture rejects local, reserved, metadata and multicast addresses', () => {
  for (const ip of ['127.0.0.1', '10.0.0.2', '172.31.0.1', '192.168.1.1', '169.254.169.254', '100.64.0.1', '0.0.0.0', '224.0.0.1', '198.19.0.1', '192.0.2.1', '198.51.100.2', '203.0.113.4', '::1', '999.1.1.1']) assert.equal(publicAddress(ip), false, ip)
  assert.equal(publicAddress('93.184.216.34'), true)
})
test('each fetched URL and redirect must remain public HTTPS without credentials or alternate ports', () => {
  for (const url of ['http://example.com', 'https://user:password@example.com', 'https://example.com:8080', 'https://localhost', 'file:///etc/passwd', 'https://[::1]']) assert.throws(() => publicUrl(url))
  assert.equal(publicUrl('https://example.com/page?theme=green').hostname, 'example.com')
})
