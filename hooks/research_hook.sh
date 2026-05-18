#!/bin/bash
# Research Hook — runs after Write|Edit tool use.
# Updates research-state.yaml, emits events to events.jsonl.
#
# Wired by OpenCode via the hook configuration in opencode.json (or by Claude Code
# via .claude/settings.local.json).
#
# Reads tool input as JSON on stdin. Extracts the modified file path and dispatches
# on the path pattern.
#
# NOTE: This hook does NOT commit anything. Commits are exclusively the user's
# responsibility — agents in this repo are forbidden from running `git commit`.

REPO_ROOT="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"
STATE_FILE="$REPO_ROOT/research-state.yaml"
EVENTS_FILE="$REPO_ROOT/events.jsonl"

# Read hook input from stdin (OpenCode/Claude Code feed JSON like
#   { "tool_input": { "file_path": "..." } } )
INPUT=$(cat)

# Extract the file path from the tool input. Tolerate missing fields.
FILE_PATH=$(printf '%s' "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tool_input = data.get('tool_input', {}) or data.get('input', {})
    print(tool_input.get('file_path', '') or tool_input.get('filePath', ''))
except Exception:
    print('')
" 2>/dev/null)

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Skip events.jsonl and research-state.yaml to avoid recursion.
case "$FILE_PATH" in
    */events.jsonl|*research-state.yaml)
        exit 0
        ;;
esac

TS=$(date -u +"%Y-%m-%dT%H:%M:%S")

emit_event() {
    local type="$1"
    local detail="$2"
    local source="$3"
    if [ -n "$EVENTS_FILE" ]; then
        printf '{"ts":"%s","type":"%s","detail":"%s","source":"%s"}\n' \
            "$TS" "$type" "$detail" "$source" >> "$EVENTS_FILE"
    fi
}

update_state_timestamp() {
    if [ -f "$STATE_FILE" ]; then
        # Update last_updated timestamp using python for reliable YAML editing
        python3 -c "
import sys
with open('$STATE_FILE') as f:
    lines = f.readlines()
with open('$STATE_FILE', 'w') as f:
    for line in lines:
        if line.startswith('last_updated:'):
            f.write('last_updated: \"$TS\"\n')
        else:
            f.write(line)
" 2>/dev/null
    fi
}

# --- Wiki files ---
case "$FILE_PATH" in
    */wiki/topics/*|*/wiki/concepts/*|*/wiki/groups/*|*/wiki/syntheses/*|*/wiki/queries/*|*/wiki/entities/*)
        PAGE_NAME=$(basename "$FILE_PATH" .md)
        emit_event "wiki:update" "Updated wiki page: $PAGE_NAME" "hook"
        update_state_timestamp
        echo "[Research Hook] Wiki page '$PAGE_NAME' updated."
        exit 0
        ;;
esac

# --- Research evaluations ---
case "$FILE_PATH" in
    */wiki/research-evaluations/*.md)
        DOC_NAME=$(basename "$FILE_PATH" .md)
        emit_event "research_evaluation:save" "Saved evaluation: $DOC_NAME" "hook"
        update_state_timestamp
        echo "[Research Hook] Research evaluation '$DOC_NAME' saved. Will surface in next research-session briefing."
        exit 0
        ;;
esac

# --- Wiki index/log (no suggestion, just track) ---
case "$FILE_PATH" in
    */wiki/index.md|*/wiki/log.md|*/wiki/wiki.schema.md)
        update_state_timestamp
        exit 0
        ;;
esac

# --- Vault-mirror files: read-only mirror, do nothing ---
case "$FILE_PATH" in
    */vault-mirror/*)
        # Mirror files are managed by hooks/vault_sync.sh and are read-only.
        echo "[Research Hook] vault-mirror file touched — note: vault-mirror is read-only. Edits will be lost on next sync."
        exit 0
        ;;
esac

# --- Snakemake outputs: track but don't commit (build artifacts gitignored) ---
case "$FILE_PATH" in
    */build/*|*/.snakemake/*)
        exit 0
        ;;
esac

# --- Experiment results / data ---
case "$FILE_PATH" in
    */data/results/*|*/data/processed/*)
        EXPERIMENT=$(basename "$(dirname "$FILE_PATH")")
        emit_event "experiment:update" "Experiment data updated: $EXPERIMENT" "hook"
        update_state_timestamp
        echo "[Research Hook] Experiment '$EXPERIMENT' data updated. Consider updating wiki with new findings."
        exit 0
        ;;
esac

# --- Manuscript / report drafts ---
case "$FILE_PATH" in
    */report/*.md|*/manuscript/*.tex|*paper_draft*|*draft*)
        DOC_NAME=$(basename "$FILE_PATH")
        emit_event "writing:edit" "Edited: $DOC_NAME" "hook"
        update_state_timestamp
        echo "[Research Hook] Draft '$DOC_NAME' edited."
        exit 0
        ;;
esac

# --- Configuration files (Snakemake, opencode, etc.) ---
case "$FILE_PATH" in
    */config/*.yaml|*/Snakefile|*/rules/*.smk|*/envs/*.yaml|*/profiles/*/config.yaml|*/opencode.json|*/AGENTS.md)
        emit_event "config:edit" "Edited config: $(basename "$FILE_PATH")" "hook"
        update_state_timestamp
        exit 0
        ;;
esac

# --- Other markdown / docs (lighter touch) ---
case "$FILE_PATH" in
    */wiki/meta/*|*.md)
        emit_event "docs:edit" "Edited: $(basename "$FILE_PATH")" "hook"
        update_state_timestamp
        exit 0
        ;;
esac

# --- Everything else: no action ---
exit 0
