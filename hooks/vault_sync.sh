#!/bin/bash
# Vault Sync — one-way replication of project notes from the primary Obsidian vault
# into this repo's vault-mirror/ directory.
#
# Reads configuration from research-state.yaml under the `vault_sync:` key. If the
# config is missing or incomplete, falls back to environment variables:
#   PRIMARY_VAULT          (default: $HOME/Documents/OneDrive/obs-notes)
#   PROJECT_PATH_IN_VAULT  (e.g. "02 - Projects/GREAT")
#   MIRROR_TARGET          (default: vault-mirror)
#
# Usage:
#   bash hooks/vault_sync.sh           # reads config from state file
#   bash hooks/vault_sync.sh --check   # report drift without syncing
#
# Requires: rsync, python3.

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"
STATE_FILE="$REPO_ROOT/research-state.yaml"
EVENTS_FILE="$REPO_ROOT/events.jsonl"

CHECK_ONLY=0
if [ "${1:-}" = "--check" ]; then
    CHECK_ONLY=1
fi

# --- Load config -----------------------------------------------------------

read_state_value() {
    local key="$1"
    [ ! -f "$STATE_FILE" ] && return
    python3 - <<EOF 2>/dev/null
import sys
try:
    import yaml
except Exception:
    print("", end="")
    sys.exit(0)
try:
    with open("$STATE_FILE") as f:
        data = yaml.safe_load(f) or {}
    cfg = data.get("vault_sync", {}) or {}
    val = cfg.get("$key", "") or ""
    print(val, end="")
except Exception:
    print("", end="")
EOF
}

PRIMARY_VAULT="${PRIMARY_VAULT:-$(read_state_value primary_vault)}"
PRIMARY_VAULT="${PRIMARY_VAULT:-$HOME/Documents/OneDrive/obs-notes}"
PRIMARY_VAULT="${PRIMARY_VAULT/#\~/$HOME}"

PROJECT_PATH_IN_VAULT="${PROJECT_PATH_IN_VAULT:-$(read_state_value project_path_in_vault)}"
MIRROR_TARGET="${MIRROR_TARGET:-$(read_state_value mirror_target)}"
MIRROR_TARGET="${MIRROR_TARGET:-vault-mirror}"

if [ -z "$PROJECT_PATH_IN_VAULT" ]; then
    echo "[vault-sync] No project_path_in_vault configured."
    echo "[vault-sync] Edit research-state.yaml and add:"
    echo ""
    echo "    vault_sync:"
    echo "      primary_vault: \"$PRIMARY_VAULT\""
    echo "      project_path_in_vault: \"02 - Projects/<project-name>\""
    echo "      mirror_target: \"vault-mirror\""
    echo ""
    echo "[vault-sync] Or set the PROJECT_PATH_IN_VAULT environment variable and re-run."
    exit 1
fi

SOURCE="$PRIMARY_VAULT/$PROJECT_PATH_IN_VAULT"
TARGET="$REPO_ROOT/$MIRROR_TARGET"

if [ ! -d "$SOURCE" ]; then
    echo "[vault-sync] ERROR: source does not exist: $SOURCE"
    exit 1
fi

mkdir -p "$TARGET"

# --- Run sync --------------------------------------------------------------

if ! command -v rsync >/dev/null 2>&1; then
    echo "[vault-sync] ERROR: rsync not installed."
    echo "[vault-sync] Install via your package manager (e.g. \`pacman -S rsync\` or \`apt install rsync\`)."
    exit 1
fi

RSYNC_FLAGS=(-a --delete \
    --exclude=".obsidian" \
    --exclude=".trash" \
    --exclude="Attachments" \
    --exclude="*.canvas" \
    --exclude="README.md" \
    --exclude=".gitkeep")

if [ "$CHECK_ONLY" -eq 1 ]; then
    RSYNC_FLAGS+=(--dry-run --itemize-changes)
fi

START_TS=$(date +%s)
echo "[vault-sync] Source : $SOURCE"
echo "[vault-sync] Target : $TARGET"
echo "[vault-sync] Mode   : $([ $CHECK_ONLY -eq 1 ] && echo 'dry-run (--check)' || echo 'live sync')"
echo ""

# Note the trailing slashes — rsync treats them carefully.
rsync "${RSYNC_FLAGS[@]}" "$SOURCE/" "$TARGET/"
RC=$?
END_TS=$(date +%s)
DURATION=$((END_TS - START_TS))

if [ "$CHECK_ONLY" -eq 1 ]; then
    echo ""
    echo "[vault-sync] Dry-run complete. Re-run without --check to apply."
    exit 0
fi

# --- Update state and emit event -----------------------------------------

TS=$(date -u +"%Y-%m-%dT%H:%M:%S")

# Append last-sync timestamp into the vault_sync block of research-state.yaml.
python3 - <<EOF 2>/dev/null
try:
    import yaml
    with open("$STATE_FILE") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("vault_sync", {})
    data["vault_sync"]["last_sync_at"] = "$TS"
    with open("$STATE_FILE", "w") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
except Exception:
    pass
EOF

NUM_FILES=$(find "$TARGET" -type f 2>/dev/null | wc -l | tr -d ' ')

printf '{"ts":"%s","type":"vault:sync","detail":"Synced %s files from %s","source":"vault-sync"}\n' \
    "$TS" "$NUM_FILES" "$PROJECT_PATH_IN_VAULT" >> "$EVENTS_FILE"

echo ""
echo "[vault-sync] Sync complete."
echo "[vault-sync] Files in mirror: $NUM_FILES"
echo "[vault-sync] Duration: ${DURATION}s"

exit "$RC"
