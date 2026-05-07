---
type: query
original_question: "How do I initialize nested Git submodules on HPC after cloning a repository?"
date_answered: 2026-05-07
source_pages: [[nested-git-submodules-reproducibility]]
---

# Setting Up Nested Submodules on HPC

## Short Answer

Use `git submodule update --init --recursive` after cloning. This recursively initializes all submodules and their nested submodules in one pass, ensuring all dependencies (code + data) are available locally without external network calls during job execution.

## Detailed Procedure

### Local Development (Before Pushing to HPC)

If you're adding a nested submodule locally (e.g., Balmorel + Balmorel_data):

```bash
# Inside the parent repo (mbrpdoc-great)
git submodule add <URL-to-Balmorel> scripts/Balmorel

# Inside Balmorel, add the nested data submodule
cd scripts/Balmorel
git submodule add <URL-to-Balmorel-data> base/data
cd ../..

# Commit the new submodule declarations
git add .gitmodules scripts/Balmorel
git commit -m "Add Balmorel model and data as nested submodules"
git push origin <branch>
```

### On HPC (One-Time Setup After Clone)

```bash
# Clone the parent repo
git clone git@github.com:user/mbrpdoc-great.git
cd mbrpdoc-great

# Initialize all submodules recursively
git submodule update --init --recursive

# Verify submodules are populated
ls -la scripts/Balmorel/base/data/  # Should show data files, not empty directory
```

### Running Snakemake on HPC (Afterward)

Once submodules are initialized, the job has everything locally:

```bash
module load pixi  # or conda, depending on HPC environment
pixi run snakemake --cores <N> build/report.html
# No external network needed; all dependencies (Balmorel, data, scripts) are local
```

## Why `--recursive`?

Without `--recursive`, Git only clones the top-level submodule:
- ✓ `scripts/Balmorel/` directory exists
- ✗ `scripts/Balmorel/base/data/` is empty (submodule not initialized)

With `--recursive`, Git clones nested submodules too:
- ✓ `scripts/Balmorel/` populated
- ✓ `scripts/Balmorel/base/data/` populated

## Updating Submodules Later

If the parent repo is updated and submodule URLs or commits change:

```bash
git pull origin <branch>
git submodule update --recursive
```

## Notes for HPC Job Scripts

- **SSH keys required:** If using `git@github.com:...` URLs, ensure SSH keys are available on the HPC login node before submitting the job.
- **No need to re-clone:** Submodules are persisted locally. Future job runs don't need to re-fetch them.
- **Disk quota:** Large data submodules (e.g., 100+ MB) may consume significant disk. Plan HPC storage accordingly.

## Related

- [[nested-git-submodules-reproducibility]] — conceptual overview of nested submodules
- Project setup guide: `../AGENTS.md`
