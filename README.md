# Research Template

A reproducible-research project template made by Claude Opus 4.7. It combines structures from 
three repositories:

1. **A working pipeline** — Snakemake DAG, Pixi environment management, LaTeX-compiled PDF report, pytest, GitHub Actions CI/CD that re-runs every push. Adapted from [`timtroendle/cookiecutter-reproducible-research`](https://github.com/timtroendle/cookiecutter-reproducible-research) with some inspiration 
from [FedericoTartarini/reproducible-research](https://github.com/FedericoTartarini/reproducible-research).
2. **A living wiki** — Obsidian-compatible knowledge base (`wiki/`) with topic, concept, group, synthesis, query, entity, and research-evaluation pages. Append-only event log + state file. Adapted from [`andrehuang/researcher-pack`](https://github.com/andrehuang/researcher-pack).
3. **An LLM research loop** — `paper-read`, `lit-search`, `research-companion`, `weekly-review`, `orchestrate`, `vault-sync` skills with eager invocation. Three sub-agents (brainstormer, idea-critic, research-strategist) for divergence, critique, and strategy. Hook-based bookkeeping for event tracking and state management.

The result is one repo where the *thinking* (wiki + skills) and the *running*
(Snakemake + tests) sit next to each other and don't drift.

## Quickstart

```bash
git clone https://github.com/<you>/research-template.git my-project
cd my-project
rm -rf .git
./setup.sh                 # interactive wizard: project name, vault sync
pixi run snakemake --cores 4   # build the demo report (pixi installs deps automatically)
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
├── hooks/                      # research_hook.sh, vault_sync.sh
├── wiki/                       # Knowledge base (Obsidian vault)
│   ├── meta/                   # Principles + architecture docs
│   └── .vault-mirror/          # READ-ONLY mirror of primary Obsidian vault
├── Snakefile + analysis/ + tests/ + report/
├── pixi.toml + pixi.lock       # Environment + dependency lockfile
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
     vault-sync mirrors primary vault → wiki/.vault-mirror/
     research_hook.sh logs every write
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
  mirror_target: "wiki/.vault-mirror"
```

Then run `bash hooks/vault_sync.sh` (or invoke the `vault-sync` skill in
OpenCode and let the LLM run it). The sync is **one-way** (vault → mirror) with
deletion. Edit notes in the primary vault; the mirror reflects on demand.

Cross-vault Obsidian links work bidirectionally:

- `[[obsidian://vault/obs-notes/02 - Projects/MyProject/Some Note]]` from project wiki
- `[[obsidian://vault/MyProject/wiki/topics/some-topic]]` from primary vault

## Environment & Dependencies

This template uses **[Pixi](https://pixi.sh)** for environment and dependency management:

- **Single source of truth**: `pixi.toml` defines all dependencies (analysis, testing, reporting, linting)
- **Deterministic lockfile**: `pixi.lock` ensures reproducibility across machines and CI runs
- **Fast installation**: `pixi install` resolves dependencies via a Rust-based solver (faster than conda)
- **No per-rule environments**: All Snakemake rules run in the shared pixi environment (simpler, faster)

### Installation

Install pixi once: https://pixi.sh/latest/#installation

Then bootstrap the project:

```bash
cd my-project
pixi install              # Creates isolated project environment
pixi run snakemake --cores 4   # Runs pipeline in pixi environment
```

Or use a pixi shell for interactive work:

```bash
pixi shell --environment default  # Activate pixi environment
snakemake --cores 4               # No pixi prefix needed inside shell
exit                              # Leave environment
```

## LaTeX Development Workflow

This project uses **native LaTeX** (pdflatex via latexmk).

### Prerequisites

- **TeX Live** installed ([tug.org](https://tug.org/texlive/quickinstall.html))
- **latexmk** (included with TeX Live)
- **zathura** (optional, for PDF viewing)
- **nvim + vimtex** (optional, for editing)

### Local Development

1. **Edit LaTeX files** in `report/`:
   - `main.tex` — document root
   - `preamble.tex` — packages & metadata
   - `sections/*.tex` — chapter/section content
   - `bibliography.bib` — references

2. **Compile and view** using the provided script:

   ```bash
   cd report
   ./compile.sh        # Compile and open in zathura
   ./compile.sh -f     # Force clean rebuild
   ```

3. **In a tmux session** (recommended):

   ```
   tmux new-session -s latex
   tmux split-window -h -l 40   # nvim pane (left, 60% width)
   tmux split-window -v         # latexmk pane (bottom-left)

   # Pane 1 (top-left): nvim report/main.tex
   nvim report/main.tex

   # Pane 2 (bottom-left): latexmk watch
   cd report && latexmk -pdf -pvc main.tex  # Preview continuous mode

   # Pane 3 (right): zathura opens automatically
   ```

4. **Sync with Overleaf** (via GitHub):

   ```bash
   git push origin main
   # Then pull in Overleaf from GitHub
   ```

### Pipeline Compilation

For automated builds (e.g., CI):

```bash
pixi run snakemake --cores 4
```

This compiles the LaTeX report as part of the full pipeline.

### References

- [vimtex](https://github.com/lervag/vimtex) — nvim LaTeX plugin with snippets
- [latexmk](https://ctan.org/pkg/latexmk) — Perl script to automate LaTeX compilation
- [zathura](https://pwmt.org/projects/zathura/) — Lightweight PDF viewer

## CI/CD

`.github/workflows/reproduction.yaml` re-runs `snakemake` on every push, PR,
and the 8th of each month via pixi. `.github/workflows/lint.yaml` runs ruff + shellcheck
+ yamllint.

## Customising

Each layer is independently editable:

- **Add a skill** → drop a `.opencode/skills/<name>/SKILL.md` and a trigger row in `.opencode/AGENTS.md`.
- **Add a sub-agent** → drop a `.opencode/agent/<name>.md` with frontmatter (`description`, `mode: subagent`, `tools: ...`).
- **Add a Snakemake rule** → write it in `rules/<name>.smk` and `include:` from `Snakefile`.
- **Add a wiki page type** → extend `wiki/wiki.schema.md` and update the hook's dispatch in `hooks/research_hook.sh`.

Nothing is hidden behind framework abstractions. If you can read the file, you
can fork it.

## Companions

- **[Pixi](https://pixi.sh)** — fast environment & dependency management (Rust-based)
- **[Snakemake](https://snakemake.readthedocs.io)** — pipeline DAG
- **[TeX Live](https://tug.org/texlive/)** — LaTeX distribution
- **[latexmk](https://ctan.org/pkg/latexmk)** — Perl script to automate LaTeX compilation
- **[vimtex](https://github.com/lervag/vimtex)** — nvim LaTeX plugin
- **[zathura](https://pwmt.org/projects/zathura/)** — Lightweight PDF viewer
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

Read [wiki/meta/docs/PATTERN.md](wiki/meta/docs/PATTERN.md) for the higher-level argument and
[wiki/meta/docs/architecture.md](wiki/meta/docs/architecture.md) for the implementation walkthrough.

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgements

This template is a synthesis of:

- **`timtroendle/cookiecutter-reproducible-research`** — Snakemake/Pixi/Pandoc scaffolding (MIT)
- **`FedericoTartarini/reproducible-research`** — folder-structure conventions (MIT)
- **`andrehuang/researcher-pack`** — skill format, wiki schema, hook design (MIT)
- **Nicholas Carlini** — research-strategy principles (RS1–RS8, derived from his "How to Win a Best Paper Award")
- **Michael Black** — academic-writing principles (B1–F2, distilled from "Writing a Good Scientific Paper")
