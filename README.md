# Research Template

A reproducible-research project template combining three things that usually
live in three separate worlds:

1. **A working pipeline** — Snakemake DAG, Conda environments, Pandoc-rendered HTML/PDF/DOCX report, pytest, GitHub Actions CI/CD that re-runs every push. Adapted from [`timtroendle/cookiecutter-reproducible-research`](https://github.com/timtroendle/cookiecutter-reproducible-research).
2. **A living wiki** — Obsidian-compatible knowledge base (`wiki/`) with topic, concept, group, synthesis, query, entity, and research-evaluation pages. Append-only event log + state file. Adapted from [`andrehuang/researcher-pack`](https://github.com/andrehuang/researcher-pack).
3. **An LLM research loop** — `paper-read`, `lit-search`, `research-companion`, `weekly-review`, `orchestrate`, `vault-sync` skills with eager invocation. Three sub-agents (brainstormer, idea-critic, research-strategist) for divergence, critique, and strategy. Hook-based bookkeeping that auto-commits if you opt in.

The result is one repo where the *thinking* (wiki + skills) and the *running*
(Snakemake + tests) sit next to each other and don't drift.

## Quickstart

```bash
git clone https://github.com/<you>/research-template.git my-project
cd my-project
./setup.sh                 # interactive wizard: project name, vault sync, auto-commit
conda env create -f environment.yaml
conda activate <project-short-name>
snakemake --use-conda --cores 4   # build the demo report
```

Then open the repo in OpenCode and start a conversation. The
`research-session` skill activates eagerly on greetings, briefings, or "what
should I work on?".

## What you get

```
.
├── .opencode/                  # Skills + sub-agents (eager invocation)
│   ├── agent/                  # brainstormer, idea-critic, research-strategist
│   └── skills/                 # 7 skills covering the full research loop
├── .github/workflows/          # reproduction.yaml + lint.yaml
├── hooks/                      # research_hook.sh, auto_commit.sh, vault_sync.sh
├── principles/                 # academic-writing.md, research-strategy.md
├── wiki/                       # Knowledge base (Obsidian vault)
├── vault-mirror/               # READ-ONLY mirror of primary Obsidian vault
├── Snakefile + envs/ + scripts/ + tests/ + report/
├── research-state.yaml         # State (read on session start)
└── events.jsonl                # Append-only event log
```

## The Loop

```
                  ┌──────────────────────┐
                  │  research-session    │  ← eager-invoked on greetings
                  │  (briefing + route)  │
                  └──────────┬───────────┘
                             ▼
   ┌─────────────┬───────────────────┬───────────────┐
   │ paper-read  │ research-companion│  lit-search   │
   │  (5 phases) │   (6 phases)      │  (subfield    │
   │             │  brainstormer +   │   workspace)  │
   │             │  idea-critic +    │               │
   │             │  research-strategist             │
   └──────┬──────┴─────────┬─────────┴───────┬───────┘
          ▼                ▼                 ▼
       wiki/topics     wiki/research-      wiki/queries
       wiki/entities   evaluations         (graduates →
                                            topics/syntheses)

   weekly-review reads events.jsonl + state + git log
   vault-sync mirrors primary vault → vault-mirror/
   research_hook.sh logs every write & queues auto-commit
```

## Eager Invocation

Skills are not slash commands. The LLM detects intent and reads the relevant
SKILL.md. See `.opencode/AGENTS.md` for the full trigger table; the short
version:

| You say... | LLM activates |
|---|---|
| "what should I work on?", "catch me up", session start | `research-session` |
| Mentions a PDF, arXiv URL, "read this paper" | `paper-read` |
| "find papers on X", "lit review", "survey [field]" | `lit-search` |
| "brainstorm", "what if", "should I try X?" | `research-companion` |
| "weekly review", "progress check" | `weekly-review` |
| "sync from vault", "pull notes" | `vault-sync` |
| Multi-angle / parallel review | `orchestrate` |

If you'd rather invoke explicitly, `research-session` also exists as
`.opencode/command/research-session.md`.

## Vault Sync

If you keep a primary Obsidian vault for cross-project knowledge (e.g.,
`~/Documents/OneDrive/obs-notes` with `02 - Projects/<this-project>/`), point
this repo's `vault-sync` at it:

```yaml
# research-state.yaml
vault_sync:
  primary_vault: "~/Documents/OneDrive/obs-notes"
  project_path_in_vault: "02 - Projects/MyProject"
  mirror_target: "vault-mirror"
```

Then run `bash hooks/vault_sync.sh` (or invoke the `vault-sync` skill in
OpenCode and let the LLM run it). The sync is **one-way** (vault → mirror) with
deletion. Edit notes in the primary vault; the mirror reflects on demand.

Cross-vault Obsidian links work bidirectionally:

- `[[obsidian://vault/obs-notes/02 - Projects/MyProject/Some Note]]` from project wiki
- `[[obsidian://vault/MyProject/wiki/topics/some-topic]]` from primary vault

## Auto-Commit

Off by default. To enable:

```bash
touch .autocommit.enabled
# or export RESEARCH_TEMPLATE_AUTOCOMMIT=1
```

The hook batches commit-worthy writes behind a 30-second debounce. Wiki
updates, research-evaluation saves, and config edits get categorised commit
messages (`wiki: update foo, bar`, `research: update baz`). It pushes if a
remote named `origin` is configured; otherwise commits locally.

## CI/CD

`.github/workflows/reproduction.yaml` re-runs `snakemake` on every push, PR,
and the 8th of each month. `.github/workflows/lint.yaml` runs ruff + shellcheck
+ yamllint.

## Customising

Each layer is independently editable:

- **Add a skill** → drop a `.opencode/skills/<name>/SKILL.md` and a trigger row in `.opencode/AGENTS.md`.
- **Add a sub-agent** → drop a `.opencode/agent/<name>.md` with frontmatter (`description`, `mode: subagent`, `tools: ...`).
- **Add a Snakemake rule** → write it in `rules/<name>.smk` and `include:` from `Snakefile`.
- **Add a wiki page type** → extend `wiki/wiki.schema.md` and update the hook's dispatch in `hooks/research_hook.sh`.
- **Tweak the auto-commit message format** → edit `do_commit()` in `hooks/auto_commit.sh`.

Nothing is hidden behind framework abstractions. If you can read the file, you
can fork it.

## Companions

- **[Snakemake](https://snakemake.readthedocs.io)** — pipeline DAG
- **[Pandoc](https://pandoc.org)** — Markdown → HTML/PDF/DOCX
- **[Obsidian](https://obsidian.md)** — open `wiki/` and your primary vault as separate vaults
- **[Dataview plugin](https://github.com/blacksmithgu/obsidian-dataview)** — for inline-field queries on the wiki

## Philosophy

Research lives in the handoffs between activities. Reading on Monday, drafting
on Friday, brainstorming in between — without a binding substrate, none of
those activities know the others happened. This template gives you that
substrate as plain text the machine maintains for you.

The hook is non-negotiable: humans abandon knowledge bases because maintaining
cross-references is boring; LLMs don't get bored. The wiki is the system of
record; everything else (state file, event log, primary vault) feeds it.

Read [docs/PATTERN.md](docs/PATTERN.md) for the higher-level argument and
[docs/architecture.md](docs/architecture.md) for the implementation walkthrough.

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgements

This template is a synthesis of:

- **`timtroendle/cookiecutter-reproducible-research`** — Snakemake/Conda/Pandoc scaffolding (MIT)
- **`FedericoTartarini/reproducible-research`** — folder-structure conventions (MIT)
- **`andrehuang/researcher-pack`** — skill format, wiki schema, hook design (MIT)
- **Nicholas Carlini** — research-strategy principles (RS1–RS8, derived from his "How to Win a Best Paper Award")
- **Michael Black** — academic-writing principles (B1–F2, distilled from "Writing a Good Scientific Paper")
