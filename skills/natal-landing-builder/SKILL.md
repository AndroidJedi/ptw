---
name: natal-landing-builder
description: Build and iteratively revise fast, dependency-free Natal landing pages from a structured brief or completed PTW Idea Laval evaluation. Use for selecting or repeatedly switching among the Natal product, community, and waitlist templates, applying owner feedback, preparing landing copy, generating a previewable static build, updating an existing Natal landing, or running the authenticated PTW Firebase landing workflow. Do not use for unrelated brands or arbitrary publishing targets.
---

# Natal Landing Builder

Create a truthful, previewable Natal site while keeping the brand identity and
template system canonical under `natal/`.

## Build contract

1. Read `natal/README.md`, `natal/brand/style-guide.md`, and the manifest for
   the selected template. Do not rename Natal, edit canonical logo/icon files,
   or introduce a second visual system.
2. When the source is a completed Idea Laval evaluation, retain its Laval run
   and thesis IDs in `brief.source`. Use evaluated target user, problem, value
   moment, mechanisms, and loop steps. Do not turn assumptions into proof.
3. Select `product` for software/service and feature-led conversion,
   `community` for events or group participation, and `waitlist` for an early
   concept or lean demand test. When Commander supplied a template, respect it.
4. Follow `natal/brief.schema.json` and populate the version-1 brief fields:
   `business_idea`, `target_audience`,
   `pain`, `promise`, one to six `key_features`, two to five `steps`, optional
   verified `proof_points`, optional `faq`, `cta`, `language`, and `source`.
5. Never invent testimonials, customer counts, conversion metrics, prices,
   deadlines, scarcity, launch availability, or integrations. If proof is not
   supplied, keep the builder's explicit no-proof state.
6. Generate only within the output path named by the approved task. A normal
   command-line or agent build is local static output, not authorization to
   deploy, publish, spend, contact users, or change another app.
7. Automatic publication is allowed only for the owner-authenticated
   `POST /api/v1/landings/builds` workflow. The server must resolve the
   dedicated Firebase site and source IDs; never accept a caller-supplied site,
   project, credential, output path, or arbitrary file tree. Persist the build
   and its `derived_from` Idea source before starting, and expose only its
   landing-domain status and retry controls.
8. Publish only allowlisted static HTML, CSS, JavaScript, SVG, and PNG files.
   Keep `brief.json`, `build.json`, credentials, source IDs, and other internal
   metadata private. Stop before the Firebase release if the PTW emergency stop
   becomes active.
9. Treat each owner submission as an immutable landing revision. `product`,
   `community`, and `waitlist` may be applied repeatedly in any order; a
   recommendation is never a lock. Link a revision to its published parent with
   `supersedes` and retain every earlier public URL.
10. Treat review comments as append-only skill memory. Persist a
    `HumanFeedback` entity that `evaluates` the exact published Landing and a
    zero-delta `WeightUpdate` that `adjusts` the reviewed template component.
    Do not rewrite an earlier comment, landing, or artifact. PostgreSQL is the
    runtime authority; do not make browser feedback dirty the Git checkout by
    appending it to `SKILL.md`.
11. Before a new revision starts, snapshot the latest 100 feedback IDs for that
    Idea evaluation in chronological order; retain older feedback as immutable
    graph history. A fresh `natal_landing_revision` builder-agent turn
    receives the current brief, target template, this skill contract, and that
    exact memory. Feedback is instruction, not factual proof. Keep source IDs,
    verified proof, and CTA destination server-owned, and persist the bounded
    application summary plus fresh invocation provenance.

## Generate and verify

Store the brief as JSON outside the canonical `natal/` kit, then run:

```sh
python3 -m natal.builder \
  --template <product|community|waitlist> \
  --brief <brief.json> \
  --output <approved-output-directory>
```

The builder validates copy bounds and CTA schemes, checks canonical asset
digests, emits source IDs in `brief.json` and `build.json`, and refuses to
overwrite a non-empty directory. Use `--overwrite` only when the approved task
explicitly identifies that existing generated directory.

Preview the generated `index.html` at 360 px and desktop widths. Confirm the
Natal name/logo, CTA destination, no horizontal overflow, no unfilled template
tokens, and no unsupported claims. Run:

```sh
python3 -m unittest discover -s tests/commander -p 'test_natal_builder.py' -v
git diff --check
```

For the authenticated iterative workflow, also verify that one request creates
one idempotent PostgreSQL revision, starts it immediately, passes through
`revising`, reaches `published`, returns the exact Firebase URL, survives an
Owner Gateway restart, and appears only in that Idea's Landing history. Record
feedback on a published revision, switch to a different template, then reapply
an earlier template; require each new build to have an increasing revision
number, the intended parent, and the exact captured feedback IDs. Confirm the
public URL serves the selected brief and that `/brief.json` and `/build.json`
are not published. A builder-agent, build, or Firebase failure must end in a
durable `failed` state with a safe retry action; it must never look successful,
discard feedback, or redirect the owner to global Jobs.
