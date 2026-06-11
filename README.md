# SybilPicker — Sybil Score Estimator

> Estimate the probability that a wallet is a sybil (a duplicate
> or farmed account) by scoring it on six independent
> on-chain signals.

[![python](https://img.shields.io/badge/python-3.9%2B-blue)]()
[![license](https://img.shields.io/badge/license-MIT--0-green)]()
[![rpc](https://img.shields.io/badge/RPC-JSON--RPC%20%7C%20EVM-orange)]()

## Overview

SybilPicker walks a wallet's transaction history via JSON-RPC,
computes six independent sybil-risk signals (funding source,
wallet age, funding dispersion, dormancy ratio, activity
regularity, asset variety), and rolls them up into a single
0–100 score plus a five-tier label.

It works against any EVM-compatible JSON-RPC endpoint and ships
with first-class support for the Pharos networks (see
[Supported networks](#supported-networks)).

## Features

- **Six independent signals** — funding source, wallet age,
  funding dispersion, dormancy ratio, activity regularity, asset
  variety.
- **0–100 sybil score** with five-tier label (`HUMAN` /
  `LOW_RISK` / `MEDIUM_RISK` / `HIGH_RISK` / `LIKELY_SYBIL`).
- **Per-signal breakdown** — see *why* a wallet scored the way
  it did, with a plain-English detail string.
- **Dominant signal** — the engine surfaces the signal that
  contributed most to the score, so the user knows what to
  investigate.
- **Pluggable known-funder list** — supply `--known-funders`
  with a JSON of contract addresses to bias the funding-source
  signal toward your protocol's Funder contracts.
- **Multi-format output** — text (with ANSI colors), JSON,
  Markdown, or HTML via the `report.py` formatter.
- **Agent-ready** — ships a `SKILL.md` at the repo root with
  the invocation contract an agent runtime needs to drive the
  tool.

## Supported networks

The tool runs against any EVM-compatible JSON-RPC endpoint. The
following networks are explicitly supported out of the box and
used in the examples below.

| Network                 | Chain ID | RPC URL                                | Native token | Explorer                          |
|-------------------------|----------|----------------------------------------|--------------|-----------------------------------|
| Pharos Pacific Mainnet  | `1672`   | `https://rpc.pharos.xyz`               | PROS         | https://www.pharosscan.xyz/       |
| Pharos Atlantic Testnet | `688689` | `https://atlantic.dplabs-internal.com` | PHRS         | https://atlantic.pharosscan.xyz/  |

You can target either by passing the matching `--rpc-url` flag
(see [Usage](#usage)).

## Framework

- **Language:** Python 3.9+
- **RPC protocol:** JSON-RPC (`eth_blockNumber`,
  `eth_getBlockByNumber`, `eth_getTransactionCount`,
  `eth_getCode`, `eth_getLogs`, `eth_chainId`)
- **External CLIs (optional):** `cast` from
  [Foundry](https://book.getfoundry.xyz/) for manual cross-checks
  of tx history; `jq` for ergonomic RPC URL extraction in shell
  pipelines.
- **No web3 framework required** — the engine speaks JSON-RPC
  directly over `requests`.

## Dependencies

Runtime (Python):

- `requests>=2.31` — HTTP client used by `src/rpc.py`.

External (only if you want the optional CLIs):

- `cast` / `forge` — Foundry CLI (https://book.getfoundry.xyz/getting-started/installation).
- `jq` — command-line JSON processor, used in README shell snippets.

Everything is pinned in `requirements.txt` at the repo root.

## Install

### 1. Install Foundry (the engine the skill is built on)

```bash
curl -L https://foundry.paradigm.xyz | bash
foundryup
```

Verify with `cast --version`. This gives you `cast`, `forge`, `anvil`, and `chisel` on your `$PATH`.

### 2. Install jq (used to parse JSON)

```bash
# macOS
brew install jq
# Debian/Ubuntu/Termux
apt install -y jq
# Alpine
apk add jq
```

Verify with `jq --version`.

### 3. Get the skill

```bash
git clone https://github.com/Johnnelson2409/sybilpicker
cd sybilpicker
chmod +x scripts/*.sh
```

That's it. No `pip install`, no `npm install`, no `forge build`, no compile. The skill is one or more bash scripts that use `cast` (from Foundry) for every RPC read. The `assets/networks.json` file already knows the Pharos Pacific Mainnet and Atlantic Testnet endpoints.
## Usage

### Score a wallet on Pharos mainnet

```bash
python src/sybil_score.py \
  --wallet 0xYourWallet \
  --rpc-url https://rpc.pharos.xyz \
  --block-count 10000
```

### Score a wallet on Pharos Atlantic testnet

```bash
python src/sybil_score.py \
  --wallet 0xYourWallet \
  --rpc-url https://atlantic.dplabs-internal.com \
  --block-count 10000
```

### Score with a custom known-funder list

```bash
python src/sybil_score.py \
  --wallet 0xYourWallet \
  --rpc-url https://rpc.pharos.xyz \
  --known-funders funders.json
```

A known-funders file is a JSON list of addresses (or a
`{name: address}` map):

```json
[
  "0xFunder1...",
  "0xFunder2..."
]
```

### Output as JSON, then format as Markdown

```bash
python src/sybil_score.py \
  --wallet 0xYourWallet \
  --rpc-url https://rpc.pharos.xyz \
  --format json \
  | python src/report.py --format markdown --out sybil-report.md
```

### Output as HTML

```bash
python src/sybil_score.py \
  --wallet 0xYourWallet \
  --rpc-url https://rpc.pharos.xyz \
  --format json \
  | python src/report.py --format html --out sybil-report.html
```

### Command-line flags

| Flag                | Required | Default | Description                                       |
|---------------------|----------|---------|---------------------------------------------------|
| `--wallet`          | yes      | —       | 0x address to analyze                             |
| `--rpc-url`         | yes      | —       | JSON-RPC endpoint                                 |
| `--block-count`     | no       | 10000   | How many recent blocks to scan                    |
| `--known-funders`   | no       | —       | Path to JSON list of known Funder contract addresses |
| `--format`          | no       | text    | `text`, `json`, `markdown`, `html`                |
| `--out`             | no       | -       | Output file (`-` for stdout)                      |

### Sample output

See `examples/sample-output.md` for what a real report looks like.

## AI Agent Integration

This repository ships a `SKILL.md` at the root that any agent
runtime can load to discover the skill. The flow is:

1. The agent reads `SKILL.md` to learn the capability and
   required arguments (`--wallet`, `--rpc-url`).
2. The agent collects the wallet address from the user (it never
   invents one).
3. The agent runs `python src/sybil_score.py` with the
   parameters and captures stdout (or `--out` to a file).
4. The agent surfaces the sybil score, label, dominant signal,
   and recommended action as the top of its reply.
5. If a formatted report is needed, the agent pipes the JSON
   output through `python src/report.py --format <fmt>`.

A typical prompt that triggers the skill:

> "Is the Pharos wallet `0xYourWallet` a sybil? RPC is
> `https://rpc.pharos.xyz`."

A typical reply:

> **Sybil score: 80 / 100 — LIKELY_SYBIL** — Reject. Almost
> certainly a farmed account. Dominant signal: `funding_source`
> (0.85) — first funder is a known Funder contract. See
> `sybil-report.md` for the full per-signal breakdown.

## Repository layout

```
sybilpicker/
├── SKILL.md                       # Agent-facing skill spec
├── README.md                      # This file
├── LICENSE                        # MIT-0
├── requirements.txt
├── src/
│   ├── sybil_score.py             # CLI entry point
│   ├── funding.py                 # Funding-source tracer
│   ├── signals.py                 # Six per-signal scorers
│   ├── scorer.py                  # 0-100 weighted score + label
│   ├── rpc.py                     # JSON-RPC client
│   └── report.py                  # Text / JSON / Markdown / HTML formatter
├── references/
│   ├── signals.md                 # Per-signal definitions
│   └── scoring-rules.md           # Weights + worked examples
└── examples/
    └── sample-output.md           # What a real report looks like
```

## How detection works

See `references/signals.md` for what each signal measures and
`references/scoring-rules.md` for the weights and label
boundaries.

## Roadmap

- [ ] Wire in cluster detection (graph-based): if a wallet
      shares a Funder with 50 others, all 50 should be flagged
      together.
- [ ] Add a `--cluster-id` output that groups sybil-likely
      wallets by their funding graph.
- [ ] Bundle a more comprehensive CEX / Funder address list.
- [ ] Off-chain signals (ENS, GitHub, Twitter) via plug-in
      adapters.

## Contributing

PRs welcome — especially new signals, better funder classification
lists, and benchmarks against real airdrop claim lists.

## License

[MIT-0](https://opensource.org/licenses/MIT-0) — free to use, modify,
redistribute. No attribution required.

---

**Author:** Johnnelson2409
**Built with:** Python 3.9+, plain JSON-RPC, and a healthy distrust
of bulk-funded airdrop farms.
