#!/bin/bash
# Research Template — Setup Script
#
# Usage:
#   ./setup.sh          # interactive wizard: customise this clone for a specific project
#   ./setup.sh --check  # report what would change without writing anything
#
# Run this AFTER cloning the template. It:
#   - Asks for project metadata (name, short_name, author, institute, primary vault path)
#   - Substitutes placeholders in research-state.yaml and report/preamble.tex
#   - Updates pixi.toml with project short name
#   - Optionally configures vault_sync (path to primary Obsidian vault + project sub-path)
#   - Optionally enables auto-commit (touches .autocommit.enabled)
#   - Initialises a fresh git repo if one isn't already present
#   - Automatically runs `pixi install` to set up the project environment

set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
CHECK_ONLY=0
if [ "${1:-}" = "--check" ]; then
    CHECK_ONLY=1
fi

# --- Helpers ---------------------------------------------------------------

info()    { printf "  [ok] %s\n" "$1"; }
action()  { printf "  [+]  %s\n" "$1"; }
warn()    { printf "  [!]  %s\n" "$1"; }
bold()    { printf "\033[1m%s\033[0m\n" "$1"; }

prompt() {
    local question="$1" default="$2" answer
    if [ -n "$default" ]; then
        printf "  %s [%s]: " "$question" "$default" >&2
    else
        printf "  %s: " "$question" >&2
    fi
    read -r answer
    echo "${answer:-$default}"
}

confirm() {
    local question="$1" default="${2:-N}" answer
    printf "  %s (y/N): " "$question" >&2
    read -r answer
    answer="${answer:-$default}"
    case "$answer" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

run_or_check() {
    if [ "$CHECK_ONLY" -eq 1 ]; then
        echo "  [check] would run: $*"
    else
        "$@"
    fi
}

# --- Wizard ----------------------------------------------------------------

bold "Research Template — setup wizard"
echo "Customise this clone for your project. Re-runnable; safe to skip with Ctrl-C."
echo ""

PROJECT_NAME=$(prompt "Project name (human-readable)" "My Research Project")
PROJECT_SHORT_NAME=$(prompt "Project short name (kebab-case, used in pixi project name)" "my-research-project")
AUTHOR=$(prompt "Author name" "$USER")
INSTITUTE=$(prompt "Institute" "Your Institute")
SHORT_DESCRIPTION=$(prompt "Short description (one line)" "A reproducible research project.")
DOMAIN=$(prompt "Research domain (one-line descriptor; freeform)" "research")
echo ""

# --- Vault sync configuration ---------------------------------------------

bold "Primary Obsidian vault sync (optional)"
PRIMARY_VAULT=""
PROJECT_PATH_IN_VAULT=""
if confirm "Configure vault-sync from a primary Obsidian vault?"; then
    PRIMARY_VAULT=$(prompt "Primary vault absolute path" "$HOME/Documents/OneDrive/obs-notes")
    PROJECT_PATH_IN_VAULT=$(prompt "Project sub-path within the vault (e.g. '02 - Projects/MyProject')" "")
fi
echo ""

# --- Auto-commit -----------------------------------------------------------

WANT_AUTOCOMMIT="no"
if confirm "Enable auto-commit? (debounced, 30s quiet period; touches .autocommit.enabled)"; then
    WANT_AUTOCOMMIT="yes"
fi
echo ""

# --- Apply -----------------------------------------------------------------

bold "Applying configuration..."

# 1. research-state.yaml
STATE_FILE="$REPO_ROOT/research-state.yaml"
if [ -f "$STATE_FILE" ]; then
    if [ "$CHECK_ONLY" -eq 0 ]; then
        python3 - <<EOF
import sys
try:
    import yaml
except Exception:
    print("[setup] PyYAML missing — install via 'pip install pyyaml'. Skipping state file rewrite.")
    sys.exit(0)
try:
    with open("$STATE_FILE") as f:
        data = yaml.safe_load(f) or {}
except Exception as e:
    print(f"[setup] could not load state: {e}")
    sys.exit(0)
data["domain"] = "$DOMAIN"
data["project_short_name"] = "$PROJECT_SHORT_NAME"
data["institute"] = "$INSTITUTE"
data["description"] = "$SHORT_DESCRIPTION"
if "$PRIMARY_VAULT" and "$PROJECT_PATH_IN_VAULT":
    data.setdefault("vault_sync", {})
    data["vault_sync"]["primary_vault"] = "$PRIMARY_VAULT"
    data["vault_sync"]["project_path_in_vault"] = "$PROJECT_PATH_IN_VAULT"
    data["vault_sync"]["mirror_target"] = "vault-mirror"
with open("$STATE_FILE", "w") as f:
    yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
EOF
        action "research-state.yaml updated (domain, project_short_name, institute, description${PRIMARY_VAULT:+, vault_sync})"
    else
        echo "  [check] would update research-state.yaml: domain, project_short_name, institute, description${PRIMARY_VAULT:+, vault_sync}"
    fi
fi

# 2. pixi.toml — substitute pixi project name
PIXI_FILE="$REPO_ROOT/pixi.toml"
if [ -f "$PIXI_FILE" ] && [ "$CHECK_ONLY" -eq 0 ]; then
    sed -i.bak "s|^name = \"research-template\"|name = \"$PROJECT_SHORT_NAME\"|" "$PIXI_FILE" && rm -f "$PIXI_FILE.bak"
    action "pixi.toml: name -> $PROJECT_SHORT_NAME"
elif [ -f "$PIXI_FILE" ]; then
    echo "  [check] would update pixi.toml: name -> $PROJECT_SHORT_NAME"
fi

# 3. report/preamble.tex — substitute title and author
# Pass values via env vars to avoid shell-quoting hell with LaTeX backslashes.
PREAMBLE_FILE="$REPO_ROOT/report/preamble.tex"
if [ -f "$PREAMBLE_FILE" ] && [ "$CHECK_ONLY" -eq 0 ]; then
    PREAMBLE_FILE="$PREAMBLE_FILE" \
    PROJECT_NAME="$PROJECT_NAME" \
    AUTHOR="$AUTHOR" \
    python3 - <<'PYEOF'
import os, re
path = os.environ["PREAMBLE_FILE"]
project_name = os.environ["PROJECT_NAME"]
author = os.environ["AUTHOR"]
with open(path) as f:
    text = f.read()
# Replace \title{...} and \author{...}; use lambdas to avoid backref interpretation.
text = re.sub(r"\\title\{[^}]*\}", lambda _m: r"\title{" + project_name + "}", text, count=1)
text = re.sub(r"\\author\{[^}]*\}", lambda _m: r"\author{" + author + "}", text, count=1)
with open(path, "w") as f:
    f.write(text)
PYEOF
    action "report/preamble.tex: title, author"
elif [ -f "$PREAMBLE_FILE" ]; then
    echo "  [check] would update report/preamble.tex: title, author"
fi
# Note: abstract lives in main.tex as a placeholder; user customises post-setup.
# Institute and short description are stored in research-state.yaml for skills
# to consume. The default LaTeX article class has no native \institute — add a
# custom command in preamble.tex if you want it on the title page.

# 4. Auto-commit marker
if [ "$WANT_AUTOCOMMIT" = "yes" ] && [ "$CHECK_ONLY" -eq 0 ]; then
    touch "$REPO_ROOT/.autocommit.enabled"
    action "auto-commit enabled (.autocommit.enabled marker created)"
fi

# 5. Initialise git if not already
if [ ! -d "$REPO_ROOT/.git" ] && [ "$CHECK_ONLY" -eq 0 ]; then
    if confirm "Initialise a fresh git repo here?"; then
        run_or_check git -C "$REPO_ROOT" init
        run_or_check git -C "$REPO_ROOT" add .
        run_or_check git -C "$REPO_ROOT" commit -m "chore: bootstrap research-template for $PROJECT_NAME"
        action "git initialised"
    fi
fi

# 6. Run vault-sync once if configured
if [ -n "$PRIMARY_VAULT" ] && [ -n "$PROJECT_PATH_IN_VAULT" ] && [ "$CHECK_ONLY" -eq 0 ]; then
    if confirm "Run an initial vault-sync now?"; then
        bash "$REPO_ROOT/hooks/vault_sync.sh" || warn "vault-sync exited with non-zero status"
    fi
fi

echo ""
bold "Done."
echo ""
echo "Next steps:"
echo "  1. Inspect research-state.yaml and report/preamble.tex — adjust if needed."
echo "  2. pixi will auto-install environments when you run snakemake (no manual activation needed!)."
echo "  3. Run the demo pipeline:  pixi run --environment default snakemake --use-pixi --cores 4"
echo "  4. Or, activate pixi shell: pixi shell --environment default"
echo "  5. Open in OpenCode and start a conversation — the research-session skill will activate on greetings."
echo ""
if [ -z "$PRIMARY_VAULT" ]; then
    echo "  Vault-sync is not configured. To enable later, edit research-state.yaml and add the vault_sync block, then run \`bash hooks/vault_sync.sh\`."
fi
