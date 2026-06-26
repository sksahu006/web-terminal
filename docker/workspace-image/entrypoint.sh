#!/bin/bash

# Workspace Entry Script
# Displays welcome message and starts web terminal

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_tool_version() {
    local label="$1"
    local command_name="$2"
    shift 2

    if command -v "$command_name" >/dev/null 2>&1; then
        printf "   - %-8s %s\n" "$label:" "$($command_name "$@" 2>/dev/null | head -n 1)"
    fi
}

clear
echo -e "${GREEN}"
echo "=================================================================="
echo "              Virtual Terminal Lab"
echo "=================================================================="
echo -e "${NC}"

echo -e "${BLUE}Welcome to your ephemeral lab workspace.${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT: This workspace is disposable.${NC}"
echo "   Any files created here are lost when the lab stops."
echo ""
echo -e "${GREEN}Available tools:${NC}"
print_tool_version "ttyd" ttyd --version
print_tool_version "Tree" tree --version
print_tool_version "Curl" curl --version
print_tool_version "Wget" wget --version

echo ""
echo -e "${GREEN}Workspace:${NC} /workspace"
echo ""

# Run ttyd as a background daemon — decoupled from container TTY state
ttyd --writable --interface 0.0.0.0 -p 7681 bash &
TTYD_PID=$!
echo "ttyd started (PID $TTYD_PID)"

# Keep the container alive for exactly as long as ttyd runs
wait $TTYD_PID
echo "ttyd exited, container stopping"


