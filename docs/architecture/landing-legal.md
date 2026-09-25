# Shared Landing terms and policies

Status: implemented locally; not deployed or legally finalised.

The shared renderer links every Project Landing and App Showcase footer to
`/legal/terms`, `/legal/privacy` and `/legal/cookies`, with `?lang=uk|en`.
The public shell serves these exact routes before Project lookup. They do not
reserve Project slugs, use authenticated APIs, load remote fonts, or emit
analytics/Meta requests. Unknown nested paths retain the visual 404. Private
Studio/gallery links use the canonical public origin; the public renderer uses
same-origin links. Existing explicit privacy/terms URLs take precedence.

This is shared website policy content, not a rewrite of an immutable template,
Landing content record, approval or publication. Empty stored URL fields remain
empty. New preview bundles change preview-cache identity through the existing
renderer contract. Legal wording is not generated from a Product Brief and
composition/Manual Agent must still preserve contact and legal endpoints.

## Documents and operator facts

`apps/landing-web/src/legal/documents.ts` contains original Ukrainian/English
website terms, privacy and cookie notices. The terms include contract formation,
per-offer disclosures, payments/subscriptions, cancellation and statutory
remedies, intellectual property, reasonable suspension, liability carve-outs,
disputes and prospective changes. They do not impose acceptance by browsing,
universal no-refund rules, a blanket liability cap, forced arbitration, or a
fictional choice of governing law. Browsing does not create a paid contract.

`apps/landing-web/src/legal/profile.json` separates the operator and operational
facts from reusable wording. It intentionally starts incomplete and unreviewed.
Every document therefore displays **Draft for review**, missing facts and no
effective date. Setting `reviewed` alone does not remove that status: identity,
address, registration, establishment, markets, both-language retention and
transfer disclosures, representative/DPO applicability, and an effective date
must also be supplied. Completeness is a presentation check, not a certification
of legal adequacy. No browser or API can mark this file reviewed.

Reference inspected: the sibling `natal/sesh/terms.html` and `privacy.html`.
Those are paid-meetup documents with specific prices, group sizes, Telegram
workflows and Firebase Analytics. Their operator name is evidence to confirm,
not proof of the current Natal operator. No price, transaction condition,
assumed registered address, Google Analytics use or broad consent was copied.
Existing Natal email/phone come from the canonical contact asset.

Before treating the documents as final, confirm the legal operator and public
business address/registration details, actual target countries, processor roles,
hosting/email/logging providers, their countries and transfer mechanisms,
retention/deletion and backup schedules, privacy-request handling and any
representative/DPO requirements. The code has a 90-day raw-event purge in the
Analytics synchronization path; that alone does not establish a guaranteed
90-day maximum across scheduling, logs, aggregates and backups. The public draft
does not claim that it does. Have qualified counsel review the actual operation
and applicable jurisdictions. Do not represent this framework as universally
enforceable or suitable for every future business without adaptation.

## Future business modules

The common website baseline remains reusable. A future service needs the
following actual offer details and product behaviour before taking orders:

| Business | Additional terms and implementation |
| --- | --- |
| Physical goods | Seller identity, full price/taxes/shipping, delivery, return address/costs, withdrawal instructions/form, conformity remedies, safety obligations. |
| Bookings, events, services | Scope, provider, location/date, confirmation, rescheduling, cancellation, no-show rules and any lawful dated-service exceptions. |
| Digital products/subscriptions | Functionality, compatibility, licence, updates, billing/renewal/trial conversion, accessible cancellation, remedies and separate immediate-performance consent where needed. |
| Marketplace or third-party supply | Which party contracts, trader status, responsibility allocation, ranking/fees, complaints and platform-specific duties. |
| B2B, AI or regulated services | Negotiated commercial terms, data roles/DPA, confidentiality, output/IP and human-review rules, licensing, sector and safeguarding requirements. |

Use a reviewed service-specific privacy/terms URL in the existing owner fields
when appropriate. A new collector, SDK, vendor, purpose or special-category data
requires a truthful privacy supplement and technical controls before activation.
If a future EU online transaction has a statutory withdrawal right, assess and
implement the applicable online withdrawal function; an email address buried
in generic terms is not a substitute. No checkout, account, payment, acceptance
ledger, refund workflow or online withdrawal function is introduced by this work.

## Consent behaviour

The public shell gives separate unchecked choices for first-party Natal
measurement and Meta advertising. Reject optional and Allow all have equal
presentation; Save preferences preserves independent choices. Viewing a page or
following a legal link does not consent. First-party events are now also opt-in:
reports count consenting visitors and should not be interpreted as all traffic.
The backend event schema and graph authority are unchanged.

`natal_privacy_preferences_v2` stores the choices, version and timestamp locally
for at most 180 days of consent validity. Legacy Meta-only consent, malformed,
future-dated and expired records grant nothing. Storage failures retain the
current in-memory decision; cross-tab changes and long-lived expiry are handled.
Cookie settings remains available on every public page and within privacy/cookie
documents. Withdrawal stops application events, issues Meta consent revocation,
removes queued PageViews and deletes accessible host/parent-domain `_fbp`/`_fbc`
cookies. Third-party-domain cookies and already transmitted records cannot be
erased by this code. Meta automatic configuration is disabled. New vendors or
purposes require a new consent revision; editing policy copy is not fresh consent.

These are browser request controls, not proof that Meta's remote processing or
the operator's entire business complies with every privacy law. Initial and
withdrawal behaviour is tested with intercepted provider requests, not a live
advertising account. No production data or publication changes are needed.

## Research and limits

Primary sources checked 2026-09-25:

- [ICO: information to provide](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/the-right-to-be-informed/what-privacy-information-should-we-provide/): identity, purposes, grounds, recipients, retention, transfers and rights. ICO flags ongoing guidance updates following the Data (Use and Access) Act.
- [ICO: managing consent](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guidance-on-the-use-of-storage-and-access-technologies/how-do-we-manage-consent-in-practice/): meaningful refusal and accessible withdrawal.
- [European Commission: individual data rights](https://commission.europa.eu/law/law-topic/data-protection/information-individuals_en) and [handling requests](https://commission.europa.eu/law/law-topic/data-protection/information-business-and-organisations/dealing-requests-individuals_en).
- [Your Europe: unfair terms](https://europa.eu/youreurope/citizens/consumers/unfair-treatment/unfair-contract-terms/index_en.htm) and [shopping rights](https://europa.eu/youreurope/citizens/consumers/shopping/shopping-consumer-rights/index_en.htm).
- [Directive (EU) 2023/2673](https://eur-lex.europa.eu/legal-content/en/ALL/?uri=CELEX%3A32023L2673) and the [Commission's Consumer Rights Directive page](https://commission.europa.eu/law/law-topic/consumer-protection-law/consumer-contract-law/consumer-rights-directive_en): online withdrawal changes apply from 19 June 2026, subject to relevant national implementation and scope.
- [Ukraine personal-data law](https://zakon.rada.gov.ua/go/2297-17) and [consumer-protection law](https://zakon.rada.gov.ua/laws/show/1023-12): official indexed excerpts were available; direct Rada fetches returned 403. Do not infer a complete current Ukrainian-law review from those excerpts, especially the commencement/transition of Law 3153-IX.
- [Meta's official GTM template](https://github.com/facebook/GoogleTagManager-WebTemplate-For-FacebookPixel/blob/main/template.tpl): runtime consent command behaviour. The public Meta privacy/cookie pages redirected to login, so no fixed third-party cookie lifetime is asserted.

## Verification

Run both web unit suites/builds, public browser tests on 1280/768/360px and
iPhone WebKit, and affected Owner Landing/Templates browser flows. Verify direct
links, both languages, visible incomplete-profile status, explicit URL overrides,
empty-URL defaults with/without the marketing footer, responsive wrapping,
no optional requests before consent, purpose separation, withdrawal/reload,
old/invalid/expired consent, blocked storage and cross-tab changes. Keep these
as browser/UI checks with mocked snapshots/providers, not production end-to-end
legal or payment verification.
