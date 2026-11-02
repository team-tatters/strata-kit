# Container for a clean RED (MB-strata-kit-2026-002, order 2026.10.31-04): nothing of the host's Claude setup is
# inside — no user CLAUDE.md, no memory, no plugins or skills, no STRATA_* variables — and the fixture lives at /work,
# so no path names strata-kit. Login comes from CLAUDE_CODE_OAUTH_TOKEN at run time; no credential is baked in.
FROM node:22-slim
ARG CLAUDE_CODE_VERSION=2.1.314
RUN apt-get update && apt-get install -y --no-install-recommends git python3 ca-certificates && rm -rf /var/lib/apt/lists/* \
 && npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION} \
 && useradd -m runner
USER runner
RUN git config --global user.name eval && git config --global user.email eval@example.invalid
WORKDIR /work
