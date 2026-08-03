# GREAT — Agent Instructions

You operate inside the GREAT research repo. See `README.md` for what the
project is; this file is the operational protocol.

## Repo Layout

```
.
├── Snakefile                   # The DAG: data -> analysis -> report + tests
├── rules/                      # Additional Snakemake rules (e.g. download_data.smk)
├── config/default.yaml         # Pipeline parameters
├── profiles/default/           # Snakemake profile
├── analysis/                   # Analysis scripts
│   └── Balmorel/               # Git submodule (Mathias157/Balmorel) — has its own
│                                #  nested submodule at base/data
├── report/                     # LaTeX report (compiled to PDF via latexmk)
├── tests/                      # Pytest tests of pipeline outputs
├── data/                       # Raw input data (gitignored)
├── docs/research-strategy.md   # Carlini-derived research-direction principles
├── pixi.toml / pixi.lock       # Environment + dependency lockfile
└── .github/workflows/          # CI: reproduction.yaml, lint.yaml
```

## Critical Conventions

**LLM agents in this repo are forbidden from running `git commit` under any
circumstances.** Commits are exclusively the user's responsibility.

**Nested submodules.** `analysis/Balmorel` is a git submodule that itself
contains a submodule (`base/data`). After cloning or pulling, run:

```
git submodule update --init --recursive
```

Uninitialized submodules look like empty directories — don't assume the code
or data is missing before checking this.

## Snakemake Discipline

The DAG runs data → preprocessing → analysis → LaTeX report → tests:

1. Edit `analysis/*.py` (or add new scripts) for new analysis steps.
2. Add corresponding rules in `rules/*.smk` and `include:` them in `Snakefile`.
3. Update `config/default.yaml` with new parameters.
4. Add tests to `tests/test_*.py`, referenced as fixtures in `tests/test_runner.py`.
5. Run `pixi run snakemake --cores 4` to verify the DAG resolves and produces
   `build/main.pdf` and `build/test.success`.

`.github/workflows/reproduction.yaml` re-runs this on every push/PR and
monthly. Keep it green.

## Research Strategy

When evaluating whether a research direction is worth pursuing (not just
whether it's technically feasible), consult `docs/research-strategy.md` — 8
principles derived from Nicholas Carlini's "How to Win a Best Paper Award"
(e.g. "if you don't do this, how many months until someone else does?").

## Tone & Style

- Match the user's language — Danish or English, mixed is fine.
- The user is doing PhD-level research (energy systems, sector coupling,
  Balmorel modelling). Don't condense into pop-science.
- Honest assessments matter more than encouragement. If an idea or result is
  weak, say so.

## When in Doubt

1. Read `README.md` for project context.
2. Read `docs/research-strategy.md` if the question is about direction, not mechanics.
3. Ask the user one specific question, not five.
