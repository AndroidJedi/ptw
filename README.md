# PTW — web-only Commander

PTW is an owner-operated system for building a company with a plausible path to
a USD 20M sale or valuation within 36 months. The system is designed to be
managed remotely from idea discovery through implementation and deployment,
with explicit policy gates for destructive operations.

The only product UI is the mobile-first React PWA in `apps/commander-web`.
Firebase supplies Google authentication and App Check; it does not store domain
data. PostgreSQL remains the runtime authority, Git owns code, policy, and
canonical Markdown, and generated artifacts are immutable files addressed by
digest.

```text
React PWA
    |
Owner Gateway (HTTPS/WSS; Firebase Auth + App Check)
    |-- Idea Laval + post APIs -> PostgreSQL
    |-- Plan / Execute -> Codex
    `-- Unix socket -> root broker -> root PTY

Telegram <- notifications + /help /status /stop
```

## Local development

Commander and idea-generation checks:

```sh
python3 -m unittest discover -s tests/commander -v
python3 -m commander.demo --output-dir .local/commander-demo
```

Idea Laval is available in the Ideas web view and through `lav` inside the Idea
Evolution image. Its default fixture providers exercise the complete persisted
pipeline without paid calls; live localized SERPs and Trends require explicit
provider configuration. See
[`docs/architecture/idea-laval-engine.md`](docs/architecture/idea-laval-engine.md).

Web console:

```sh
cd apps/commander-web
npm ci
npm run dev
```

The selective documentation map is in [`docs/README.md`](docs/README.md), the
current milestone in
[`docs/architecture/commander-current-state.md`](docs/architecture/commander-current-state.md),
and operator-console rules in [`DESIGN_RULES.md`](DESIGN_RULES.md).

PTW has no native iOS/Android runtime or legacy compatibility surface.
Historical implementations are available only through Git history.
