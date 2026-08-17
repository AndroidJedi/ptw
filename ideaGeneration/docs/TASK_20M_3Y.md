# Mission — Build a Remotely Operated Company Worth USD 20M Within 36 Months

**Mission code:** `MISSION_20M_3Y`  
**Horizon:** 36 months from activation  
**Target outcome:** create a company with a plausible path to a sale or
valuation of at least **USD 20 million**.

This is an optimization target, not a guarantee. “Plausible” requires evidence,
economics, and identifiable buyers or valuation logic; a large market alone is
not sufficient.

## Operating constraint

The company must be controllable remotely from idea discovery, research, and
marketing through development, deployment, and operations. The owner should
intervene asynchronously in high-value decisions rather than perform recurring
delivery, sales, support, or infrastructure work.

Autonomy is always bounded by policy. The system must stop or request approval
for actions that are destructive, legally sensitive, financially irreversible,
or outside an explicit budget and scope.

## Allowed businesses

Prefer software, AI-native products, data products, developer tools, platforms,
marketplaces with automated operations, media/software hybrids, and
productized services that can rapidly remove linear labor. Any legal and
ethical model is allowed if it satisfies the mission and remote-operation
constraint.

## Required idea fields

Every user-facing generated field is a localized object:

```json
{"en": "English source", "uk": "Український переклад"}
```

Each idea must include localized `title`, `one_liner`, `customer`, `problem`,
`product`, `business_model`, `distribution`, `automation`,
`three_year_exit_logic`, `key_risks`, and `first_validation_test`.

The English value is the LLM reasoning contract. Ukrainian is the default UI
value and must preserve meaning rather than add claims.

## Hard questions

Every idea must explain:

1. Why a buyer or investor could reasonably value it at USD 20M within 36
   months.
2. How the owner can control idea, marketing, development, deployment, and
   operations remotely.
3. Which workflows become software-driven or delegated and where human policy
   gates remain.
4. How distribution grows without permanent owner-led selling.
5. Why value can scale faster than operating cost.
6. What becomes difficult to copy.
7. What small test can quickly disprove the central assumption.

## Evaluation rubric — 100 points

- **Three-year USD 20M exit potential — 25.** Credible revenue, growth,
  strategic-acquirer, or financing logic inside 36 months.
- **Remote operability and autonomy — 25.** Remote visibility and control,
  repeatable automation, small-team leverage, and explicit policy gates.
- **Distribution — 15.** A believable, scalable acquisition mechanism beyond
  generic paid ads or permanent owner sales.
- **Scalability and economics — 15.** Revenue or strategic value can grow
  materially faster than headcount, delivery cost, and complexity.
- **Defensibility — 10.** Data, network, workflow, integration, ecosystem,
  brand, or distribution advantage compounds.
- **Speed and capital efficiency — 10.** The riskiest assumption can be tested
  quickly without large irreversible investment.

Total: `25 + 25 + 15 + 15 + 10 + 10 = 100`.
