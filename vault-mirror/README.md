# vault-mirror/

This directory is a **read-only one-way mirror** of project notes from the
user's primary Obsidian vault, populated by `hooks/vault_sync.sh` (invokable
via the `vault-sync` skill).

## Rules

1. **NEVER edit files inside this directory.** The next sync will overwrite or
   delete your changes. The primary vault is the source of truth.
2. **DO grep / read** these files when researching, ideating, or ingesting
   papers. They contain the user's prior thinking on the project from outside
   the repo.
3. **DO surface insights** from these notes into wiki pages where appropriate
   (with citation back to the original primary-vault path).

## Configuration

Sync settings live in `research-state.yaml` under `vault_sync:`. Run the sync:

```bash
bash ../hooks/vault_sync.sh           # live sync
bash ../hooks/vault_sync.sh --check   # dry run, report drift
```

The mirror reflects whatever was in the primary vault's project sub-path at
the time of the last sync.

## Why a mirror, not a symlink?

A symlink would couple the project repo's git state to the primary vault's
content — every reorganisation in the primary vault would touch the project's
git diff. The mirror is **explicitly desynchronised**: the user controls when
to refresh, and the refresh is an event in the audit trail (`events.jsonl`).
