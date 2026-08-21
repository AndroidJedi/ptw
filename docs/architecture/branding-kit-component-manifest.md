# Branding kit component manifest

Status: code-owned contract
Updated: 2026-08-21

Every approved Brand Kit ZIP contains:

| Path | Contract |
| --- | --- |
| `brand-kit.json` | Validated name, palettes, typography, principles, provenance, clearance warning, and asset map |
| `package.json` | React-compatible ESM package with React 18+ peer dependencies and no generated runtime dependency |
| `src/tokens.css` | Bundled-font faces, light/dark tokens, focus states, reduced motion, controls, cards, alerts, badges, and tabs |
| `src/theme.ts` | Typed light/dark palette, typography, radius, and spacing values |
| `src/components.tsx` | Button, IconButton, TextField, Select, Checkbox, Switch, Card, Badge, Alert, and Tabs |
| `src/index.ts` | Public exports and token stylesheet import |
| `README.md` | Setup, theming, and naming-clearance disclosure |
| `assets/` | Symbol, deterministic light/dark wordmarks, favicon, and app icon |
| `fonts/` | Selected pinned font binaries, full per-family OFL files, and checksum/source catalog |

The model cannot add, remove, or alter component source. Changes to this table
must be implemented in `idea_generation/brand_kit.py`, compiled in a consumer
fixture, and reviewed as application code.
