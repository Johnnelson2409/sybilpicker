#!/bin/bash
set -e
SCRIPT="scripts/score.sh"
bash "$SCRIPT" --help >/dev/null
if bash "$SCRIPT --demo" | grep -q "CRITICAL\|HIGH"; then
  echo "OK: demo"
else
  echo "FAIL"; exit 1
fi
echo "All passed."
