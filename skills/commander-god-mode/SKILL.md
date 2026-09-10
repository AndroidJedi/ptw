---
name: commander-god-mode
description: Implement owner-directed PTW features, fixes, and system changes through Commander GOD-mode chat, and maintain the relevant development skills. Use for repository-wide Commander development requests in the local or isolated hosted checkout.
---

# Commander GOD Mode

## Scope and context

This is the PTW development agent behind Settings → Commander → GOD mode.
It can change application code, APIs, tabs, Telegram implementation, tests,
documentation, and canonical skills across the repository. A requested carousel
workspace is a feature to implement, not an unsupported Studio template field.
Read the repository entrypoint and only the documentation route relevant to the
request. Existing product scope describes the baseline; the owner's explicit
feature request may extend it. Preserve generic Brief learning and domain lineage.

The runner targets either the local checkout or the isolated hosted development
checkout named by the UI. The hosted checkout contains tracked source only and
is separate from the live deployment checkout and production data. Neither mode
offers deployment, publishing, production database access, Docker control, or
external messaging. Prepare operational changes for review through the normal
operations path; changing this skill never grants those capabilities.

## Complete a chat turn

- Inspect current files and uncommitted changes; conversation history is context,
  not proof that an earlier edit or test still exists. Preserve unrelated edits.
- Implement the requested behavior across the layers it actually requires.
  For a new tab, account for navigation, API, persistence, empty/error states,
  and focused interaction tests. Do not manufacture domain data for a demo.
- Run checks appropriate to the change. For Commander changes, run the repository
  Commander tests/demo and whitespace checks. For web changes, verify unit/build
  and the affected desktop/360px/WebKit flow. Label mocked browser tests honestly.
- Report changes, verification, remaining limitations, and any skill maintenance.
  If essential input is missing, ask one concise question in the reply; the next
  chat message continues the task. Do not turn routine edits into approval steps.
- Python changes require an API restart to take effect. Do not restart the API
  hosting the current chat from its own running turn: that stops the worker before
  it can persist its result. Finish the turn and identify the required restart.

## Maintain GOD-mode skills

Skill maintenance is part of completing work, as explicitly requested by the
owner. After a verified fix, new feature, or owner correction, inspect whether a
reusable decision or diagnostic was learned. Update the narrowest applicable
canonical `skills/<name>/SKILL.md` or its referenced resource in the same change.
For Commander chat behavior and repository-wide development, maintain this skill.
For a specific Studio, Landing, provider, or operations workflow, maintain its
existing skill instead of duplicating that guidance here. Add a new skill only
when a distinct repeated workflow merits it.

Keep lessons actionable: the trigger, the diagnostic or decision that mattered,
and the verification that prevents regression. Correct stale guidance and remove
superseded instructions. A no-op or a run that taught nothing needs no artificial
lesson. Owner preferences apply at the scope the owner specified; one example
does not create a universal product rule.

Canonical files live in the repository; desktop copies must remain symlinks.
After skill edits, run `python3 scripts/verify_ptw_skills.py`. For a new skill,
add its entry to that verifier, add `agents/openai.yaml`, and use the canonical
skill-sync installer to create its link when the execution environment permits.
Do not replace a link with a copied directory. Never store credentials, raw owner
chat, project-specific Brief copy, transient IDs, or release hashes in skills.
Do not rewrite execution permissions, authentication, or deployment authorization
as a learned shortcut. Development skill updates do not create Product Brief,
Post, or Landing learning entities or cross their lesson namespaces.

## Established chat diagnostics

- GOD mode is additive in Settings: keep ChatGPT Authorization visible in local
  and production Settings. The English/Ukrainian language control belongs in
  Settings, not the navigation rails. Test these controls together when changing
  Settings so a mode condition cannot hide an existing owner control.

- An uncertain message POST must retain its request UUID. Reconcile that UUID
  before resubmitting; a new UUID can execute the same code mutation twice.
- Stop and timeout terminate the worker process group. A parent-liveness pipe
  also stops it when the API crashes; marking a database row interrupted alone
  does not stop an orphaned coding process. Restart never replays mutations.
- A missing local control can be a launcher/build-flag mismatch. The local shell
  uses `VITE_LOCAL_APP=true`; backend chat additionally requires
  `PTW_COMMANDER_CHAT_MODE=1`. Hosted Settings always shows the control. Its
  Firebase/App Check routes proxy through Owner Gateway to the private
  `commander-god` service; only that service mounts the isolated checkout.
- Readiness means the CLI and canonical skill are present. It does not prove
  model authorization. A failed execution needs a local Codex sign-in/runtime
  check; never expose raw CLI output or credentials as a diagnostic.
- Hosted credential publication is read-only. Before every turn, copy only the
  published `auth.json` into the runner's private writable state directory and
  point `CODEX_HOME` there. Checking that the source is readable is insufficient:
  the CLI needs a writable runtime home even for ephemeral execution.

- Post publishing is an approved-artifact boundary. Keep renderer/editor CTA
  controls, pending edits, historical PNGs, and learning namespaces unchanged.
  Verify the selected approved digest for preview/export; a website ad's native
  CTA is independent. Load export sources before remote capability checks so
  missing advertising permissions cannot block organic publishing or export.
- Instagram publish timeouts are ambiguous external mutations. Persist the
  request and container, then persist the publish-start flag before the POST.
  Restart/sync must reuse that container without replaying media_publish. Save
  the returned media ID before requesting its permalink. Exercise response loss,
  restart, duplicate input, account changes, and media expiry in regression tests.
