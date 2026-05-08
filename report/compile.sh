#!/bin/bash
# compile.sh — Local LaTeX compile + view workflow
# Usage: ./compile.sh [-f]
# -f : force clean rebuild
#
# Output: ../build/report.pdf (matches the Snakemake pipeline output naming).

set -e

cd "$(dirname "$0")"
src="main"          # source TeX file (without extension)
out="report"        # final PDF name (matches pipeline output)

if [ "${1}" == "-f" ]; then
  echo "Force clean rebuild..."
  latexmk -c
  latexmk -pdf -f "${src}.tex"
else
  latexmk -pdf "${src}.tex"
fi

# Rename latexmk's output (build/main.pdf) to match pipeline (build/report.pdf).
if [ -f "../build/${src}.pdf" ]; then
  mv "../build/${src}.pdf" "../build/${out}.pdf"
fi

# Check if zathura is running
if pgrep -x "zathura" >/dev/null; then
  echo "zathura is running; it will auto-refresh the open document."
  # Optional: focus the zathura window (Hyprland-specific; harmless elsewhere).
  hyprctl dispatch focuswindow "class:org.pwmt.zathura" 2>/dev/null || true
else
  echo "zathura not running, opening new instance..."
  nohup zathura "../build/${out}.pdf" >/dev/null 2>&1 &
  sleep 0.3
fi
