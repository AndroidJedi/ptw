# Marketing Positioning research lineage

The owner idea is stored before work begins. A strict research-plan call creates
two to four localized queries. Verified DataForSEO tasks are keyed durably;
their remote task IDs and cost are stored once and reused after retry. Total
paid cost for one revision cannot exceed USD 0.05.

Only bounded organic results and safe public HTTPS pages are eligible. The page
fetcher rejects private/local addresses, credentials, non-HTTP redirects,
unsupported MIME, excessive bodies, and unsafe DNS results. Selected findings
enter through `ResearchKnowledgeService`, which creates permanent Source UUIDs
before synthesis.

Each generated factual statement lists allowed Source UUIDs. Uncited inference
is marked `assumption: true`; metrics, proof, testimonials, limitations, and
competitive facts cannot be invented. Failure of research, safe-page reading,
bridge availability, schema validation, or quality gates fails the durable
attempt. There is no fixture/model-knowledge fallback in live generation.
