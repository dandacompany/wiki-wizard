# oh-my-wiki v2.3 reference Docker image
# Provides: tmux + python3 + git + ripgrep + node (for claude-code and opencode-ai)
# codex and gemini CLIs are user-installed (see README -- their distribution varies)
FROM node:22-bookworm-slim

RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
      tmux \
      python3 \
      python3-pip \
      python3-venv \
      git \
      ripgrep \
      curl \
      ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Node-distributed AI backends
RUN npm install -g @anthropic-ai/claude-code opencode-ai

# NOTE: codex and gemini CLIs are not installed here.
# Their distribution changes frequently. Add your own RUN step:
#   RUN npm install -g @openai/codex
#   RUN pip3 install google-generativeai   (or whichever package Google publishes)
# OMW will detect whichever backends are present at runtime.

WORKDIR /app
COPY . /app/

# Install Python deps (no third-party runtime deps; this covers dev/test extras)
RUN python3 -m pip install --no-cache-dir -e ".[dev]" 2>/dev/null || \
    python3 -m pip install --no-cache-dir pytest ruff

# Non-root user for runtime safety
RUN useradd -ms /bin/bash omwuser
USER omwuser
WORKDIR /home/omwuser

CMD ["/bin/bash"]
