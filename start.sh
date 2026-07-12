#!/bin/bash

# Newsixity Startup Script
# Starts Ollama server and Next.js dev server

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Newsixity Startup Script       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Store PIDs for cleanup
OLLAMA_PID=""
NEXT_PID=""

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down services...${NC}"

    if [ ! -z "$NEXT_PID" ]; then
        echo -e "${BLUE}→ Stopping Next.js dev server (PID: $NEXT_PID)${NC}"
        kill $NEXT_PID 2>/dev/null || true
    fi

    if [ ! -z "$OLLAMA_PID" ]; then
        echo -e "${BLUE}→ Stopping Ollama server (PID: $OLLAMA_PID)${NC}"
        kill $OLLAMA_PID 2>/dev/null || true
    fi

    echo -e "${GREEN}✓ All services stopped${NC}"
    exit 0
}

# Set up trap to catch Ctrl+C and other termination signals
trap cleanup SIGINT SIGTERM EXIT

# Check if Ollama is already running
if pgrep -x "ollama" > /dev/null; then
    echo -e "${YELLOW}⚠ Ollama is already running${NC}"
else
    echo -e "${BLUE}→ Starting Ollama server...${NC}"
    ollama serve > /dev/null 2>&1 &
    OLLAMA_PID=$!

    # Wait a moment for Ollama to start
    sleep 2

    if ps -p $OLLAMA_PID > /dev/null; then
        echo -e "${GREEN}✓ Ollama server started (PID: $OLLAMA_PID)${NC}"
    else
        echo -e "${RED}✗ Failed to start Ollama server${NC}"
        exit 1
    fi
fi

echo ""

# Clear the .next build cache if it's stale relative to the installed
# Next.js version — a mismatched cache causes RSC manifest errors
# ("Could not find the module ... in the React Client Manifest") that
# surface as HTTP 500s on every route.
INSTALLED_NEXT_VERSION=$(node -p "require('./node_modules/next/package.json').version" 2>/dev/null || echo "")
STAMP_FILE=".next/.newsixity-next-version"
if [ -d ".next" ]; then
    CACHED_NEXT_VERSION=$(cat "$STAMP_FILE" 2>/dev/null || echo "")
    if [ "$CACHED_NEXT_VERSION" != "$INSTALLED_NEXT_VERSION" ]; then
        echo -e "${YELLOW}⚠ Stale .next cache detected (built with a different Next.js version) — clearing${NC}"
        # macOS Finder can repopulate .DS_Store mid-delete, making a single
        # rm -rf report "Directory not empty" — retry a few times rather
        # than letting `set -e` abort the whole script on a transient race.
        for _ in 1 2 3; do
            rm -rf .next 2>/dev/null && break
        done
        rm -rf .next || true
    fi
fi
mkdir -p .next
echo "$INSTALLED_NEXT_VERSION" > "$STAMP_FILE"

echo -e "${BLUE}→ Starting Next.js dev server...${NC}"
npm run dev &
NEXT_PID=$!

# Wait a moment for Next.js to start
sleep 3

if ps -p $NEXT_PID > /dev/null; then
    echo -e "${GREEN}✓ Next.js dev server started (PID: $NEXT_PID)${NC}"
else
    echo -e "${RED}✗ Failed to start Next.js dev server${NC}"
    cleanup
    exit 1
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     🚀 All services running!           ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Services:${NC}"
echo -e "  ${GREEN}→${NC} Ollama:  http://localhost:11434"
echo -e "  ${GREEN}→${NC} Next.js: http://localhost:3000"
echo ""

# Open Brave browser to localhost:3000
echo -e "${BLUE}→ Opening Brave browser...${NC}"
sleep 2
open -a "Brave Browser" http://localhost:3000 2>/dev/null || \
  echo -e "${YELLOW}⚠ Could not open Brave browser (is it installed?)${NC}"

echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Wait for Next.js process (keeps script running)
wait $NEXT_PID
