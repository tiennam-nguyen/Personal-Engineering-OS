# PEOS

Personal Engineering OS is a local-first, single-user modular monolith.

Milestone 1 implements one complete local artifact round trip. Canonical Markdown files are the
source of truth; SQLite is rebuildable derived state. The only supported type is
`knowledge.concept`. Workflows, models, protocols, and providers are not implemented yet.

```powershell
uv run peos --workspace demo init
uv run peos --workspace demo artifact create --title "Concept" --body "Durable idea" --tag peos
uv run peos --workspace demo artifact get art_<id>
uv run peos --workspace demo artifact search "durable"
uv run peos --workspace demo artifact verify art_<id>
Remove-Item demo\.peos\index.sqlite3
uv run peos --workspace demo index rebuild
```

See [MAP.md](MAP.md), [PLAN.md](PLAN.md), [CONTRIBUTING.md](CONTRIBUTING.md), and [adr](adr).
