#!/usr/bin/env bash
# oh-my-wiki one-line installer:  curl -fsSL <raw>/bin/omw-install.sh | bash
# Installs the omw CLI, then auto-launches the setup wizard. Re-run `omw setup`
# anytime to (re)configure.
set -euo pipefail

REPO="${OMW_REPO:-git+https://github.com/dandacompany/oh-my-wiki}"

echo "[omw-install] installing the omw CLI..."
if command -v pipx >/dev/null 2>&1; then
    pipx install --force "${REPO}"
elif command -v python3 >/dev/null 2>&1; then
    python3 -m pip install --user --upgrade "${REPO}" \
      || python3 -m pip install --user --break-system-packages --upgrade "${REPO}"
else
    echo "[omw-install] need python3 (and ideally pipx). Aborting." >&2
    exit 1
fi

if ! command -v omw >/dev/null 2>&1; then
    echo "[omw-install] 'omw' is not on PATH yet. Add your user bin dir to PATH, then run: omw setup" >&2
    exit 0
fi

echo "[omw-install] configuring omw..."
if [ -t 0 ]; then
    omw setup || true                       # interactive terminal → wizard prompts
else
    omw setup --noninteractive || true       # piped install → create a default vault
    echo "[omw-install] a default vault was created. Run 'omw setup' in a terminal to customize (vault, search providers, ...)."
fi
echo "[omw-install] done. Next: open Claude Code and use the omw skill for wiki work."
