# Research Template — Agent Instructions

This is a **reproducible-research project template** that combines:

- **Snakemake** pipeline for data → analysis → report (.tex -> .pdf via latexmk)
- **Conda** environments per pipeline step
- **OpenCode skills** for the LLM-driven research loop (paper-read, lit-search, research-companion, weekly-review, orchestrate)
- **Wiki** as the persistent knowledge base (Obsidian-compatible)
- **Hooks** that auto-track edits, debounce-commit, and emit events
- **Vault-sync** that mirrors notes from the user's primary Obsidian vault

You (the LLM) operate inside this repo. Read this file first, then follow it.

## Repo Layout

```
.
├── .opencode/                  # Skills + sub-agents + commands
│   ├── agent/                  # brainstormer.md, idea-critic.md, research-strategist.md
│   ├── command/                # Optional explicit slash commands
│   ├── skills/                 # research-session, paper-read, lit-search, research-companion,
│   │                           #  weekly-review, orchestrate, vault-sync — each a folder w/ SKILL.md
│   └── AGENTS.md               # Eager-invocation triggers (READ THIS)
│
├── .github/workflows/          # CI: snakemake reproduction, lint
├── hooks/                      # research_hook.sh, auto_commit.sh, vault_sync.sh
│
├── wiki/                       # Knowledge base (Obsidian vault)
│   ├── meta/                   # Meta-documentation: principles and architecture
│   │   ├── principles/         # academic-writing.md, research-strategy.md (referenced by skills)
│   │   └── docs/               # PATTERN.md, architecture.md
│   ├── topics/                 # THE HEART — thematic pages, 5–15 papers each
│   ├── concepts/               # Cross-cutting methodological ideas
│   ├── groups/                 # Research groups
│   ├── syntheses/              # Cross-cutting analyses
│   ├── queries/                # Saved Q&A + per-topic lit-search workspaces
│   ├── research-evaluations/   # PURSUE/PARK/KILL verdicts from research-companion
│   ├── entities/               # Optional deep-read paper pages
│   ├── sources/{papers,notes}/ # Raw source material
│   ├── .vault-mirror/          # READ-ONLY mirror from primary Obsidian vault
│   ├── wiki.schema.md          # Page-type definitions and operations
│   ├── AGENTS.md               # Wiki-specific agent protocol
│   ├── index.md                # Content catalog
│   └── log.md                  # Append-only operation log
│
├── # Snakemake side
├── Snakefile                   # The DAG: data -> analysis -> report + tests
├── config/default.yaml         # Pipeline parameters
├── profiles/default/           # Snakemake profile
├── report/                     # LaTeX report (will be compiled to PDF with latexmk)
├── scripts/                    # Python/R/etc. analysis scripts
├── tests/                      # Pytest tests of pipeline outputs
├── data/                       # Raw input data (gitkeep)
├── rules/                      # Additional Snakemake rules
│
├── research-state.yaml         # Read on session start (state)
├── events.jsonl                # Append-only event log
├── opencode.json               # OpenCode config (registers hooks)
├── environment.yaml            # Top-level conda env (snakemake)
├── setup.sh                    # Init wizard for customising the template
├── .autocommit.enabled         # Marker (absent by default) — touch to enable auto-commit
└── README.md
```

## Critical Conventions

### Eager Skill Invocation

The user prefers eager invocation — they don't want to type slash commands.

When their message matches a trigger from `.opencode/AGENTS.md`, IMMEDIATELY READ
the relevant `.opencode/skills/<name>/SKILL.md` and follow it. Do NOT paraphrase
the skill. Do NOT delay with clarifying questions before reading — the skill
itself tells you whether to ask.

Quick reference:

| User says or does... | Read this skill |
|---|---|
| Session start, "what should I work on?", "catch me up" | `research-session` |
| Mentions PDF, arXiv URL, "read this paper", "discuss" | `paper-read` |
| "find papers on X", "lit review", "survey" | `lit-search` |
| "brainstorm", "what if", "should I try X?", proposes an idea | `research-companion` |
| "weekly review", "progress check" | `weekly-review` |
| "sync from vault", "pull notes" | `vault-sync` |
| Multi-angle / complex multi-domain task | `orchestrate` |

### Wiki Discipline

When ingesting a paper:

1. **Update an existing topic page** rather than creating a standalone entity page (default).
2. Promote to `wiki/entities/<short-id>.md` only if it warrants a deep-read.
3. Always add `[[wikilinks]]` between new and existing pages — no orphans.
4. Append to `wiki/log.md` and update `wiki/index.md` after every operation.
5. See `wiki/wiki.schema.md` for page-type schemas and length tiers.

### State Discipline

- `research-state.yaml` at repo root — read on session start. The hook updates `last_updated`. You update content fields (`recent_research_evaluations`, `wiki.total_pages`, etc.) as side effects of skill execution.
- `events.jsonl` is **append-only**. Never edit it. Hooks and skills append; nothing rewrites.
- Both files live at the **repo root**, not under `.claude/` or `.opencode/`. This keeps them brand-neutral and visible.

### Vault-Mirror Discipline

`wiki/.vault-mirror/` is a one-way mirror of the user's primary Obsidian vault
(typically `~/Documents/OneDrive/obs-notes/02 - Projects/<project>/`). The mirror
is configured in `research-state.yaml` under `vault_sync:`, populated by
`hooks/vault_sync.sh`, and surfaced by the `vault-sync` skill.

**NEVER edit files inside `wiki/.vault-mirror/`.** Any edits are overwritten on the
next sync. Use it as **input material**: grep it for keywords, cite findings in
wiki pages, surface insights when relevant.

If the user wants content reflected back in their primary vault, they edit the
primary vault directly.

### Fidelity Discipline (no extrapolation)

**All wiki documentation must be a condensation of input, never an extrapolation
from it.** This applies to every page you write or edit — topic pages, entity
pages, syntheses, queries, research evaluations.

Rules:

1. **Cite or omit.** Every claim, finding, or quote on a wiki page must be
   traceable to a specific source: a paper in `wiki/sources/papers/`, a note in
   `wiki/.vault-mirror/`, a chat exchange, or an explicit user statement. If
   you cannot point to the source, do not write the claim.
2. **No filling in gaps.** If `wiki/.vault-mirror/` contains a half-formed note,
   do **not** complete the thought, infer what the user "probably meant", or
   smooth a fragment into a paragraph. Quote or paraphrase only what is there.
   Mark genuine gaps with `TODO: <what's missing>` rather than inventing.
3. **No synthesis without explicit user request.** Do not write "X implies Y"
   or "this generalises to Z" unless the source said so or the user asked for
   synthesis. When the user asks for synthesis, label it: `> [!synthesis]` or a
   "Synthesis (LLM-generated)" heading.
4. **Prefer shorter over longer.** Default to compression. A 200-word topic
   update beats a 1500-word topic update built on speculation. If you find
   yourself padding a section, stop and cut it instead.
5. **Vault-mirror is read-only input, not a prompt.** Notes in
   `wiki/.vault-mirror/` are seeds the user wrote for themselves — they are
   often shorthand, exploratory, or contradictory. Treat them as evidence of
   what the user has thought about, **not** as a license to expand on the
   user's behalf. If a mirrored note contains "consider Balmorel under
   structural change", the wiki may say "user has flagged Balmorel under
   structural change as an open question (`vault-mirror/<path>`)" — it must
   **not** invent what that exploration would conclude.
6. **Distinguish observation from interpretation.** When a section mixes both,
   separate them: facts in plain prose, interpretation under a clearly labelled
   "Interpretation" or "Open questions" subhead.

If you catch yourself writing prose that has no anchor in a source you've read
this session, delete it.

### Cross-Vault Linking

Project notes from the primary vault can link to project-wiki pages and vice
versa using Obsidian's URI scheme:

```
[wiki page from primary vault](obsidian://vault/<repo-folder>/wiki/topics/foo)
[primary-vault note from project](obsidian://vault/obs-notes/02%20-%20Projects/X/note)
```

Or with vault aliases configured: `[[obs-notes/<note>]]` and `[[<repo-name>/<page>]]`.

### Snakemake Discipline

The repo ships with a working demo pipeline (linear-model fit + plot + latexmk
report). To replace with real analyses:

1. Edit `scripts/model.py` and `scripts/vis.py` (or add new scripts).
2. Add corresponding rules in `rules/*.smk` and include them in `Snakefile`.
3. Update `config/default.yaml` with new parameters.
4. Add tests to `tests/test_*.py` and reference them as fixtures in `tests/test_runner.py`.
5. Run `snakemake --use-conda --cores 4` to verify the DAG resolves and produces `build/report.html`, `build/report.pdf`, and `build/test.success`.

The CI workflow at `.github/workflows/reproduction.yaml` re-runs the pipeline
on every push/PR. Keep it green.

### Hook Awareness

`hooks/research_hook.sh` fires on file writes (configured in `opencode.json`).
It:

- Appends events to `events.jsonl` based on the modified file's path
- Updates `last_updated` in `research-state.yaml`
- Queues files for the debounced auto-commit (`hooks/auto_commit.sh`)

Auto-commit is **opt-in**: set `RESEARCH_TEMPLATE_AUTOCOMMIT=1` or `touch .autocommit.enabled` to enable. Without that marker, the hook tracks but does not commit.

If hooks don't fire automatically (platform difference), invoke them explicitly:

```bash
echo '{"tool_input":{"file_path":"wiki/topics/foo.md"}}' | bash hooks/research_hook.sh
```

### Principles

Two principle files live at `wiki/meta/principles/`:

- **`academic-writing.md`** — 30 prose-quality principles (referenced by paper-read, orchestrate, anything writing-adjacent).
- **`research-strategy.md`** — 8 Carlini-derived strategy principles (referenced by idea-critic, research-strategist, research-companion).

Skills load these by reading the file directly (no plugin needed). When a skill says "see wiki/meta/principles/X.md", actually read it.

## Tone & Style

- Match the user's language — Danish or English, mixed is fine.
- The user is doing PhD-level research (energy systems, sector coupling, Balmorel/Antares modelling). Don't condense into pop-science.
- Honest assessments matter more than encouragement. If a paper is weak, say so. If an idea has scooping risk, name names.
- Inline `Topics:: [[..]]` and `Created:: ...` are Dataview-compatible — keep them as inline fields, don't move to YAML frontmatter (unless explicitly Obsidian frontmatter, like in `wiki/topics/<page>.md` per the schema).

## On Skills That Don't Exist Yet

This template provides 7 skills. If the user asks for something that maps to
one of them, use it. If they ask for something that doesn't (e.g., a writing
review pipeline), say so honestly and offer to do it ad-hoc rather than
fabricating a missing skill.

## When in Doubt

1. Read the relevant skill SKILL.md file.
2. Read the wiki schema (`wiki/wiki.schema.md`).
3. Read the principles (`wiki/meta/principles/research-strategy.md`, `wiki/meta/principles/academic-writing.md`).
4. Ask the user one specific question, not five.
