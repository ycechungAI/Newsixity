#!/bin/bash
set -e

# Newsixity test script — runs backend pytest suite

echo "🧪 Running Newsixity tests..."
echo ""

# Check if we're in the right directory
if [ ! -f "backend/pytest.ini" ]; then
    echo "❌ Error: backend/pytest.ini not found. Run this from the repo root."
    exit 1
fi

# Run all backend tests
echo "📚 Running backend tests (pytest)..."
python -m pytest backend/tests/ -v --tb=short

echo ""
echo "✅ All tests passed!"
