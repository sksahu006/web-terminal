#!/bin/bash

# Kali Terminal Lab Entry Script

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

clear
echo -e "${RED}"
echo "=================================================================="
echo "              Kali Linux Terminal Lab"
echo "=================================================================="
echo -e "${NC}"

echo -e "${BLUE}Welcome to your Kali Linux lab environment.${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT: This workspace is disposable.${NC}"
echo "   Any files created here are lost when the lab stops."
echo ""
echo -e "${GREEN}Available tools:${NC}"
echo "   - nmap, netcat, curl, wget, python3, ping, dig"
echo ""
echo -e "${GREEN}Workspace:${NC} /workspace"
echo ""

# Start ttyd as background daemon (same pattern as workspace-dev)
ttyd --writable --interface 0.0.0.0 -p 7681 bash &
TTYD_PID=$!
echo "ttyd started (PID $TTYD_PID)"

wait $TTYD_PID
echo "ttyd exited, container stopping"
