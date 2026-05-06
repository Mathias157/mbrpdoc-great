---
name: vault-sync
description: >-
  One-way sync from the user's primary Obsidian vault into this project repo's
  `vault-mirror/` directory. ACTIVATE EAGERLY when the user mentions syncing notes from
  their primary vault, says "pull from vault", "refresh notes", "sync project notes", or
  when the research-session briefing reports vault-mirror drift.
---

# Vault-Sync — Primary Vault → Project Mirror

You handle one-way synchronisation from the user's primary Obsidian vault (the "main" vault, e.g., `~/Documents/OneDrive/obs-notes`) into this project repo's `vault-mirror/` directory. The mirror is read-only from the LLM's perspective — it surfaces project-relevant notes from the primary vault so they're searchable and citeable from the project repo without duplicating content.

## Activation Triggers (eager invocation)

ACTIVATE this skill when the user says:

- "sync from vault", "pull from vault", "refresh vault-mirror"
- "pull project notes", "import primary vault notes"
- The research-session briefing reports drift in `vault-mirror/`
- The user references a note like `[[<note name>]]` and the LLM cannot find it locally

## Configuration

Sync settings live in `research-state.yaml` under the `vault_sync` key. Defaults:

```yaml
vault_sync:
  primary_vault: "~/Documents/OneDrive/obs-notes"
  project_path_in_vault: "02 - Projects/<project-name>"
  mirror_target: "vault-mirror"
  exclude:
    - ".obsidian"
    - ".trash"
    - "Attachments"
    - "*.canvas"
```

If `vault_sync` is missing from the state file, ask the user for:

1. **Primary vault path** (default: `~/Documents/OneDrive/obs-notes`)
2. **Project path within vault** (the user types e.g. `02 - Projects/GREAT`)
3. **Mirror target** (default: `vault-mirror`)

Then write the values back to `research-state.yaml`.

## Sync Protocol

The actual sync is performed by `hooks/vault_sync.sh` which uses `rsync` for one-way replication with deletion (so removed notes in primary vault disappear from the mirror).

### Steps

1. **Read configuration** from `research-state.yaml` → `vault_sync`.
2. **Resolve paths**: expand `~`, verify the source exists, create the target directory if missing.
3. **Run the sync**:

   ```bash
   bash hooks/vault_sync.sh
   ```

   The script does the equivalent of:

   ```bash
   rsync -av --delete \
     --exclude='.obsidian' --exclude='.trash' --exclude='Attachments' --exclude='*.canvas' \
     "$PRIMARY_VAULT/$PROJECT_PATH/" \
     "$REPO_ROOT/$MIRROR_TARGET/"
   ```

4. **Confirm**: report the number of files synced, any deletions, and the wall-clock duration.
5. **Update state**: set `vault_sync.last_sync_at` to the current ISO-8601 timestamp.
6. **Emit event** to `events.jsonl`:

   ```jsonl
   {"ts":"<ISO-8601>","type":"vault:sync","detail":"Synced N files from primary vault","source":"vault-sync"}
   ```

7. **Surface insights**: scan the synced notes for any that touch active wiki topics. Report: "Note `<name>` references `[[topic]]` which has a wiki page — want me to update the topic page with anything from this note?"

## Read-Only Discipline

- **NEVER edit files inside `vault-mirror/`**. Edits will be overwritten on the next sync.
- Treat `vault-mirror/` as read-only input material.
- If the user wants changes reflected back in the primary vault, they must edit the primary vault directly. The sync is one-way (vault → mirror) by design.

## Cross-Vault Linking (Obsidian)

The user can navigate between vaults in Obsidian using the cross-vault link syntax:

```
[Click to open primary vault note](obsidian://vault/obs-notes/02%20-%20Projects/GREAT/some-note)
```

Or if both vaults have aliases configured, simply `[[obs-notes/02 - Projects/GREAT/some-note]]`. Project-wiki pages may use this syntax to link back to the primary vault when referencing the broader knowledge graph.

## When to Sync

Suggest a sync at:

1. **Session start** if the briefing reports drift (more than 7 days since last sync, or significant primary-vault activity).
2. **Before paper-read** when the paper's topic intersects with project notes in the primary vault.
3. **After a research-companion session** so any insights captured in the primary vault during ideation are picked up.
4. **Before weekly-review** so the digest reflects fresh state.

Do NOT sync on every turn — the operation may take seconds and is rarely needed mid-conversation.

## Conflict Handling

The sync uses `rsync --delete`, which means:

- A note added in primary vault → appears in mirror on next sync.
- A note edited in primary vault → mirror is overwritten.
- A note deleted in primary vault → mirror copy is deleted.
- A file added in mirror but NOT in primary vault → **deleted on next sync**.

This is intentional: the primary vault is the source of truth. If the LLM has accidentally edited a mirrored file, that edit will be discarded. Always edit the primary vault directly for content the user wants to keep.

## Failure Modes

- **Primary vault path doesn't exist** → ask the user to verify the path; offer to update the config.
- **No project path within vault** → list candidate project folders (`ls "$PRIMARY_VAULT/02 - Projects/"`) and ask which one to mirror.
- **rsync not installed** → suggest installing it via the system package manager; provide a `cp -r` fallback (without `--delete` semantics).
- **Permission denied** → check that the user owns the OneDrive sync folder and isn't blocked by a file lock.

## Output Format

After running, report:

```
Vault Sync Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Source : ~/Documents/OneDrive/obs-notes/02 - Projects/<project>
Target : vault-mirror/
Files  : N synced (M new, K updated, L deleted)
Time   : 0.4s

Notes that intersect active wiki topics:
  - <note-name> → [[wiki-topic]]
  - ...
```
