# Workspace Development Environment Image
# This image provides a clean, ephemeral development environment

FROM ubuntu:22.04

LABEL maintainer="Virtual Workspace Platform"
LABEL workspace.type="ephemeral"

# Prevent interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm-256color

# Create workspace user (non-root)
RUN useradd -m -s /bin/bash developer && \
    mkdir -p /workspace && \
    chown -R developer:developer /workspace

# Install essential tools and development dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Essential utilities
    curl \
    wget \
    git \
    vim \
    nano \
    htop \
    tree \
    unzip \
    zip \
    ca-certificates \
    gnupg \
    lsb-release \
    # Build essentials
    build-essential \
    gcc \
    g++ \
    make \
    # Python
    python3 \
    python3-pip \
    python3-venv \
    # SSH client for Git
    openssh-client \
    # ttyd for web terminal
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 LTS
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install ttyd for web terminal access
RUN curl -L https://github.com/tsl0922/ttyd/releases/download/1.7.4/ttyd.x86_64 -o /usr/local/bin/ttyd && \
    chmod +x /usr/local/bin/ttyd

# Install common global npm packages
RUN npm install -g yarn pnpm typescript ts-node nodemon

# Configure Git
RUN git config --system init.defaultBranch main && \
    git config --system core.editor vim && \
    git config --system pull.rebase false

# Create welcome message
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set working directory
WORKDIR /workspace

# Switch to non-root user
USER developer

# Expose ttyd port
EXPOSE 7681

# Entry point
ENTRYPOINT ["/entrypoint.sh"]
