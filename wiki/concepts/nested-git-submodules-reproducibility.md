---
type: concept
aliases: [nested submodules, transitive dependencies, reproducibility via git]
related_projects: [mbrpdoc-great]
related_concepts: [[reproducible-research-template-patterns]]
confidence: high
last_reviewed: 2026-05-07
---

# Nested Git Submodules for Reproducibility

**Definition:** Using Git submodules to recursively pin both a primary dependency (e.g., an energy model) and its own dependencies (e.g., model data), ensuring that a single `git clone` followed by `git submodule update --init --recursive` reconstructs the exact computational environment across machines.

## Key Claims

1. **Reproducibility at scale** — Nested submodules make large, multi-component research projects reproducible without manual intervention or external data fetches.
2. **HPC-friendly** — Once cloned with `--recursive`, compute nodes have no external dependencies; no network calls during job submission or execution.
3. **Explicit versioning** — Every component (model, data, scripts) is pinned to a specific commit, making it impossible to accidentally use a newer version.
4. **Single source of truth** — The project repo becomes self-contained; no need for documentation like "install model from X, then fetch data from Y".

## Evidence

### Use Case: Balmorel Energy Model in mbrpdoc-great

**Setup:**
- `scripts/Balmorel/` is a Git submodule pointing to `github.com:Mathias157/Balmorel.git`
- `scripts/Balmorel/base/data/` is a nested submodule (declared in Balmorel's `.gitmodules`) pointing to `github.com:Mathias157/Balmorel_data.git`

**Outcome:**

```bash
# Clone and initialize everything in one pass
git clone git@github.com:mberos/mbrpdoc-great.git
cd mbrpdoc-great
git submodule update --init --recursive
# ✓ mbrpdoc-great/scripts/Balmorel/ populated
# ✓ mbrpdoc-great/scripts/Balmorel/base/data/ populated
# ✓ All snakemake analyses can run without external fetches
```

**Advantage:** On an HPC, after `git clone` + `--recursive`, the job runs entirely within the local filesystem — no bandwidth bottleneck, no external API dependencies, no "data not found" surprises.

## Open Questions

1. **Submodule depth limit** — How many levels of nesting is practical? (2–3 levels are standard; 5+ becomes unwieldy.)
2. **Large data submodules** — When does the data repo size become a bottleneck? (Balmorel_data is ~100 MB; beyond 1 GB on typical connections, manual mirroring or shallow clones become necessary.)
3. **Submodule branch tracking** — Should nested submodules track a branch (e.g., `master`) or always a commit hash? (Hash is safer for reproducibility; branch is more flexible for development.)

## Related

- [[reproducible-research-template-patterns]] — broader archival and reconstruction strategy
- [[git-workflows-large-projects]] — strategies for managing multi-repo projects in research
