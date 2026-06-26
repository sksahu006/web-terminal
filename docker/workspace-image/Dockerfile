# Lean terminal lab image — Alpine-based for broad compatibility
# Uses Alpine's ttyd package (avoids segfault from GitHub pre-built binary on Docker Desktop)

FROM alpine:3.20

LABEL maintainer="Virtual Workspace Platform"
LABEL workspace.type="ephemeral-terminal-lab"

ENV TERM=xterm-256color

# Install tools + ttyd from Alpine community repository
RUN apk add --no-cache \
        bash \
        ca-certificates \
        curl \
        wget \
        tree \
        nano \
        less \
        netcat-openbsd \
        ttyd \
    && addgroup -S developer \
    && adduser -S -G developer -s /bin/bash -h /home/developer developer \
    && mkdir -p /workspace \
    && chown -R developer:developer /workspace

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /workspace
USER developer

EXPOSE 7681
ENTRYPOINT ["/entrypoint.sh"]
