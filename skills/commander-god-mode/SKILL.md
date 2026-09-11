---
name: commander-god-mode
description: Implement owner-directed PTW features, fixes, and system changes through Commander GOD-mode chat, and maintain the relevant development skills. Use for repository-wide Commander development requests in the local or isolated hosted checkout.
---

# Commander GOD Mode

## Scope and context

This is the PTW development agent behind the dedicated Commander GOD workspace.
It can change application code, APIs, tabs, Telegram implementation, tests,
documentation, and canonical skills across the repository. A requested carousel
workspace is a feature to implement, not an unsupported Studio template field.
Read the repository entrypoint and only the documentation route relevant to the
request. Existing product scope describes the baseline; the owner's explicit
feature request may extend it. Preserve generic Brief learning and domain lineage.

The runner targets either the local checkout or the isolated hosted development
checkout named by the UI. The hosted checkout contains tracked source only and
is separate from the live deployment checkout and production data. The coding
runner never receives publishing, production database, Docker, SSH, GitHub-key,
or external-messaging access. An explicit owner instruction to deploy authorizes
the host-handled `request_deployment` tool without another confirmation. Complete
implementation and checks first; the host durably hands off the result, then the
separate release controller freezes and deploys the candidate. Never use shell
commands to bypass that bounded interface or claim a queued release is live.

Plan uses native collaboration mode in a separate read-only worker without
deployment tools. Build uses native Default mode. Use interactive questions for
clarifications; answers and replies continue the same task. The selected model
and effort are authoritative. Implement plan switches to Build but does not
authorize deployment unless the owner also requests deployment.

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

- Commander has its own navigation destination and no Project selector. Settings
  retains authorization and language. Use a timeline, history drawer and sticky
  composer, with Plan/Build, runtime model/effort choices, Reply, Send and Stop.

- An uncertain message POST must retain its request UUID. Reconcile that UUID
  before resubmitting; a new UUID can execute the same code mutation twice.
- Scope pending deployment UUIDs to their conversation. A disconnected Git push
  is an uncertain outcome, not proof of failure: reconcile the immutable request
  branch before allowing another release. Test a push that succeeds remotely
  while its local transport reports failure.
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
- Hosted Codex runs inside the dedicated container sandbox. Do not nest the
  CLI's Linux `workspace-write` sandbox there: Docker's dropped capabilities
  correctly prevent Bubblewrap from creating its namespace, leaving even Git
  reads unusable. Use Codex's externally-sandboxed execution mode only for the
  hosted target. Retain its read-only root filesystem, isolated checkout/state
  mounts, absent Docker socket and production data, resource limits, and safe
  environment allowlist. Local Commander must retain `workspace-write` with
  shell network disabled.
- Chat-triggered deployment and the one-click Deploy action share a durable
  request UUID. "Implement and deploy" survives clarification, but questions,
  quoted examples, negations and Plan messages never initiate a release. The
  final coding response and handoff must persist before the checkout lock is
  released. All versioned PTW paths are eligible, including workflows, Docker,
  Compose, receiver code and migrations; routine releases preserve data. Resets,
  credential rotation and unrelated systems need specifically scoped requests.
- The candidate branch contains source; the request branch is based on the last
  accepted revision and changes only a bounded manifest. Its trusted workflow
  builds without production credentials; the privileged stage verifies artifacts
  and invokes the restricted receiver. Recovery remains owned by the accepted
  release until application, infrastructure, migrations and Hosting pass.
- A previous successful release does not prove newer edits are live. Match the
  exact candidate, authoritative deployed marker and workflow outcome. Preserve
  per-conversation release links; distinguish rollout failure from bookkeeping
  repair. Never publish the generated `skills/.system` runtime directory.
- App-server threads are ephemeral. Persist sanitized transcript, effective turn
  settings, questions and answers; reconstruct context after restart and retrieve
  archived messages by cursor when needed. Keep Send available for steering and
  reconcile completion races with the original request UUID. Never replay an
  interrupted mutation automatically. Plan has a separate bridge token, not the
  Owner Gateway/release token; its checkout mount must actually reject writes.

- GOD chat image inputs are request-scoped visual context, not repository assets.
  Accept only bounded PNG/JPEG/WebP uploads, decode and normalize them before use,
  strip metadata, and pass only the latest turn's verified temporary files to the
  Codex CLI. Keep image bytes out of Git and chat SQLite, and delete them on every
  terminal outcome, Stop, timeout, launch failure, and service restart. The owner-
  authenticated preview path must verify the normalized digest. Retain only safe
  filename/digest metadata in history, and test that later turns cannot reattach
  pixels from an earlier request.

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
- Public Landing analytics belong to the single `apps/landing-web` shell, not
  immutable Landing snapshots. A Meta Pixel ID is public configuration; keep
  tokens out of the browser. Load the external library and emit `PageView` only
  after an explicit persisted visitor choice, keep the Firebase CSP allowlist
  narrow, and verify both zero pre-consent requests and post-consent loading in
  desktop/mobile browser tests.
