#!/usr/bin/env bash
# oh-my-wiki — uninstaller
#
# Removes the skill symlinks from ~/.claude/skills/ and (optionally) uninstalls
# the Python package. Does NOT delete your vaults or the registry database.
#
# Usage:
#   bash bin/uninstall.sh                  # remove symlinks, keep pip package
#   bash bin/uninstall.sh --pip            # also pip uninstall oh-my-wiki
#   bash bin/uninstall.sh --skills-dir <path>   # override ~/.claude/skills/
#   bash bin/uninstall.sh --quiet          # no per-step output

set -euo pipefail

REMOVE_PIP=0
SKILLS_DIR="${HOME}/.claude/skills"
QUIET=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pip)         REMOVE_PIP=1 ; shift ;;
    --skills-dir)  SKILLS_DIR="$2" ; shift 2 ;;
    --quiet)       QUIET=1 ; shift ;;
    -h|--help)
      sed -n '2,15p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

log() { [[ "$QUIET" -eq 1 ]] || echo "$@"; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

unlink_one() {
  local name="$1"
  local link="${SKILLS_DIR}/${name}"
  if [[ -L "$link" ]]; then
    rm "$link"
    log "    ✅ removed symlink ${link}"
  elif [[ -e "$link" ]]; then
    log "    ⚠️  ${link} exists but is not a symlink — left in place"
  else
    log "    (no symlink at ${link})"
  fi
}

log "==> Removing skill symlinks under ${SKILLS_DIR}"
unlink_one "oh-my-wiki"
unlink_one "omw"

if [[ "$REMOVE_PIP" -eq 1 ]]; then
  log "==> pip uninstall oh-my-wiki"
  python3 -m pip uninstall -y oh-my-wiki >/dev/null
  log "    ✅ pip package removed"
else
  log "==> Pip package left installed (use --pip to remove)"
fi

log ""
log "   Uninstalled. Your vaults and data/registry.db are untouched."
log "   To fully remove the project: rm -rf ${REPO_ROOT}"
log "   To reinstall: bash ${REPO_ROOT}/bin/install.sh"
