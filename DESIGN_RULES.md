# PTW Design Rules

PTW must feel direct, bold, human, and emotionally immediate.

## Content

- Do not explain what navigation, layout, or context already makes obvious.
- Show primary content directly. A bounded recent-activity preview may open a
  larger collection, but every previewed entry stays complete and untruncated.
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
- A creator's current project is a dedicated page, not a project tile. Its
  image, identity, goal, and deadline form one full-bleed hero.
- Use borderless editorial sections, direct response typography, image bands,
  and thin dividers for ongoing content. Do not package updates or social
  activity into generic cards.
- Hero social signals expose real stored activity through compact text and
  custom indicators. They are information, not another card or button.
- Prototype proof imagery must be visually distinct from its project hero.

## Typography

- Sticker typography identifies the project, a hero state, or the first
  action-sheet choice. It is hierarchy, never decoration.
- Use the outlined Lilita One treatment for project goals, hero facts, and the
  first action-sheet choice only.
- CTA labels use a centered white sticker wordmark with a crisp black contour,
  a small hot-pink hard shadow, and no leading icon.
- Keep supporting copy, messages, proof, metadata, selectors, fields, and
  secondary actions in Roboto.
- Preserve natural capitalization and complete content. Project stickers may
  scale down to fit, but never truncate.
- On images and saturated surfaces, sticker text is white with a hard black
  outline and offset shadow. On black controls, it uses the current accent with
  a thin white outline.
- Reserve enough inset around sticker text for its outline and offset shadow;
  the visible mark must never touch or clip against a screen edge.

## Interaction

- Project is the creator hub. Do not use persistent tab bars.
- Other creators appear in an immersive full-width activity stream, not a
  discovery grid or another navigation shell.
- Secondary creator screens use a white Apple-style back chevron.
- A screen has at most one prominent black capsule action. It stays pinned
  while the content scrolls.
- Back controls, inputs, selectors, and tappable content do not count as the
  screen action. A screen may have no capsule when its content is the action.
- Reserve small, minimal outlined icons for meaningful navigation and
  metadata. Primary CTA capsules remain icon-free.
- When secondary actions are necessary, the single capsule opens a focused
  action sheet. The primary action appears first; no secondary buttons remain
  on the screen.
- Every tap must perform a real action, not merely reveal information that
  could already be visible.
- Important navigation destinations remain available even when their content
  is empty.
- Do not promote the same destination with both a navigation control and a
  separate content preview.
- Organize mixed activity with typography and thin separators, not cards or
  section containers.
- Merge proofs and reactions into one chronological stream. Do not separate
  related activity into type-based sections when time is the useful context.
- Navigation, status bars, and backgrounds must feel like one continuous
  surface.
