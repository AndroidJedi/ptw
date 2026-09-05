# Project-scoped Landing Studio

Landing / Лендінг is the third private Owner Console destination. A Landing is
not a public site, publishing workflow, campaign, analytics surface, or lead
collector. It belongs to one Project and starts from one immutable approved
Post version plus its source approved Product Brief.

## Bounded page contract

The sole v1 page template keeps this exact order: Hero, three feature cards,
social proof, a generated visual break, contacts, and three FAQs. The owner can
edit bounded content and theme/layout controls but cannot add HTML, CSS,
scripts, arbitrary sections, or reorder the composition. Hero and visual-break
art are independently generated text-free PNGs; each retains its newest three
digest-checked raw images and supports exact-image enhancement and selection.

Initial AI composition receives the approved Brief, the frozen Post version’s
design snapshot, the live Landing catalog, and Landing-only global/Project
skills. It must not invent social proof or contact endpoints. Owner evidence
and one email, phone, or HTTPS URL are required before approval, together with
both visuals, all three features, and all three FAQs.

## Authority and lifecycle

The first page for a Post version is idempotently reserved. A variant is
available only after the latest sibling has an immutable approved version. A
Landing captures its source Post snapshot at reservation; future Post edits
never synchronize into it.

PostgreSQL stores Landing metadata, workspace files, visual bytes, composition
and visual generation runs, immutable versions, checkpoints, and Landing-only
learning snapshots/proposals with explicit Project, Brief, and Post-version
graph lineage. Loopback provides the
same append-only metadata contract and per-page workspace files. All APIs are
authenticated and Project/page scoped under `/api/v1/landings`; visual bytes are
private and `no-store`. Bare or public Landing endpoints do not exist.

Save and Approve create a Landing-only checkpoint when state changed. Learning
may append Landing global and Project rules, but never alters Post Studio skills
or generation. The bridge retains its four existing JSON modes and existing
text-free media mode; Landing uses its own strict schemas and canonical skills.
