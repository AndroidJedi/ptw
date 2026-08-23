# PTW v2 owner-console rules

Status: canonical
Updated: 2026-08-23

## Product and navigation

- Ukrainian is the default chrome; source/output language is explicit per
  project. IDs, source text, logs, and provider errors remain verbatim.
- Primary navigation is Marketing Positioning, Landing, Ads, and Admin. Admin
  contains Jobs plus Docs/System/Terminal.
- Old page locations redirect to Positioning. Old domain APIs do not exist.
- Design first for 360 px and one-hand use, with 44×44 CSS pixel targets, no
  horizontal page overflow, keyboard access, and reduced-motion support.

## Marketing Positioning

- Start from raw idea, country, research language, and output language. Another
  idea or market creates another project.
- Show source UUIDs and assumption markers beside claims. Never hide a failed
  live research or strict-synthesis attempt behind fallback output.
- A correction selects one section and creates a complete immutable revision.
  The existing revision remains active until explicit approval.
- Landing and Ads expose only the active approved revision.

## Landing

- Show exact project/revision IDs and require an HTTPS privacy policy before
  creating the three Natal drafts.
- The editor exposes all eight blocks. Preview uses sandboxed self-contained
  `srcdoc`; forms and CTAs are inert. Mobile 360 px and desktop toggles are
  explicit.
- Proof, privacy, form behavior, source facts, publication target, and IDs are
  protected. A correction replaces only its selected block.
- Publication has one explicit action and consumes the exact current snapshot
  without another rewrite. Show durable failures/retries, publication history,
  lead UUIDs, submitted fields, and notification status.

## Ads and Admin

- Ads shows the two approved Positioning concepts and the literal state
  “Generation and publishing are not implemented.” It exposes no generate,
  campaign, post, image, or publish action.
- Plan and Execute remain visibly distinct and digest-bound. The root terminal
  is labelled break-glass and retains bounded lifetimes.
- The irreversible reset preview names only `ptw_commander.public` and requires
  `RESET PTW PRODUCTION`.

## Trust and caching

- Empty production state is valid. Never seed fake projects, Landings, proof,
  or leads.
- PWA caching is limited to public shell resources. API, preview, lead,
  terminal, and sensitive responses are never cached.
- Do not show invented metrics, proof, testimonials, urgency, scarcity,
  limitations, or competitive facts.
