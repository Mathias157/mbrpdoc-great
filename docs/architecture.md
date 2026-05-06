# Architecture

The research template has three layers stacked on top of a Snakemake pipeline.
This document walks through each layer in enough detail to read the source.

For the higher-level pattern (why integrate research activities at all?), see
[PATTERN.md](./PATTERN.md).

## Layer 0 — Reproducible Pipeline

`Snakefile` defines a DAG that turns raw `data/` and a `config/default.yaml`
into `build/report.html`, `build/report.pdf`, `build/report.docx`, and
`build/test.success`. Each rule has its own conda environment under `envs/`,
so the dependency graph is fully captured by:

- `environment.yaml` (top-level: snakemake itself)
- `envs/default.yaml` (analysis: numpy, pandas, matplotlib)
- `envs/report.yaml` (rendering: weasyprint, pandoc, pandoc-crossref, katex)
- `envs/test.yaml` (testing: pytest, pytest-html)
- `envs/dag.yaml` (visualisation: graphviz)

`profiles/default/config.yaml` sets `software-deployment-method: conda` so any
`snakemake` invocation gets conda-managed environments per rule. CI pins this
in `.github/workflows/reproduction.yaml`, which re-runs the entire DAG on every
push.

## Layer 1 — Skills and Sub-Agents

Each skill lives at `.opencode/skills/<name>/SKILL.md`. OpenCode loads them via
`.opencode/AGENTS.md`, which is read at session start. A skill is a structured
prompt that tells the agent which files to read, which phases to run, and how
to report progress.

Each skill is designed to be useful on its own. You could delete
`research-companion/` and the rest would still work. Coupling between skills is
indirect — they communicate through shared state (`research-state.yaml`,
`events.jsonl`, the wiki), not through function calls.

Sub-agents (under `.opencode/agent/`) are a different primitive. OpenCode
spawns them via the `task` tool with a fresh context window and a narrow role
(`brainstormer`, `idea-critic`, `research-strategist`). Skills delegate to
agents for tasks that benefit from isolated context or adversarial framing.

The skills shipped:

| Skill | Triggers | Output |
|---|---|---|
| `research-session` | session start, "what should I work on?" | briefing + route to a sub-skill |
| `paper-read` | PDF/arXiv mention, "read this paper" | wiki/topics + optional wiki/entities |
| `lit-search` | "find papers on X", "lit review" | wiki/queries/<topic>/ workspace |
| `research-companion` | "brainstorm", "what if", "evaluate this idea" | wiki/research-evaluations + state |
| `weekly-review` | "weekly review", "progress check" | digest event + suggested priorities |
| `orchestrate` | "parallel review", multi-angle task | synthesis from multiple sub-agents |
| `vault-sync` | "sync from vault", briefing reports drift | refreshed `vault-mirror/` |

## Layer 2 — Shared State

Three plain-text files form the bus:

| File | Format | Purpose |
|---|---|---|
| `research-state.yaml` | YAML | Snapshot: wiki counts, last session, suggested actions, vault-sync config |
| `events.jsonl` | JSON Lines, append-only | Chronological log of every research action |
| `wiki/` | Markdown with YAML frontmatter + `[[wikilinks]]` | The knowledge base itself |

At session start, the `research-session` skill reads all three. During a
session, skills update the state file as a side effect of their work. The
append-only event log lets `weekly-review` reconstruct activity over arbitrary
time ranges.

The `paths:` block at the top of `research-state.yaml` is the only place that
resolves physical locations — everything else uses relative references the
agent resolves on read.

The wiki carries one page type that deserves a separate mention:
`research_evaluation`. A research-evaluation page is what `research-companion`
writes at the end of its DECIDE phase — a dated record of the idea it
considered, the alternatives it killed, the stress tests it survived, the
final verdict (PURSUE / PARK / KILL), and the revisit conditions if it was
parked. These pages compose with the rest of the substrate in four ways:

1. The wiki schema treats them as first-class (missing frontmatter fails the
   same lint checks).
2. The index page lists them alongside topics and concepts.
3. The `weekly-review` skill scans them to produce the "decisions you made
   this week" section of the digest.
4. `research_hook.sh` recognises edits under `wiki/research-evaluations/` and
   emits a dedicated event, so the history of every decision is recoverable
   from the event log alone.

## Layer 3 — Bookkeeping Daemon

Three shell scripts in `hooks/`:

- **`research_hook.sh`** — registered as a file-edited hook in `opencode.json`.
  Runs after every Write/Edit. Dispatches on the modified file's path: wiki
  edits emit `wiki:update` events and update the state timestamp;
  research-evaluation edits emit their own event; manuscript edits emit
  `writing:edit`; experiment data emits `experiment:update`. It degrades
  gracefully if hooks aren't auto-fired (the LLM can call it explicitly).

- **`auto_commit.sh`** — called by `research_hook.sh` for commit-worthy
  changes. Uses a pending-file debounce pattern: each call timestamps the
  change; a background process waits for a 30-second quiet period before
  committing everything at once. Categorises commit messages (`wiki: update
  X`, `research: update Y`). Opt-in via `RESEARCH_TEMPLATE_AUTOCOMMIT=1` or a
  `.autocommit.enabled` marker file.

- **`vault_sync.sh`** — one-way `rsync` from the user's primary Obsidian vault
  into `vault-mirror/`. Reads configuration from `research-state.yaml` →
  `vault_sync:`. Updates the state file's `last_sync_at` timestamp and emits a
  `vault:sync` event. Excludes `.obsidian/`, `.trash/`, `Attachments/`, and
  `*.canvas` by default.

These three scripts close the loop without the human having to remember. The
alternative — "maintain a tidy knowledge base by sheer discipline" — is
exactly the thing humans fail at.

## Data Flow, End to End

Here's what happens when the user shares a paper PDF:

1. The user pastes a path or URL: "Can you read this paper?"
2. OpenCode reads `AGENTS.md` and `.opencode/AGENTS.md` on session start. The
   `paper-read` activation row matches.
3. The LLM reads `.opencode/skills/paper-read/SKILL.md` and follows it from
   Phase 1.
4. Phase 1: `read` the PDF (or `webfetch` the URL). Confirm.
5. Phase 2: Generate the structured analysis. Reads `wiki/index.md` and
   relevant `wiki/topics/*.md` to position the paper.
6. Phase 3: Discuss with the user — back-and-forth, grounded in the wiki.
7. Phase 4: Ingest. Edits `wiki/topics/<topic>.md`, optionally creates
   `wiki/entities/<short-id>.md`, appends to `wiki/log.md`, updates
   `wiki/index.md`. Each edit triggers `research_hook.sh`, which appends a
   `wiki:update` event to `events.jsonl` and bumps `last_updated` in
   `research-state.yaml`.
8. After a 30s quiet period, `auto_commit.sh` (if enabled) bundles all the
   changes into one commit and pushes if a remote is configured.
9. Phase 5: Suggest a follow-up — `research-companion` to brainstorm
   implications, `lit-search` to map the surrounding subfield, or another
   paper-read to deepen.

At no point did the user write a commit message, update an index by hand, or
maintain cross-references. That's all in Layer 3.

One other flow worth calling out: `lit-search` is the "many papers at once"
counterpart to `paper-read`. It owns a per-topic workspace under
`wiki/queries/<topic>/` (memory-bank + mind-graph + references.bib) and chains
to `paper-read` whenever the user asks for depth on any one paper. This keeps
the "discover" and "deep-read" layers separate: the workspace is the
scratchpad, `wiki/entities/` and the topic pages are the canonical record, and
the workspace graduates into a `wiki/topics/` or `wiki/syntheses/` page once
its mind-graph stabilises.

## Cross-Vault Architecture

The user keeps a primary Obsidian vault outside this repo (their permanent
knowledge base, PARA + Zettelkasten). This repo is a project-scoped vault that
references the primary vault.

```
~/Documents/OneDrive/obs-notes/         <- PRIMARY VAULT (read-mostly)
  02 - Projects/MyProject/              <- project notes (meetings, plans)

~/Repos/MyProject/                      <- THIS REPO (write-heavy)
  wiki/                                 <- project wiki (Obsidian vault)
  vault-mirror/                         <- read-only mirror of primary vault project notes
```

The `vault-sync` skill keeps `vault-mirror/` aligned with the primary vault
on demand. The wiki cross-references the primary vault via `obsidian://vault/`
URIs. The mirror is read-only from the LLM's perspective: edits there are
overwritten on the next sync, so any changes the user wants reflected in the
primary vault must be made in the primary vault directly.

## Extending

**New skill**: write a new skill under `.opencode/skills/<name>/SKILL.md` and
add a trigger row in `.opencode/AGENTS.md`. If it reads/writes files, the hook
will auto-log its events. If it needs a specialised sub-agent, add it under
`.opencode/agent/`.

**New file type for the hook to recognise**: add a `case` clause to
`hooks/research_hook.sh`. The existing dispatch is organised top-to-bottom by
specificity — wiki pages first, then experiment results, then manuscripts, then
configs, then fallbacks.

**New path convention**: edit the `paths:` block in `research-state.yaml` and
the skills that read it. Skills are forgiving — they default to standard
locations if a path is missing.

**New Snakemake rule**: write it in `rules/<name>.smk` and `include:` from
`Snakefile`. Add a corresponding conda env if it needs new packages, and
extend `tests/test_runner.py` with fixtures for the new outputs.

## The Visual Dashboard

The repo intentionally ships no dashboard of its own. The wiki is plain
markdown, so the right dashboard is a markdown viewer the user already trusts
— and the recommended viewer is Obsidian. Open `wiki/` as a vault. The
folder-based structure (`topics/`, `concepts/`, etc.) maps to Obsidian's graph
view directly; coloured nodes by folder require either a community theme or
the Graph Analysis plugin.

The pattern is portable across implementations because the contract is just
"read and write these plain-text files." You can swap any one tool for a
better one as long as the new one honours the state contract.
