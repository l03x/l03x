#!/usr/bin/env bash

set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN is not set}"
REPO="${REPO:-l03x/l03x}"
REPO_URL="${REPO_URL:-https://x-access-token:${GH_TOKEN}@github.com/${REPO}.git}"

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

git clone -q --depth 1 --branch main "$REPO_URL" "$workdir"
cd "$workdir"

python3 life.py --out life.svg

git add life.svg
if git diff --cached --quiet; then
  echo "life.svg unchanged, nothing to commit"
  exit 0
fi

git -c user.name="life-bot" -c user.email="life-bot@example.com" \
  commit -q -m "life: reseed $(date +%F)"
git push -q origin HEAD:main
echo "pushed"