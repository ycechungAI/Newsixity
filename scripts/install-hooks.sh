#!/bin/sh
# Installs git hooks for this repository.
# Run once after cloning: sh scripts/install-hooks.sh

HOOK=".git/hooks/pre-commit"

cat > "$HOOK" << 'EOF'
#!/bin/sh
# Auto-linter pre-commit hook.
# Runs ESLint on staged TypeScript/JavaScript files before every commit.
# To bypass in an emergency: git commit --no-verify

echo "Running linter..."
npm run lint
STATUS=$?

if [ $STATUS -ne 0 ]; then
  echo ""
  echo "Lint failed. Run 'npm run lint:fix' to auto-fix, then re-stage and commit."
  exit 1
fi

exit 0
EOF

chmod +x "$HOOK"
echo "Pre-commit lint hook installed at $HOOK"
