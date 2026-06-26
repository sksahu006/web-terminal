#!/bin/bash

# Browser Desktop Lab Entry Script

echo "Starting Virtual Display (Xvfb) on $DISPLAY..."
Xvfb $DISPLAY -screen 0 $RESOLUTION -ac -nolisten tcp &
XVFB_PID=$!

# Wait for X server to be ready
# Alpine uses xset to check if the server is up since xdpyinfo isn't installed by default
while ! xset -q >/dev/null 2>&1; do
  sleep 0.1
done

echo "Starting Window Manager (Fluxbox)..."
fluxbox >/dev/null 2>&1 &

# Set background color to dark grey
xsetroot -solid "#2c3e50"

echo "Starting Chromium Browser..."
# Chromium requires --no-sandbox because it's running inside a Docker container without extra privileges
chromium-browser --no-sandbox --disable-dev-shm-usage --start-maximized >/dev/null 2>&1 &

echo "Starting VNC Server (x11vnc) on port $VNC_PORT..."
x11vnc -display $DISPLAY -nopw -forever -shared -bg -quiet -rfbport $VNC_PORT

echo "Starting noVNC (Web VNC client) on port $NOVNC_PORT..."
websockify --web=/usr/share/novnc/ $NOVNC_PORT localhost:$VNC_PORT &
WEBSOCKIFY_PID=$!

echo "Desktop environment is ready and listening on port $NOVNC_PORT"

# Keep container alive by waiting for the noVNC bridge
wait $WEBSOCKIFY_PID
echo "noVNC exited, container stopping"
