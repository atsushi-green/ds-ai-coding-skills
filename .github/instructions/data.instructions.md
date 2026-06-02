---
applyTo: "data/**"
---
Do not create, modify, or commit real data files under `data/raw/` or `data/external/` — these are immutable. Writing derived data to `data/interim/` or `data/processed/` is allowed in code, but do not commit large data files. Only `.gitkeep` files and documentation (README, markdown) are acceptable to commit. See `.github/skills/safe-data-handling/SKILL.md`.
