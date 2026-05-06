#!/bin/bash
# Auto-commit — debounced batch commit for research files.
# Called by research_hook.sh after file writes.
# Waits for 30s of quiet before committing all pending changes.
#
# Design: uses a "pending" file as a debounce timer. Each call resets the timer.
# A background process checks if the timer has expired and commits if so.

REPO_ROOT="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"

# Opt-in guard: require RESEARCH_TEMPLATE_AUTOCOMMIT=1 or a .autocommit.enabled marker.
# This prevents accidental commits on machines where the user only wants bookkeeping.
if [ "${RESEARCH_TEMPLATE_AUTOCOMMIT:-}" != "1" ] && [ ! -f "$REPO_ROOT/.autocommit.enabled" ]; then
    exit 0
fi

PENDING_FILE="$REPO_ROOT/.commit-pending"
LOCK_FILE="$REPO_ROOT/.commit-lock"
DEBOUNCE_SECONDS=30

# Record that a commit-worthy file was changed
mark_pending() {
    local file_path="$1"
    local ts
    ts=$(date +%s)

    echo "$ts $file_path" >> "$PENDING_FILE"

    # If no background committer is running, start one.
    if [ ! -f "$LOCK_FILE" ]; then
        touch "$LOCK_FILE"
        (
            while true; do
                sleep "$DEBOUNCE_SECONDS"

                if [ ! -f "$PENDING_FILE" ] || [ ! -s "$PENDING_FILE" ]; then
                    rm -f "$LOCK_FILE"
                    exit 0
                fi

                local last_ts now age
                last_ts=$(tail -1 "$PENDING_FILE" | cut -d' ' -f1)
                now=$(date +%s)
                age=$((now - last_ts))

                if [ "$age" -ge "$DEBOUNCE_SECONDS" ]; then
                    do_commit
                    rm -f "$PENDING_FILE" "$LOCK_FILE"
                    exit 0
                fi
                # Otherwise, loop and wait more
            done
        ) &
        disown
    fi
}

do_commit() {
    cd "$REPO_ROOT" || return

    # Collect unique changed files from pending list
    local files
    files=$(cut -d' ' -f2- "$PENDING_FILE" | sort -u)

    if [ -z "$files" ]; then
        return
    fi

    # Categorize changes for commit message
    local wiki_changes="" other_changes=""
    local wiki_count=0 other_count=0

    while IFS= read -r f; do
        [ -z "$f" ] && continue
        # Only stage files that actually have changes
        if git diff --quiet -- "$f" 2>/dev/null && \
           ! git ls-files --others --exclude-standard -- "$f" 2>/dev/null | grep -q .; then
            continue
        fi

        git add "$f" 2>/dev/null

        case "$f" in
            */wiki/*|wiki/*)
                wiki_count=$((wiki_count + 1))
                page=$(basename "$f" .md)
                wiki_changes="${wiki_changes:+$wiki_changes, }$page"
                ;;
            *)
                other_count=$((other_count + 1))
                other_changes="${other_changes:+$other_changes, }$(basename "$f")"
                ;;
        esac
    done <<< "$files"

    # Also stage events.jsonl and research-state.yaml if changed
    git add events.jsonl research-state.yaml 2>/dev/null

    # Check if there's actually anything staged
    if git diff --cached --quiet 2>/dev/null; then
        return
    fi

    # Build commit message
    local msg=""
    if [ "$wiki_count" -gt 0 ] && [ "$other_count" -eq 0 ]; then
        msg="wiki: update $wiki_changes"
    elif [ "$wiki_count" -eq 0 ] && [ "$other_count" -gt 0 ]; then
        msg="research: update $other_changes"
    elif [ "$wiki_count" -gt 0 ] && [ "$other_count" -gt 0 ]; then
        msg="research: update wiki ($wiki_changes) + $other_changes"
    else
        msg="research: auto-commit pending changes"
    fi

    # Truncate message if too long
    if [ ${#msg} -gt 72 ]; then
        msg="${msg:0:69}..."
    fi

    git commit -m "$msg

Auto-committed by research-template debounced hook." 2>/dev/null

    # Push (silently, don't block) — only if a remote is configured.
    if git remote get-url origin >/dev/null 2>&1; then
        git push origin HEAD 2>/dev/null &
        disown
    fi
}

# Entry point — called with the changed file path
if [ -n "$1" ]; then
    mark_pending "$1"
fi
