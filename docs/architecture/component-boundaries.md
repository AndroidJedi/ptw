# Component boundaries

Status: active architecture contract  
Updated: 2026-08-13

PTW remains a monorepo while the creative-learning boundary is evolving. Code
organization and automated validation are component-based rather than tied to a
single repository language.

`project.components.json` is the machine-readable authority for component path
ownership and validation. The engineering runner resolves the final changed
paths against this manifest, runs global checks once, then runs only the checks
declared by affected components. Overlapping components are allowed and command
deduplication is required.

The initial boundaries are:

- `creative-learning`: Python Commander, Telegram creative transport,
  research, feedback lineage, component weights, migrations, and runtime tests.
- `flutter-product`: the Flutter mobile and web product.
- `template-tooling`: template authoring MCP and its Flutter-side contracts.

Physical directory moves are intentionally deferred. Moving stable modules is
mechanical; discovering a premature boundary through broken imports and
deployment paths is expensive. A component may move to a dedicated repository
only after it has an independent release cadence and a stable API boundary.

Documentation-only changes receive global validation unless their path is
explicitly owned by a component. Adding a new runtime or language requires a
new manifest component, not changes to the generic engineering runner.
