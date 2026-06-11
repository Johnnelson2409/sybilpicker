---
name: sybil-score-estimator
description: >
  REQUIRED for any task that requires estimating the probability
  that a wallet is a sybil (a duplicate or farmed account created
  to extract airdrops, governance power, or other per-wallet
  rewards). Invoke when the user asks to "check if this wallet is
  a sybil", "sybil score", "is this a real user", "wallet
  reputation", "airdrop farming detector", "duplicate account
  check", or wants a per-signal breakdown of (funding source,
  wallet age, funding dispersion, dormancy ratio, activity
  regularity, asset variety). Use the bundled `src/sybil_score.py`
  engine to scan a wallet's transaction history via JSON-RPC
  (works with any EVM-compatible RPC URL, including Pharos Pacific
  mainnet and Atlantic testnet).
  Do not attempt sybil estimation without reading this skill.
version: 2.0.0
requires: read
bins: [bash, cast, jq]
author: Johnnelson2409
network: pharos
tags: [pharos, blockchain, sybil, wallet, identity, agent-skill, foundry]
agents: [claude, codex, gemini, openclaw]
---


# Sybil Score Estimator

Estimate the probability that a wallet is a sybil — a duplicate or
farmed account created to extract per-wallet rewards (airdrops,
governance power, etc.). The skill scores the wallet on six
independent signals and rolls them up into a single 0–100 score
plus a five-tier label.

The skill ships a Python engine that:

1. Traces the wallet's **funding source** by walking back to the
   first inbound transfer and identifying whether the funder is a
   known CEX, a known Funder contract, an unrelated EOA, or a
   fresh address.
2. Computes the wallet **age** (time since first on-chain tx).
3. Measures **funding dispersion** — how many distinct addresses
   have funded this wallet, and how concentrated the funding is.
4. Computes the **dormancy ratio** — share of inbound transfers
   that are never followed by outbound activity (a sybil marker).
5. Computes the **activity pattern** — variance in tx timing (a
   cluster of evenly-spaced txs is a bot pattern).
6. Computes **asset variety** — does the wallet hold a broad
   portfolio or only airdrop-relevant tokens?

## When to use

- The user asks "is this wallet a sybil?"
- The user wants to filter an airdrop claim list by sybil score.
- The user wants to vet a counterparty before a high-value
  on-chain interaction.
- The user wants a per-signal breakdown of one or more wallets.

## When NOT to use

- Real KYC / AML (use a dedicated identity provider).
- Privacy mixers (the engine reads the public ledger; a wallet
  that received funds from Tornado will look "fresh" but not
  necessarily sybil).
- Wallets that are still in pending state (need at least one
  confirmed tx to score).

## Inputs

| Input             | Required | Description                                            |
|-------------------|----------|--------------------------------------------------------|
| `wallet`          | yes      | 0x address to analyze                                  |
| `rpc_url`         | yes      | JSON-RPC endpoint (any EVM-compatible chain)           |
| `block_count`     | no       | How many recent blocks to scan (default 10000)         |
| `known_funders`   | no       | Path to JSON list of known Funder contract addresses   |
| `format`          | no       | `text` (default), `json`, `markdown`, `html`           |

## Outputs

A structured report with:

- Per-signal score (0–1) and detail.
- Aggregated sybil score (0–100).
- Sybil label: `HUMAN` / `LOW_RISK` / `MEDIUM_RISK` / `HIGH_RISK` /
  `LIKELY_SYBIL`.
- Recommended action: allow / review / reject.

### Labels

| Label           | Score    | Recommended action |
|-----------------|----------|--------------------|
| `HUMAN`         | 0–20     | Allow. Looks like a normal user. |
| `LOW_RISK`      | 20–40    | Allow with light review. |
| `MEDIUM_RISK`   | 40–60    | Manual review before allowing. |
| `HIGH_RISK`     | 60–80    | Reject unless strong counter-evidence. |
| `LIKELY_SYBIL`  | 80–100   | Reject. Almost certainly a farmed account. |

## Quick start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Score a wallet on Pharos mainnet
python src/sybil_score.py \
  --wallet 0xYourWallet \
  --rpc-url https://rpc.pharos.xyz \
  --block-count 10000

# 3. Score with a custom known-funder list
python src/sybil_score.py \
  --wallet 0xYourWallet \
  --rpc-url https://rpc.pharos.xyz \
  --known-funders funders.json

# 4. Get a JSON report
python src/sybil_score.py \
  --wallet 0xYourWallet \
  --rpc-url https://rpc.pharos.xyz \
  --format json > sybil-report.json
```

## Agent invocation pattern

When the user asks for a sybil score, the Agent should:

1. Resolve the RPC URL — accept the user's URL, or use a known
   EVM RPC for the chain the user mentions.
2. Ask the user for the wallet address (never invent one).
3. Optionally, ask the user for a `known-funders` file if they
   want to bias the funding-source signal toward a specific
   protocol.
4. Run `src/sybil_score.py` with the parameters above.
5. Pipe the JSON output through `src/report.py` for a formatted
   report.
6. Surface the score, label, and the highest-weighted signal as
   the top of the reply.

## Error handling

| Error                  | Cause                              | Action |
|------------------------|------------------------------------|--------|
| `rpc unreachable`      | Bad / dead RPC URL                 | Ask user for a working RPC |
| `no txs in range`      | Wallet inactive or new             | Increase `--block-count` or confirm address |
| `unknown funder`       | First inbound came from a fresh EOA | Not an error; reported as `FRESH` |
| `archive node required` | Some signals need historical state | Tell the user to supply an archive RPC |

## Limitations

- All signals are on-chain only. Off-chain identity (Twitter
  followers, ENS name, GitHub activity) is not in scope.
- The funder-classification step uses a small built-in CEX list;
  supplement with `--known-funders` for accuracy.
- The activity-regularity signal can flag power users (who
  schedule their txs) as bots. Combine with the other signals
  before rejecting.
- The skill runs against a single chain. A wallet that looks
  clean on Pharos mainnet may look sybil-ish on Ethereum — the
  user should re-run per chain.

## Prerequisites

```bash
python3 --version   # 3.10+
```

The skill uses only the Python standard library (`urllib.request`,
`json`, `argparse`). No third-party packages, no Foundry, no
`pip install` step.

The skill is **read-only** — no private key is required or accepted.

## Network Configuration

Network RPC URLs and chain IDs are sourced from
`assets/networks.json` (canonical Pharos Skill Engine schema). To
add a new network, append a new object to the `networks` array and
update `defaultNetwork` if needed.

## Capability Index

| User Need | Capability | Detailed Instructions |
|---|---|---|
| Default entry point | CLI with a `--wallet` / `--safe` / `--governor` flag | See the `Usage` section in the README; the CLI takes a target identifier and prints a Markdown or JSON report |
| JSON for an agent | `--format json` | Output is a structured payload that an agent can import directly |
| Markdown report | pipe to `report.py` | `python3 src/... --format json \| python3 src/report.py --format markdown --out X.md` |
| Bounded scan | `--max-blocks` / `--lookback` / `--block-count` | Default scans are bounded to stay within the public Pharos RPC's request rate |
| Network switch | `--chain mainnet\|testnet` | Default is Atlantic testnet; pass `--chain mainnet` to switch |

## General Error Handling

| Error Scenario | CLI Error Signature | Handling |
|---|---|---|
| Target not on the specified chain | `null` receipt / no data returned | Exit with "not found on chain=X; try `--chain <other>`" |
| RPC rate-limited (HTTP 429) | Backoff response from RPC | Built-in exponential backoff (0.4s, 0.8s, 1.6s, 3.2s) with 4 retry attempts |
| Bad target format | Validator rejects the input | CLI prints a usage hint; no RPC call is made |
| Missing required arg | `argparse` exits with usage | CLI prints required args; user re-invokes with the right flags |
| No matches (clean target) | Empty result / `verdict: clean` | Normal case — emit the "no issues" report, no error |

## Security Reminders

- **Private Key Protection** — the skill is read-only and never
  accepts a private key. Do not paste keys into chat.
- **Network Confirmation** — before any future write-skill
  integration, confirm the network with the user.
- **No External API** — the skill does not call any third-party
  service beyond the Pharos RPC and PharosScan (where applicable).
  All data is fetched directly.

## Write Operation Pre-checks

This skill is **read-only** and never submits a transaction, so the
full 4-step write pre-check is not applicable. If a future version
adds a write path, the pre-checks must include:

1. **Private Key Check** — `--private-key` / `$PRIVATE_KEY` must be
   set; warn if the key has zero balance.
2. **Derive Public Address** — `cast wallet address`; confirm the
   key is for the intended network.
3. **Network Confirmation** — prompt the user with "You are about
   to write to Pacific mainnet. Continue? (y/N)".
4. **Automatic Balance Check** — `cast balance`; if below the
   operation cost + gas, abort with a clear error.
