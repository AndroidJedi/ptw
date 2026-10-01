# Local identity-led car-sharing review

Owner-directed local revision, 2026-09-30. Input for both real generations was
exactly `car sharing`, with Identity-led, `gpt-6-astra` / `xhigh`. Ukrainian and
English runs are independent hypotheses, not translations or a controlled
comparison between languages. No approval, publication or performance learning.

The reported output merely restated occasional access without ownership. Its
consultation came from a generalized mentoring-call lesson, reinforced by a
validator requiring promotional keywords. Updating instructions alone initially
failed twice because the provider's natural next step did not pass that
validator. V2 now accepts a bounded, nonempty offer without those keywords;
language, fabricated-proof and shape checks remain enforced. V1 keeps its
historical promotion contract. The failed trial remains in private local storage.

| Field | Ukrainian run | English run |
| --- | --- | --- |
| Promise | Зберіть друзів на вихідний виїзд без потреби мати власне авто. | Be there for Sunday lunch without owning a car. |
| Identity | Я збираю друзів і перетворюю задум на спільну поїздку. | Someone who makes time to visit family. |
| Category | Авто для вихідного разом. | A car for time around the family table. |
| Offer | Запитайте про доступність авто та умови користування для вашого наступного виїзду з друзями. | Ask about a shared car for your next Sunday family visit. |
| CTA | Запитати про авто для виїзду | Ask about your Sunday trip |

Both selected a recognizable human occasion and made it visible in the main
promise, audience, benefits and offer. Temporary access to a car supports the
emotional premise. Neither invented a free consultation, discount, luxury fleet
or guaranteed availability. The English run chose family visits; the Ukrainian
run chose initiating an outing with friends. These are plausible positioning
hypotheses, not established customer research or evidence that the headlines
convert. The wording remains restrained; owners can explicitly correct it toward
a bolder tone. These checks generated Briefs, not new Post/Landing artwork.

Receipts and complete copy:

- `.local/car-sharing-identity-v2/brief.json` and `review.md` (Ukrainian).
- `.local/car-sharing-identity-en/brief.json` and `review.md` (English).
- `.local/car-sharing-identity/` preserves the failed pre-validator-fix attempt.

Reproduce using `scripts/try_identity_brief.py`, described in the
[Product Brief route](simplified-validation-pipeline.md). Use a fresh output
directory for a new policy experiment; existing receipts are deliberately reused.

Local browser checks also exercised the real loopback API and an existing
authored Post on desktop, 360px and WebKit: explicit Project selection, no history
fetch before opening the inspector, successful digest-checked history reads,
and a fresh authoritative preview. Screenshots are under
`.local/identity-ui-check/`. This verifies local behavior; the owner's screenshot
does not establish the precise cause of the production transport failure, and
this revision has not been deployed.

## Punchier copy and downstream identity, second owner review

The owner rejected the explanatory headline and asked for recognizable weekend
car imagery and a valued self-image. Policy revision 3 aims for a 3–7-word hook,
puts explanation in supporting fields, and conveys resourcefulness through the
choice/action rather than generic intelligence praise. Post, Landing, Manual
Agent, image and Natal skills now interpret that same handoff explicitly.
No new schema, agent or runtime inference stage was added.

A real Ukrainian Brief used the owner's more specific weekend/friends direction,
not the earlier two-word-only input. It returned “Збери друзів на вихідні за
містом.” (six words) and the identity “Винахідливий друг, який втілює спільні
плани й цінує час разом.” Natal binding carried the hook to both surfaces, with
“Час із друзями вже дорогою.” as Post support. The image direction called for a
recognizable car, friends loading their bags and a weekend setting. Generated
desktop artwork expresses that scene. This is evidence of a coherent handoff,
not a guarantee of artistic distinctiveness or measured audience response.

The seed template's narrow mobile crop initially hid the car silhouette and
friends. The trial retains those first renders and exercises the existing Natal
bounded visual-review contract using the same raw art. Reviewing complete subjects
includes retaining the product and identity-bearing action, not merely filling
an image box. Framing/layout can change; semantic image defects never trigger
an automatic image regeneration.

Private receipts: `.local/car-sharing-aura-brief/` and
`.local/car-sharing-aura-package/`. Reproduce downstream copy with:

```sh
.venv/bin/python scripts/run_marketing_trial.py \
  --brief-file .local/car-sharing-aura-brief/brief.json \
  --output-dir .local/car-sharing-aura-package
.venv/bin/python scripts/run_marketing_trial.py \
  --output-dir .local/car-sharing-aura-package --artwork-only
.venv/bin/python scripts/run_marketing_trial.py \
  --output-dir .local/car-sharing-aura-package --review-only
```

These are Natal concept drafts in a simple native template pair, not approved
Project Post/Landing versions. Source Brief IDs/digests, provider receipts and
original pixels remain available. Neither the first renders nor copy length alone
proves that the desired mood works; inspect the actual final crop on each surface.

The real visual reviewer identified the missing friends/car in the mobile crop,
changed both image slots to `contain`, then reduced the mobile spacing through
four bounded `mobile_box` edits. A third inspection returned ready with no edits
or issues. Manual inspection confirms the complete group, bags and recognizable
car survive on mobile. The fixture still has unused space below its content
because changing canvas height is outside this review contract. Reviewed PNGs
are `*-reviewed.png`; the raw image was generated once and retained throughout.
These bounded passes are the existing Natal review stage, not a new runtime agent.

The six-word first headline still felt literal. The final revision narrows the
writing target to 3–5 words, leaving the original test receipts intact. This is
an editorial target, not a word-count validator or a universal slogan.
The fresh revision-4 run returned “Збирай друзів. Рушайте на вихідні.” (five
words). Its complete immutable receipt is in `.local/car-sharing-punchy-brief/`.
The package gallery preserves the earlier six-word trial and its visual-review
history; it is not relabelled as output from the newer Brief.

## Explicit brand section, third owner review

The owner correctly distinguished a use occasion from brand identity. V3 now
stores and displays `brand_identity` as its own section in both Brief views.
The video supplies strategic mechanics, not measured business evidence:

| Mechanic | Explicit Brief field |
| --- | --- |
| A brand point of view beyond the ordinary function | belief |
| The meaning of choosing the product; desired self-image | identity_signal, values |
| A specific convention or conflicting desire | cultural_tension |
| A meaningful new context for an ordinary product | category_reframe |
| The feeling about oneself that the choice supports | emotional_reward |
| Useful distinctions that help the customer feel capable | competence_cue |
| A real functional reason supporting the emotion | proof_anchor |
| Fitting voice and recurring recognizable symbols; elevated diction is optional | voice, visual_world |
| Participation through a proposed repeatable behaviour | ritual, optional |

The section is one coherent hypothesis. Rebellion, luxury, a common enemy,
community and pricing changes are not mandatory. No unsupported revenue claims,
demographic stereotypes, manufactured anxiety or health promises are imported.
V1/V2 remain unchanged; only new generation or an explicit correction adds V3.

Two real Ukrainian generations used `gpt-6-astra` / `xhigh`:

- Sparse `car sharing`: “До рідних на обід.” Brand belief: closeness grows from
  ordinary meetings at a shared table; the tension is postponing visits until
  holidays. Receipts: `.local/car-sharing-brand-v3/`.
- Owner's weekend/friends direction: “Вихідні з друзями починаєш ти.” Values are
  initiative, friendship and thoughtful choice; the convention is “треба якось
  зібратися” that never becomes a plan. The competence cue is people, bags and
  route first, car second. Voice is warm and decisive; visual direction is
  friends loading bags into a recognizable car in morning light. Receipts:
  `.local/car-sharing-weekend-brand-v3/`.

Real Natal binding used that exact second Brief. Post/Landing retain its short
promise, and Landing support reads “Врахуй пасажирів, багаж і маршрут.” Image
generation receives the complete original brand section as well as positioning,
not merely a summary written by another agent. The generated scene shows three
friends loading bags into a recognizable car. As in the previous seed-template
trial, the first tall mobile crop hides some friends and the vehicle. This is a
layout failure, not evidence that the source identity was absent; preserve the
original and inspect the existing bounded visual-review correction.

The completed review changed Landing image fitting to `contain`, then tightened
four mobile layout boxes. A third inspection returned ready with no issues.
Manual inspection confirms the complete friends/car/bags scene remains readable.
The seed template still has unused bottom canvas space; this is a private brand
handoff trial, not a finished Landing design. Original art/renders are retained.

Reproduce with fresh private output folders:

```sh
.venv/bin/python scripts/try_identity_brief.py --idea 'car sharing' \
  --output-dir .local/my-brand-trial
.venv/bin/python scripts/run_marketing_trial.py \
  --brief-file .local/my-brand-trial/brief.json --output-dir .local/my-brand-package
.venv/bin/python scripts/run_marketing_trial.py \
  --output-dir .local/my-brand-package --artwork-only
.venv/bin/python scripts/run_marketing_trial.py \
  --output-dir .local/my-brand-package --review-only
```

The current package is `.local/car-sharing-brand-package-v3/index.html`. Its
source IDs, policy snapshot, full copy, image provenance and review receipts are
retained. Test the UI at `http://127.0.0.1:5173/?e2e=1`: select a Project, choose
Identity-led and generate a new Brief, or correct an existing one with “Develop
the brand identity.” Natal Create uses the same section and replacement workflow.
Existing Project replacements need fresh approval before Post generation.

Verification: 483 backend tests in the built image and 49 final focused checks,
147 frontend tests/build, 42 browser cases across desktop/360px/WebKit (including
actual Ukrainian section wrapping and V2 history), disposable PostgreSQL
migration/immutability/restart checks, Commander tests/demo and skill validation.
Browser inference is scripted; the private examples above use real inference.
The full Ukrainian Manual Agent envelope revealed a 20,933-byte input; its
ceiling increased from 20 to 22 KiB (total 32 to 34 KiB), retaining exact source
data and the existing 1 KiB correction reserve. Other provider ceilings stay put.
