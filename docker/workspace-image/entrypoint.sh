#!/bin/bash

# Workspace Entry Script
# Displays welcome message and starts web terminal

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print welcome message
clear
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                                                                  ║"
echo "║           🚀 Virtual Workspace Platform                          ║"
echo "║                                                                  ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${BLUE}Welcome to your ephemeral development workspace!${NC}"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT: This workspace is EPHEMERAL${NC}"
echo "   All changes will be lost when the workspace stops."
echo "   Make sure to push your code to GitHub before stopping!"
echo ""
echo -e "${GREEN}📋 Quick Start Guide:${NC}"
echo "   1. Clone your repository:"
echo "      git clone https://github.com/username/repo.git"
echo ""
echo "   2. Make your changes"
echo ""
echo "   3. Before stopping, push your changes:"
echo "      git add . && git commit -m 'message' && git push"
echo ""
echo -e "${BLUE}🛠️  Available Tools:${NC}"
echo "   • Git:     $(git --version)"
echo "   • Python:  $(python3 --version)"
echo "   • Node.js: $(node --version)"
echo "   • npm:     $(npm --version)"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Configure Git with GitHub token if provided
if [ -n "$GITHUB_TOKEN" ]; then
    git config --global credential.helper store
    echo "https://oauth2:${GITHUB_TOKEN}@github.com" > ~/.git-credentials
    chmod 600 ~/.git-credentials
    echo -e "${GREEN}✅ GitHub authentication configured${NC}"
    echo ""
fi

# Start ttyd web terminal
exec ttyd -W -p 7681 bash
