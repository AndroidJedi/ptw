# Component boundaries

Status: active architecture contract  
Updated: 2026-08-17

`project.components.json` is the machine-readable authority for path ownership
and validation. PTW has four current boundaries:

- `creative-learning`: generic Python learning domain, Idea Laval,
  creative production, feedback lineage, PostgreSQL migrations, and workers.
- `commander-web`: the React/TypeScript mobile-first PWA. It renders bounded
  read models and sends owner intent; it never becomes a domain database.
- `owner-control-plane`: authenticated HTTP/WSS gateway, Codex Plan/Execute,
  documentation/system views, and the narrow Unix-socket root-broker boundary.
- `repository-architecture`: cross-component policies and canonical docs.

Instagram is an adapter within creative learning. Product reasoning and
feedback remain generic so another distribution surface can be added without
changing the core graph.

The PWA and gateway may deploy independently, but schemas and contracts change
through versioned migrations and APIs in this monorepo. The unrelated
`/opt/ptw/platform` Git history is integrated through HTTP/database contracts;
it is never merged into this repository.

Adding another runtime requires a manifest component with its own validations.
There is no native mobile or compatibility component.
