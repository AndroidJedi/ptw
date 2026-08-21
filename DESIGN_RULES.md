# PTW React operator-console rules

Status: canonical
Updated: 2026-08-21

## Product language

- Українська is the default operator language. English source text is always
  available behind an explicit “EN” disclosure.
- Raw command output, logs, diffs, IDs, paths, and provider errors remain
  verbatim.
- Labels describe an action or state; do not add explanatory copy where the
  interface already makes the meaning clear.

## Mobile first

- Design first for a 360 px viewport and one-hand use.
- Primary navigation is Overview, Ideas, Branding, Jobs, More at the bottom on
  mobile and a compact left rail on desktop.
- Put the primary action inside thumb reach. Minimum interactive target is
  44x44 CSS pixels.
- Avoid horizontal page scrolling. Large tables become ranked cards or compact
  lists with progressive disclosure.

## Visual identity

- PTW hot pink `#f4066e`, near-black `#09090b`, and white are the core palette.
- Use pink for intent and progress, not for every surface. State colors must
  retain WCAG AA contrast and never communicate by color alone.
- Prefer strong type, whitespace, thin borders, and direct content over generic
  dashboard cards nested inside cards.
- Motion is brief and functional and respects `prefers-reduced-motion`.

## Operational safety

- Plan and Execute are visibly different modes. An approved plan shows its
  immutable digest.
- Destructive actions show an exact preview, verified backup evidence, and a
  typed confirmation.
- The root terminal is always labelled **Break-glass · root**. It displays its
  idle and maximum lifetime and never stores transcript in application state.
- Job state, validation evidence, deployment revision, and failure recovery are
  visible without opening raw logs.

## Creative review

- The image remains the largest review surface. Pin, rectangle, and freehand
  annotations use normalized `[0,1]` coordinates and can be edited without
  changing the immutable artifact.
- Each region has a comment. Overall rating and comment are separate.
- Ten-variant batches keep the sequence visible and advance only after the
  current feedback and producing-context conclusion are persisted.
- Never hide Creative UUID or artifact digest; show shortened values with a
  copy action and the full value in details.

Branding is the owner-friendly exception to showing graph IDs in the primary
flow: direction cards identify a readable name and ordinal, while the gateway
resolves the immutable Creative UUID and digest server-side. Full provenance
remains available in stage and review details.

## Branding

- A candidate leads with the original Idea, recommended thesis, target user,
  evidence quality, and prior Brand Kit state. Optional research context stays
  behind disclosure.
- The primary review flow shows one logo at a time and accepts one required
  text comment. Branding does not show annotation tools, numeric rating,
  palette, type specimens, or raw principles in this path.
- Each primary state has one CTA: save and advance, approve the selected
  direction, recover saved work, or download the finished kit. Run switching,
  provider/cost details, stages, artifacts, and deliberate rerun remain behind
  progressive disclosure.
- Fetch and render only the currently reviewed or selected logo. Do not request
  a second copy for an annotation surface or preload all three full PNGs.
- Do not enable approval until all three current logos have feedback. Direction
  choice and approval are one explicit owner action.
- Always show the trademark/domain-clearance warning. Never translate or vary
  the exact brand name.
- Kit previews and samples default to Ukrainian and must fit at 360 px without
  horizontal page overflow.

## Data presentation

- Collections are bounded and cursor-paginated.
- Trends show units, time range, and empty-state meaning. A score without its
  rubric or generation is ambiguous and must not be shown alone.
- Empty production state is valid. Generation 1 starts only through an explicit
  owner action.
- PWA caching is limited to the static application shell. API responses,
  images, terminal traffic, and sensitive state must never be cached.
