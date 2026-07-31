#!/bin/bash
set -e

cd "$(dirname "$0")/.."

export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

# Load secrets from .env (gitignored)
ENV_FILE="$(dirname "$0")/../.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    . "$ENV_FILE"
    set +a
fi

echo "$(date): Starting scrape..."

python3 main.py --output-dir docs --filename index

if git diff --quiet docs/ 2>/dev/null; then
    echo "$(date): No changes, skipping commit."
    exit 0
fi

git add docs/
git commit -m "Update prices $(date '+%Y-%m-%d %H:%M')"
git push origin main

echo "$(date): Done."
