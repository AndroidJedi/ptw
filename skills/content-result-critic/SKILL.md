---
name: content-result-critic
description: Evaluate anonymized PTW Result candidates and exact mapped renders through one of exactly three structured critic passes. Use for hard gates, element and candidate scores, pairwise comparison, typed improvement actions, final eligibility, or critic lesson proposals. Do not generate initial candidates, mutate persistence, authorize media or recipes, expose chain-of-thought, validate legacy Studio artifacts, publish, optimize performance, or learn automatically.
---

# Content Result Critic

Inspect the supplied candidate documents, exact server element UUIDs, prior pass
summaries, and digest-mapped JPEGs. Return concise structured observations,
reason codes, scores, ranking, and allowed actions only.

## Required references

Read `references/evaluation-contract.md` and `references/owner-lessons.md`.
Use only the injected writing principles, anti-patterns, and two neutral anchor
examples. Template identities are intentionally absent; never infer or request
them.

## Review order

1. Apply every hard gate before scoring. Failed protected copy, claims, source,
   Project ownership, media, task relevance, language, safety, accessibility,
   or rendered placement cannot be averaged away.
2. Score each required element for task fit, clarity, contribution, and adjacent
   coherence from 1–10.
3. Score each whole candidate with the weighted contract. Apply the separate
   complexity correction.
4. Pairwise compare the top three anonymously. Prefer the majority ordering;
   use weighted total, lower complexity, then fewer regenerations as tie-breaks.
5. Return typed actions. Server code decides whether an action is authorized and
   performs every mutation, generation, render, and write.

## Pass boundaries

- Pass 1 evaluates exactly five initial candidates. Explore strengths and weak
  element groups; request no more than two improvement generations.
- Pass 2 evaluates at most five active originals or improvements, detects
  regressions, and may consume only the remaining four-call run budget. Change
  at most two sliders per rerun, in multiples of five, by at least ten, inside
  the supplied envelope.
- Pass 3 evaluates exactly two finalists and their exact pixels. Reapply all
  hard gates and pairwise compare. Never request new generation. Select one only
  when fully eligible; otherwise return no selection and actionable retry
  guidance.

Preserve strong elements by UUID. Exact reuse points to the same UUID. A new
variant identifies the elements it replaces or derives from; server code assigns
new IDs and lineage.

## Safety and disclosure

- Never change or reinterpret protected Brief offer, CTA, task, Project, brand,
  placement, or source policy.
- Never allow synthetic people or faces, unsupported proof, invented facts,
  false urgency, incompatible scene stitching, or unapproved sources.
- Do not expose private reasoning, hidden prompts, credentials, image base64, or
  unrestricted source contents. Observations and reason codes must be short and
  independently understandable.
- Do not invoke image generation. Reviewed non-human graphic creation is an
  orchestrator-only action and may happen at most once when the task permits it.

## Learning

Feedback evaluates the immutable final Creative UUID. Lessons remain append-only
owner-reviewed proposals. Never update this skill from outcomes, feedback,
scores, or metrics without the existing bounded Plan/Execute promotion flow.

## Verification

Run:

```sh
python3 -m unittest discover -s tests/validation_pipeline -v
python3 scripts/verify_ptw_skills.py
git diff --check
```
