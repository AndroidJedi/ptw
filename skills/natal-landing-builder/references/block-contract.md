# Natal landing block contract

`LandingPageContent` is the only editable page-copy model. It contains a
`template_id`, `language`, and exactly seven independently owned blocks:

1. `hero`: eyebrow, title, body, CTA label.
2. `problem`: eyebrow, title, body.
3. `features`: eyebrow, title, one to six title/description items.
4. `steps`: eyebrow, title, two to five title/description items.
5. `proof`: eyebrow, title, up to four verified proof strings, honest empty
   state.
6. `faq`: eyebrow, title, up to six question/answer items.
7. `final_cta`: title, body, CTA label.

All seven blocks are required even when an item list is empty. An edit operation
returns one complete block matching the selected block schema. It must not
return a partial field patch or a full replacement page. Server code validates
the block and replaces only that key; every other block remains byte-for-byte
equivalent in the page model.

## Protected fields

The agent may change copy only. It may not change:

- template structure or template ID;
- Natal assets, visual tokens, or UI kit;
- Idea Laval run/thesis IDs or source brief facts;
- CTA destination;
- verified proof items;
- publication target, credentials, output path, or graph IDs.

The server reapplies proof and all other protected values after every agent
response. A content instruction is never evidence.

## Snapshot rules

Initial population creates snapshot 1 for each template. A successful edit
creates the next append-only snapshot for that template, links it to its exact
feedback, marks it current, and marks only its parent non-current. A failed edit
records the attempt and leaves the parent current. Edits against a non-current
snapshot are stale conflicts. Publication reads the selected current snapshot
and its content digest without another rewrite.
