# Natal landing block contract

`LandingPageContent` v2 is the only editable copy model. It contains
`template_id`, `language`, and exactly eight blocks:

1. `hero`: eyebrow, title, body, CTA label.
2. `problem`: eyebrow, title, body.
3. `features`: eyebrow, title, one to six title/description items.
4. `steps`: eyebrow, title, two to five title/description items.
5. `proof`: eyebrow, title, up to four source-backed items, honest empty state.
6. `faq`: eyebrow, title, up to six question/answer items.
7. `final_cta`: title, body, CTA label.
8. `lead_form`: one code-owned `form_id`, agent-authored heading and body.

An edit returns one complete block, never a partial patch or full page. Server
code validates the block and replaces only that key.

## Protected fields

The agent may not change Natal assets/tokens/layouts, template ID, exact
Positioning IDs or facts, proof items, honest limitation, CTA destination, form
fields/validation/submit/success behavior, publication target, output path,
credentials, or graph IDs. The form choices are `waitlist`, `contact_request`,
and `community_interest`; their definitions come only from `natal/forms.py`.

## Snapshot rules

Initial population creates snapshot 1 for each template. A successful edit
appends one superseding snapshot and marks only its parent non-current. A failed
edit leaves the current snapshot intact. Publication reads the explicitly
selected current snapshot and digest without another agent turn. Preview forms
are inert; only the published build can submit.
