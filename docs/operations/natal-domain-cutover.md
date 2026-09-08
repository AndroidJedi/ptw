# Natal public-domain cutover

This checklist transfers `natal-service.com` from the legacy
`natal-dashboard-dev` Firebase Hosting site to `natal-landings-86123`. It is a
separate external-state operation after a successful in-place PTW release; the
deployment confirmation does not authorize guessing Firebase or GoDaddy DNS
values.

## Preconditions

1. Verify `https://natal-landings-86123.web.app` with
   `scripts/audit_public_landing.sh` and exercise `/`, `/ai/<slug>`,
   `/la/<slug>`, and `/wa/<slug>` against a published test Project.
2. Run `scripts/archive_natal_dashboard.sh` and retain the reported
   `.local/archives/natal-dashboard-dev/<timestamp>/` directory, including its
   `SHA256SUMS` manifest.
3. Export or screenshot the current Firebase custom-domain state and the full
   GoDaddy DNS zone. Record the existing apex A, Firebase ownership TXT, SPF,
   MX, and `www` records without printing any credentials.

## Transfer

1. In Firebase Hosting, start Quick Setup for `natal-service.com` on the
   `natal-landings-86123` site. Remove or transfer the domain from
   `natal-dashboard-dev` only when Firebase requests it.
2. At GoDaddy, replace only the Firebase ownership TXT record with the exact
   value Firebase supplies. Preserve every SPF and MX record. Keep the existing
   apex Firebase A record unless Firebase explicitly supplies a replacement.
3. Add `www.natal-service.com` to the new site and configure Firebase's
   permanent redirect to `https://natal-service.com`. Apply only the DNS values
   Firebase displays for `www`; do not reuse an inferred target.
4. Treat `Pending` as an expected state for up to 24 hours. Do not oscillate
   records or reattach the domain to both Hosting sites.

## Acceptance and rollback boundary

Verify valid TLS at the apex and `www`, an HTTP permanent redirect from `www`
to the apex, the English umbrella at `/`, all three lane deep links, exact
public API CORS, `404` from unknown/unpublished public API paths, rejection of
unauthenticated private API calls, and Owner Console health. Run
`scripts/audit_public_landing.sh https://natal-service.com` after the certificate
is active.

The old Hosting site remains intact during the 24-hour soak. Disabling
`natal-dashboard-dev` requires separate retirement authorization after the soak;
never delete it as part of this cutover. If ownership or TLS cannot converge,
stop changing DNS, preserve the captured zone, and follow Firebase's displayed
rollback/reattach instructions using the recorded values.
