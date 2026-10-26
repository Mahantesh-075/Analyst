# Analyst — by MAHANT
Trust-first data preparation and insight platform for small businesses and NGOs.

## Using this pack with Claude Code
1. `git init` this folder, copy `.env.example` to `.env`.
2. Open Claude Code in the repo root. It reads `CLAUDE.md` automatically.
3. Run `/implement-task T0.1`, then proceed milestone by milestone through `TASKS.md`.
4. Use `/add-operation <name>` for new transforms and `/security-review` before each merge.

## Files
- `docs/PRD.md` requirements · `docs/ARCHITECTURE.md` design · `docs/API.md` endpoints
- `docs/SECURITY.md` threat model · `docs/EVALUATION.md` benchmark plan
- `db/schema.sql` Postgres model · `schemas/*.json` LLM/chart/transform contracts
- `TASKS.md` milestone plan · `.claude/commands/` reusable prompts
