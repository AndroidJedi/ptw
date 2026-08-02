# PTW Design Rules

PTW must feel direct, bold, human, and emotionally immediate.

## Content

- Do not explain what navigation, layout, or context already makes obvious.
- Show primary content directly. Never add preview/detail interactions when
  both surfaces contain the same information.
- Show complete primary content without truncation.
- Supporting copy must answer a real question or enable the next action.
  Otherwise, delete it.
- Empty and error states contain one useful recovery action, not explanatory
  cards.

## Composition

- Creator screens use hot pink `#F4066E` edge to edge, including system bars.
- User-selected colors stay meaningful inside project tiles and public project
  experiences.
- Saturated tiles, previews, selectors, and black controls use a thin 1 px
  white border. Plain form fields do not.
- Avoid generic list tiles, white cards, title/subtitle pairs, and section
  headers unless they provide essential structure.
- Let content create the composition through large typography, meaningful
  color, whitespace, and minimal metadata.
- Images and color must have a purpose. Remove them when they compete with the
  primary content.

## Typography

- Sticker typography identifies the project, the hero state, or the single
  primary action. It is hierarchy, never decoration.
- Use the outlined Lilita One treatment for project goals, CTA labels, hero
  facts, and the first action-sheet choice only.
- Keep supporting copy, messages, proof, metadata, selectors, fields, and
  secondary actions in Roboto.
- Preserve natural capitalization and complete content. Project stickers may
  scale down to fit, but never truncate.
- On images and saturated surfaces, sticker text is white with a hard black
  outline and offset shadow. On black controls, it uses the current accent with
  a thin white outline.

## Interaction

- Project is the creator hub. Do not use persistent tab bars.
- Secondary creator screens use a white Apple-style back chevron.
- A screen has at most one prominent black capsule action. It stays pinned
  while the content scrolls.
- Back controls, inputs, selectors, and tappable content do not count as the
  screen action. A screen may have no capsule when its content is the action.
- When secondary actions are necessary, the single capsule opens a focused
  action sheet. The primary action appears first; no secondary buttons remain
  on the screen.
- Every tap must perform a real action, not merely reveal information that
  could already be visible.
- Navigation, status bars, and backgrounds must feel like one continuous
  surface.
