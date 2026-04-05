#!/usr/bin/env bash
# check-secrets.sh - Pre-commit hook for MultiCode
# Scans staged files for hardcoded secrets, API keys, and credentials.
#
# Usage:
#   chmod +x scripts/check-secrets.sh
#   scripts/check-secrets.sh
#
# Or as a git pre-commit hook:
#   cp scripts/check-secrets.sh .git/hooks/pre-commit

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 Scanning for secrets..."

# Files to check
if [ -n "${1:-}" ]; then
    FILES="$1"
else
    FILES=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null || find . -type f \( -name "*.py" -o -name "*.json" -o -name "*.yaml" -o -name "*.yml" -o -name "*.toml" -o -name "*.md" -o -name "*.txt" -o -name "*.cfg" -o -name "*.ini" \) -not -path "*/.git/*" -not -path "*/node_modules/*" -not -path "*/__pycache__/*" -not -path "*/.venv/*" -not -path "*/venv/*")
fi

FOUND=0

# Pattern 1: OpenRouter API keys (real ones, not placeholders)
if echo "$FILES" | xargs grep -l -E 'sk-or-v1-[A-Za-z0-9]{20,}' 2>/dev/null; then
    echo -e "${RED}❌ Found potential OpenRouter API key${NC}"
    FOUND=1
fi

# Pattern 2: Hardcoded password/secret assignments
if echo "$FILES" | xargs grep -l -E '(password|passwd|secret|api_key)\s*=\s*["\x27][^"\x27]{8,}["\x27]' 2>/dev/null | grep -v "__pycache__" | grep -v ".pyc"; then
    echo -e "${YELLOW}⚠️  Found potential hardcoded credential${NC}"
    echo -e "${YELLOW}   Verify these are not real secrets${NC}"
    # Don't fail for this one, just warn
fi

# Pattern 3: .env files
if echo "$FILES" | grep -qE '\.env(\.|$)'; then
    echo -e "${RED}❌ Found .env file - should be in .gitignore${NC}"
    FOUND=1
fi

# Pattern 4: Key/pem/crt files
if echo "$FILES" | grep -qE '\.(key|pem|crt)$'; then
    echo -e "${RED}❌ Found key/certificate file - should be in .gitignore${NC}"
    FOUND=1
fi

# Pattern 5: Bearer tokens in code
if echo "$FILES" | xargs grep -l -E 'Bearer\s+sk-[A-Za-z0-9]' 2>/dev/null; then
    echo -e "${RED}❌ Found Bearer token in code${NC}"
    FOUND=1
fi

# Pattern 6: AWS-style keys
if echo "$FILES" | xargs grep -l -E '(AKIA|ABIA|ACCA)[A-Z0-9]{16}' 2>/dev/null; then
    echo -e "${RED}❌ Found potential AWS access key${NC}"
    FOUND=1
fi

if [ "$FOUND" -eq 0 ]; then
    echo -e "${GREEN}✅ No secrets found${NC}"
    exit 0
else
    echo -e "${RED}❌ Secrets detected! Remove them before committing.${NC}"
    exit 1
fi
