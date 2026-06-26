# Ultra-lightweight browser desktop
# Uses Alpine Linux for minimal footprint

FROM alpine:3.20

ENV DISPLAY=:1
ENV VNC_PORT=5901
ENV NOVNC_PORT=6080
ENV RESOLUTION=1280x720x24

# Install Xvfb, Fluxbox, x11vnc, noVNC, and a lightweight browser (Chromium/Firefox)
# We use Chromium on Alpine as it tends to have fewer heavy dependencies than Firefox
RUN apk add --no-cache \
    xvfb \
    fluxbox \
    x11vnc \
    novnc \
    websockify \
    chromium \
    bash \
    curl \
    wget \
    font-terminus \
    font-dejavu \
    font-noto \
    setxkbmap \
    xsetroot

# Create non-root user
RUN addgroup -S student && adduser -S -G student -s /bin/bash student \
    && mkdir -p /workspace \
    && chown -R student:student /workspace

COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

WORKDIR /workspace
USER student

EXPOSE 6080

ENTRYPOINT ["/entrypoint.sh"]
