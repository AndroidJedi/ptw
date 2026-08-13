# Instagram vertical adapter

Status: validation vertical, not core architecture.

Instagram creative generation exercises the generic learning loop. The core
owns hypotheses, experiments, observations, insights, decisions, policies,
relationships, and audit history. This adapter maps those concepts to PTW's
existing Story renderer and its reusable components: Hook, Hero Image,
Supporting Visual, Caption, and CTA.

Read next:

1. [`../../architecture/commander-architecture-review.md`](../../architecture/commander-architecture-review.md)
2. [`../../PTW_TEMPLATE_MCP.md`](../../PTW_TEMPLATE_MCP.md)
3. [`../../../PTW_Post_Generator_Current_State_Handoff.md`](../../../PTW_Post_Generator_Current_State_Handoff.md)

The current prototype does not publish to Instagram or fetch platform metrics.
The demonstration accepts deterministic sample metrics at an explicit adapter
boundary so the domain lifecycle can be proven without claiming an integration
that does not exist.
