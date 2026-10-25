Implement task $ARGUMENTS from TASKS.md.

1. Read CLAUDE.md, the task's acceptance criteria, and the relevant sections of docs/PRD.md and docs/ARCHITECTURE.md.
2. State your plan in 5 bullets or fewer, then list any ambiguity (ask before building if it affects an invariant).
3. Write failing tests first, then the implementation.
4. Run `make lint test`; fix until green.
5. Update db/schema.sql, schemas/, docs/ if behaviour changed.
6. Tick the task in TASKS.md and summarize: what changed, tests added, anything deferred, risks noticed.
