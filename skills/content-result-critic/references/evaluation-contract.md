# Evaluation contract

## Hard gates

Every candidate must pass task and approved-Brief relevance; exact offer and
CTA; language and required fields; honest claims; approved Project, brand,
media, source, and tool boundaries; one coherent message; no synthetic people
or faces; and rendered crop, collision, hierarchy, legibility, placement,
caption, and alt-text checks.

## Element scores

Give every required element integer 1–10 scores for task fit, clarity,
contribution to the candidate, and coherence with adjacent elements. A final
candidate is ineligible if any required element contribution is below 7.

## Whole-candidate weights

- Task and Brief suitability: 20%
- Hook / stop-scroll strength: 15%
- Message clarity: 15%
- Persuasion and action: 15%
- Cross-element or text/visual coherence: 15%
- Specificity and credibility: 10%
- Composition, legibility, and placement fit: 5%
- Originality and tone fit: 5%

Complexity is separate: none has no penalty, moderate subtracts five points,
and harmful is a hard fail.

Final eligibility requires all hard gates, suitability/clarity/coherence at
least 8, hook/persuasion at least 7, every required contribution at least 7,
weighted total after penalty at least 80, and every rendered placement and
accessibility check.

## Typed actions

- `recompose`: assemble a coherent candidate from locked exact and conceptual
  source elements.
- `regenerate_elements`: replace one bounded weak element group while preserving
  locked UUIDs.
- `rerun_template`: request one meaningful, envelope-valid slider variant.
- `discard`: remove a hard-failed or dominated direction from active review.
- Pass 3 uses `final_selection`, not an improvement action.

Use reason codes and short observations. Do not provide hidden reasoning.
