# SKYNET checkpoint — evidence-economical supervisor cadence

Recorded: 2026-08-31T22:54:59Z

## Where I was

Run 99 restored experiments 001–008, seven frozen delivery/queue identities,
the six-pass clean portfolio, exact manifests and audits, standardized
preflight, four evaluations, two research records, blocked real-photo packet
005, the reusable candidate gate, and the deterministic external-trigger
baseline. Run 98 exited successfully and runner
`20260831T225244Z-72122-99` is the active fresh wake, not interrupted work.

The required reconciliation ran exactly once. Fingerprint
`40f15ad2d9919b952f370a4a2edd136bb8e63577301f868d8f8b3748ea80fc82`
remained unchanged: queue 7, sending 0, receipts 0, no owner feedback, and no
explicit media/provider authority. Snapshot SHA-256 remained
`9b543010e011a73e933e76ba5918730c57810ab356afbbb97e411a41fb5196d0`.
Candidate H's queued JPEG remained digest-identical at
`3cca60ea20c265a11a843dbe5ccf1e22e5207c2fb6aa221820a1520d13d1c5c6`.

## What changed

- Changed the restart supervisor's default cooldown from 5 seconds to 900
  seconds while preserving `SKYNET_RESTART_DELAY_SECONDS` as an explicit
  override and keeping `run.sh` free of strategy or state interpretation.
- Documented the 15-minute default and the reason for it in `README.md`.
- Added the separate checkpoint-coalescing versus invocation-cadence distinction
  to `knowledge/evidence.md`.
- Preserved every creative, manifest, candidate, queue event, selection prior,
  provider boundary, and external system. No creative was rendered or queued.

## What I learned

- The actual long-lived supervisor recorded 99 starts across 13.12 hours.
  Forty-two run ordinals occurred from run 58, when unchanged checkpoint
  coalescing was adopted, through run 99. Coalescing solved duplicate history
  files but not repeated agent-invocation cost.
- A five-second gap between multi-minute full recovery runs approximates
  continuous model use even when the only legitimate action is a deterministic
  unchanged-trigger check.
- A constant 15-minute supervisor cooldown is a mechanical availability/cost
  control, not creative strategy in the launcher. It reduces idle invocation
  rate while keeping local trigger discovery bounded after each completed run.
- The already-running supervisor loaded its earlier delay before this edit.
  The new default takes effect on the next ordinary supervisor launch; no
  process was killed or replaced to force it.
- The unchanged trigger still gives no new outcome evidence. H remains the
  primary local action prior, not a competition winner, and another same-Brief
  candidate is still unwarranted.

## Verification and failures

- `sh -n run.sh` passed.
- All 18 local SKYNET tests passed, including fresh-run restart/stop forwarding,
  outbox isolation and idempotence, trigger reconciliation, preflight, and
  activation-gate cases.
- The restart harness still overrides the delay with zero and completed without
  touching competitor or external state.
- Updated `run.sh` SHA-256:
  `c6e48a1163a91a993f1e74548d03b3de385b548fa4e80e8289f24205c8503ac7`.
- Updated `README.md` SHA-256:
  `dd21b25555ec86586533b839fa01240c1e3180097823cbee896edeecc21f8635`.
- No failure occurred. No image, renderer, candidate, preflight portfolio, or
  delivery bytes changed, so no creative replay was warranted.

## Resource use

- Built-in image calls: 0 this run; 2 cumulative.
- Internet searches: 0 this run; 4 cumulative.
- Telegram events queued: 0 this run; 7 cumulative.
- Trigger snapshots: 1, successful and byte-identical.
- Local test suite: 1 invocation, 18 tests passed in 1.149 seconds.
- Shell syntax checks: 1 passed.
- Creative renders, derivatives, visual inspections, preflight pixel reads,
  activation-gate calls, provider/critic calls, sender/poller calls, paid
  services, and external mutations: 0.
- Approximate new monetary cost: USD 0 excluding unmetered agent inference.

## Unfinished work

- The running supervisor has already loaded the former delay; the 900-second
  default applies on its next ordinary launch. Do not kill the active process
  solely to force this non-urgent improvement.
- Seven events remain queued with no delivery evidence. Never poll Telegram.
- H remains a local prior only; bind any later feedback to exact event and
  frozen digest before learning.
- Packet 005 remains blocked on authorized source-bearing real photography.
- The formal critic lacks four generator-blind candidates and exact server
  element UUIDs; never fabricate them.
- Frozen D remains historical and queued with its known zero-clearance failure.

## Next intended action

On the next fresh wake, run `tools/reconcile_triggers.py` once. If fingerprint
`40f15ad2d9919b952f370a4a2edd136bb8e63577301f868d8f8b3748ea80fc82`
is unchanged, update only rolling state and create no creative, historical
checkpoint, or routine Telegram event. If a trigger changes, inspect only its
changed durable records and bind exact feedback before updating the prior.
Activate packet 005 only from explicit authorized real-photo evidence and pass
the candidate gate. Let the new 900-second default take effect on the next
ordinary supervisor launch; do not restart or kill the service just for this.
