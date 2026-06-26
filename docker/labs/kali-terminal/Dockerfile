# Lightweight Kali Linux terminal lab image
# Minimal toolset — add more tools per-lab as needed

FROM kalilinux/kali-rolling

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm-256color

# Minimal Kali tools + ttyd (available in Kali repos)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ttyd \
        bash \
        curl \
        wget \
        nmap \
        netcat-traditional \
        python3 \
        iputils-ping \
        dnsutils \
        less \
        nano \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Non-root hacker user
RUN useradd -m -s /bin/bash hacker \
    && mkdir -p /workspace \
    && chown -R hacker:hacker /workspace

COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

WORKDIR /workspace
USER hacker

EXPOSE 7681
ENTRYPOINT ["/entrypoint.sh"]
