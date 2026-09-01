# GREAT

GREAT is a [Balmorel](https://balmorel.com/)-based energy system model
evaluating the value of flexibility (e.g. datacentre demand response, EVs)
across 13 scenarios: 11 individual flexibility on/off toggles, an all-on base
scenario, and an all-off scenario.

The repo combines a Snakemake pipeline (data → analysis → LaTeX report) with
pytest tests and CI that reproduces the pipeline on every push.

## Quickstart

```bash
git clone --recurse-submodules <this-repo-url>
cd mbrpdoc-great
pixi install                  # installs dependencies
pixi run snakemake --cores 4  # runs the pipeline, builds build/main.pdf
```

`scripts/Balmorel` is a git submodule with its own nested submodule
(`base/data`). If you cloned without `--recurse-submodules`, run
`git submodule update --init --recursive` before `pixi run snakemake`.

## Repo Layout

```
.
├── Snakefile + rules/           # Snakemake DAG
├── config/default.yaml          # Pipeline parameters
├── scripts/                     # GREAT-specific preprocessing + Balmorel submodule
│   └── Balmorel/                # Balmorel model + its own analysis/plotting toolkit
├── report/                      # LaTeX report source
├── tests/                       # Pytest tests of pipeline outputs
├── data/                        # Raw input data (gitignored)
├── docs/research-strategy.md    # Research-direction principles
├── pixi.toml + pixi.lock        # Environment + dependency lockfile
└── AGENTS.md                    # Agent operating instructions
```

## Environment & Dependencies

This project uses **[Pixi](https://pixi.sh)** for environment and dependency
management:

- **Single source of truth**: `pixi.toml` defines all dependencies (analysis, testing, reporting, linting)
- **Deterministic lockfile**: `pixi.lock` ensures reproducibility across machines and CI runs
- **No per-rule environments**: All Snakemake rules run in the shared pixi environment

Install pixi once: https://pixi.sh/latest/#installation, then:

```bash
pixi install                     # Creates isolated project environment
pixi run snakemake --cores 4     # Runs pipeline in pixi environment
```

Or use a pixi shell for interactive work:

```bash
pixi shell --environment default
snakemake --cores 4
exit
```

## LaTeX Development Workflow

This project uses **native LaTeX** (pdflatex via latexmk).

### Prerequisites

- **TeX Live** ([tug.org](https://tug.org/texlive/quickinstall.html))
- **latexmk** (included with TeX Live)
- **zathura** (optional, for PDF viewing)
- **nvim + vimtex** (optional, for editing)

### Local Development

1. Edit LaTeX files in `report/`:
   - `main.tex` — document root
   - `preamble.tex` — packages & metadata
   - `bibliography.bib` — references

2. Compile and view:

   ```bash
   cd report
   ./compile.sh        # Compile and open in zathura
   ./compile.sh -f     # Force clean rebuild
   ```

3. In a tmux session (recommended):

   ```
   tmux new-session -s latex
   tmux split-window -h -l 40   # nvim pane (left, 60% width)
   tmux split-window -v         # latexmk pane (bottom-left)

   # Pane 1 (top-left): nvim report/main.tex
   nvim report/main.tex

   # Pane 2 (bottom-left): latexmk watch
   cd report && latexmk -pdf -pvc main.tex

   # Pane 3 (right): zathura opens automatically
   ```

4. Sync with Overleaf (via GitHub):

   ```bash
   git push origin main
   # Then pull in Overleaf from GitHub
   ```

## Research Strategy

`docs/research-strategy.md` holds 8 principles (derived from Nicholas
Carlini's "How to Win a Best Paper Award") for judging whether a research
direction is worth pursuing — novelty, kill-early, comparative advantage, etc.

## CI/CD

- `.github/workflows/reproduction.yaml` re-runs `snakemake` on every push, PR,
  and the 8th of each month via pixi.
- `.github/workflows/lint.yaml` runs ruff + yamllint.

## Acknowledgements

Snakemake/Pixi pipeline structure adapted from
[`timtroendle/cookiecutter-reproducible-research`](https://github.com/timtroendle/cookiecutter-reproducible-research)
and [`FedericoTartarini/reproducible-research`](https://github.com/FedericoTartarini/reproducible-research) (MIT).

## License

MIT — see [LICENSE](LICENSE).
