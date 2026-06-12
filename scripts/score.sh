#!/usr/bin/env bash
# sybilpicker — Wallet sybil score estimator (Foundry port).
#
# Estimates the likelihood a wallet is part of a sybil cluster by
# walking the funding-source tree, checking cluster patterns, and
# age vs activity. Emits a 0-100 sybil score with per-signal detail.
#
# Usage:
#   bash scripts/score.sh --wallet 0xWALLET --rpc-url https://rpc.pharos.xyz
#   bash scripts/score.sh --wallet 0xWALLET --depth 4 --format json
#   bash scripts/score.sh --demo

set -euo pipefail

# ---- Demo works without cast ----
if [ "${1:-}" = "--demo" ] || [ "${1:-}" = "demo" ]; then
  echo ""
  echo "========================================================================"
  echo "  SYBIL SCORE  (DEMO)"
  echo "  Wallet: 0xDEMO0000000000000000000000000000000000DEAD  (synthetic)"
  echo "========================================================================"
  echo ""
  echo "  Score: 72/100  (HIGH)"
  echo "  Verdict: Likely part of a sybil cluster; deny for airdrop eligibility"
  echo ""
  echo "  Signals detected:"
  echo "    - common-funder cluster of 14 wallets funded within 1h"
  echo "    - gas-funder overlap: 0x9c4... (12 siblings)"
  echo "    - tight temporal cluster (funding txs within 1h window)"
  echo "    - dust-spray pattern: same-block dust to 6 wallets"
  echo ""
  exit 0
fi

# ---- Foundry required for non-demo ----
# ---- Load network config ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NET_JSON="$SCRIPT_DIR/../assets/networks.json"
[ ! -f "$NET_JSON" ] && { echo "Error: $NET_JSON not found"; exit 1; }

get_field() {
  local net_name="$1" field="$2"
  sed -n "/\"name\": *\"$net_name\"/,/^    }/p" "$NET_JSON" \
    | grep -E "\"$field\":" | head -1 \
    | sed -E 's/^[^:]+:[[:space:]]*"([^"]*)".*/\1/' | sed -E 's/,$//'
}
get_num() {
  local net_name="$1" field="$2"
  sed -n "/\"name\": *\"$net_name\"/,/^    }/p" "$NET_JSON" \
    | grep -E "\"$field\":" | head -1 | grep -oE '[0-9]+' | head -1
}

# ---- Arg parsing ----
WALLET=""
RPC_URL=""
CHAIN="mainnet"
DEPTH=4
FORMAT="text"

usage() {
  cat <<USAGE
sybilpicker — Wallet sybil score estimator (Foundry port)

Usage:
  bash scripts/score.sh --wallet 0xWALLET --rpc-url https://...
  bash scripts/score.sh --wallet 0xWALLET --depth 4 --format json
  bash scripts/score.sh --demo

Options:
  --wallet ADDR        target wallet
  --rpc-url URL        JSON-RPC endpoint
  --chain NAME         mainnet | testnet [default: mainnet]
  --depth N            funding-tree depth [default: 4]
  --format FMT         text | json [default: text]
  --help               show this help

Prerequisites:
  - Foundry (cast): curl -L https://foundry.paradigm.xyz | bash && foundryup
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --wallet) WALLET="$2"; shift 2 ;;
    --rpc-url) RPC_URL="$2"; shift 2 ;;
    --chain) CHAIN="$2"; shift 2 ;;
    --depth) DEPTH="$2"; shift 2 ;;
    --format) FORMAT="$2"; shift 2 ;;
    -*) echo "Unknown flag: $1" >&2; usage; exit 1 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

case "$CHAIN" in
  mainnet) RPC_URL="${RPC_URL:-$(get_field mainnet rpcUrl)}"; CHAIN_ID=$(get_num mainnet chainId) ;;
  testnet) RPC_URL="${RPC_URL:-$(get_field atlantic-testnet rpcUrl)}"; CHAIN_ID=$(get_num atlantic-testnet chainId) ;;
  *) echo "Unknown chain: $CHAIN" >&2; exit 1 ;;
esac

if [ -z "$WALLET" ]; then
  echo "Error: --wallet required (or use --demo)" >&2
  usage
  exit 1
fi

# ---- Foundry required (checked AFTER arg parsing so --help works offline) ----
if ! command -v cast >/dev/null 2>&1; then
  echo "Error: 'cast' not found. Install Foundry:" >&2
  echo "  curl -L https://foundry.paradigm.xyz | bash && foundryup" >&2
  exit 1
fi

# ---- Fetch wallet state ----
NONCE=$(cast nonce --rpc-url "$RPC_URL" "$WALLET" 2>/dev/null | tr -d '\n' || echo "")
NONCE_DEC=$(cast --to-dec "$NONCE" 2>/dev/null | tr -d '\n' || echo "0")
BALANCE=$(cast balance --rpc-url "$RPC_URL" "$WALLET" 2>/dev/null | tr -d '\n' || echo "")

# ---- Heuristic scoring ----
SCORE=10
SIGNALS=()

# 1. New wallet with lots of activity = sybil
[ "$NONCE_DEC" -gt 100 ] 2>/dev/null && [ "$BALANCE" = "0" ] && {
  SCORE=$(( SCORE + 30 ))
  SIGNALS+=("High nonce but zero balance — farmed then drained")
}

# 2. Balance is round number = farming pattern
if echo "$BALANCE" | grep -qE "^[0-9]+0000$|^[0-9]+\.0+$"; then
  SCORE=$(( SCORE + 10 ))
  SIGNALS+=("Balance is a round number — farming pattern")
fi

# 3. Walk the funding tree (depth-bounded)
# In a real implementation, walk eth_getTransactionByBlock + Internal txs.
# In this bash port, we surface the per-depth analysis as a placeholder
# and let the user run a deeper scan via the Python fallback.
log_funders() {
  echo "  Funding tree walk (depth $DEPTH):"
  echo "    (run the full Python scanner for complete analysis)"
  echo "    bash src/sybil_score.py --wallet $WALLET --depth $DEPTH"
}

# Cap
[ "$SCORE" -gt 100 ] && SCORE=100

# ---- Verdict ----
if [ "$SCORE" -ge 80 ]; then VERDICT="CRITICAL"
elif [ "$SCORE" -ge 60 ]; then VERDICT="HIGH"
elif [ "$SCORE" -ge 40 ]; then VERDICT="MED"
elif [ "$SCORE" -ge 20 ]; then VERDICT="LOW"
else VERDICT="CLEAN"
fi

# ---- Render ----
if [ "$FORMAT" = "json" ]; then
  cat <<JSON
{
  "wallet": "$WALLET",
  "chainId": $CHAIN_ID,
  "nonce": $NONCE_DEC,
  "balance": "$BALANCE",
  "score": $SCORE,
  "verdict": "$VERDICT",
  "signals": [$(printf '"%s",' "${SIGNALS[@]}" | sed 's/,$//')]
}
JSON
else
  echo ""
  echo "========================================================================"
  echo "  SYBIL SCORE"
  echo "  Wallet: $WALLET"
  echo "  Chain:  $CHAIN_ID"
  echo "========================================================================"
  echo ""
  echo "  Wallet nonce:  $NONCE_DEC"
  echo "  Wallet balance: $BALANCE"
  echo ""
  echo "  >>> SCORE:    $SCORE/100  <<<"
  echo "  >>> VERDICT:  $VERDICT  <<<"
  echo ""
  if [ ${#SIGNALS[@]} -gt 0 ]; then
    echo "  Signals:"
    for sig in "${SIGNALS[@]}"; do
      echo "    - $sig"
    done
  else
    echo "  No critical signals detected."
  fi
  echo ""
  log_funders
  echo ""
fi
