# oh-my-wiki E2E test image: Claude Code (node) + omw (python) + tmux, for the
# Docker-based end-to-end harness. See tests/e2e/README.md.
#
# Build from the REPO ROOT so the whole source tree is in context:
#   docker build -f tests/e2e/Dockerfile -t omw-e2e .
FROM node:22-bookworm-slim

# System deps: python (PEP 668 → we use a venv), tmux for interactive driving,
# git/jq/curl/procps for the harness, ca-certificates for TLS (Claude OAuth, MCP).
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv python3-pip \
        git tmux jq curl ca-certificates procps less \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI (the host agent under test).
RUN npm install -g @anthropic-ai/claude-code

# omw source (build context = repo root; .dockerignore trims .venv/.git/data/docs).
COPY . /opt/oh-my-wiki

# Editable install inside a venv to avoid the bookworm externally-managed error.
# Putting the venv first on PATH makes `python3 -m scripts.X` resolve to it,
# which is what the omw skill's command snippets invoke.
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -e /opt/oh-my-wiki
ENV PATH="/opt/venv/bin:${PATH}"

# The omw skill's command snippets hardcode `python3`. Non-interactive shells
# (`bash -c`, as Claude Code spawns) inherit this ENV PATH → venv first → fine.
# But a login shell (`bash -l`) resets PATH from /etc/profile and drops the venv,
# so `python3` would fall back to the system interpreter that can't import
# `scripts`. A /usr/local/bin symlink does NOT fix this (Python's venv detection
# looks for pyvenv.cfg next to the *symlink* path and fails). The correct fix is
# to prepend the venv on the login-shell PATH via /etc/profile.d.
RUN printf 'export PATH=/opt/venv/bin:$PATH\n' > /etc/profile.d/omw-venv.sh \
    && chmod 0644 /etc/profile.d/omw-venv.sh

# Isolated OMW home (dogfoods the OMW_HOME override; never touches a real ~/.omw).
ENV OMW_HOME=/work/.omw
RUN mkdir -p /work

# Entrypoint installs the omw skill into ~/.claude/skills at container start
# (after any volume mount), then execs the requested command.
RUN cp /opt/oh-my-wiki/tests/e2e/entrypoint.sh /usr/local/bin/omw-entrypoint \
    && chmod +x /usr/local/bin/omw-entrypoint
WORKDIR /work
ENTRYPOINT ["/usr/local/bin/omw-entrypoint"]
CMD ["bash"]
