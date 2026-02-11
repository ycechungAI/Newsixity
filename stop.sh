#!/bin/bash

# Newsixity Stop Script
# Stops Ollama server and Next.js dev server

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${RED}Stopping Newsixity services...${NC}"
echo ""

# Stop Next.js dev server
if pgrep -f "next dev" > /dev/null; then
    echo -e "${BLUE}→ Stopping Next.js dev server${NC}"
    pkill -f "next dev"
    echo -e "${GREEN}✓ Next.js stopped${NC}"
else
    echo -e "${YELLOW}⚠ Next.js is not running${NC}"
fi

# Stop Ollama server
if pgrep -x "ollama" > /dev/null; then
    echo -e "${BLUE}→ Stopping Ollama server${NC}"
    pkill -x "ollama"
    echo -e "${GREEN}✓ Ollama stopped${NC}"
else
    echo -e "${YELLOW}⚠ Ollama is not running${NC}"
fi

echo ""
echo -e "${GREEN}All services stopped${NC}"
