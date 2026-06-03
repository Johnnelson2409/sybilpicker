# Sybil signals

This file documents the six signals `src/signals.py` computes
and the rationale for each. Every signal returns a score in
[0, 1] where 0 = looks human and 1 = looks sybil.

## 1. funding_source (weight: 25)

**What it measures:** the type of address that funded this
wallet for the first time.

| Funder type            | Score | Rationale                                          |
|------------------------|-------|----------------------------------------------------|
| Known CEX hot wallet   | 0.05  | A real user usually on-ramps from a CEX.           |
| Active EOA (≥50 txs)   | 0.10  | An active funder looks like a peer.                |
| Lightly-used EOA (5-49)| 0.30  | Ambiguous.                                         |
| Funder contract        | 0.85  | Bulk-funder contracts (e.g. Disperse, MultiSender) |
| Contract (other)       | 0.70  | Routers, multisends, exchange withdraw contracts.  |
| Near-fresh EOA (0-4)   | 0.75  | Likely a freshly-created top-up wallet.            |
| Zero address           | 1.00  | Self-mint; almost always a sybil.                  |

The CEX / Funder classification is bootstrapped from a small
built-in list in `src/funding.py:BUILTIN_CEX_HOT_WALLETS`. For
production, supply `--known-funders` with a comprehensive list
of protocol-specific Funder contracts.

## 2. wallet_age (weight: 20)

**What it measures:** time since the wallet's first on-chain tx.

| Age             | Score | Rationale                                  |
|-----------------|-------|--------------------------------------------|
| < 1 day         | 0.95  | Brand new.                                 |
| 1-7 days        | 0.85  | Just-in-time for an airdrop.               |
| 7-30 days       | 0.60  | Suspicious.                                |
| 30-180 days     | 0.25  | Plausible.                                 |
| ≥ 180 days      | 0.05  | Established.                               |

The age is the difference between `head_ts` and the timestamp of
the first inbound transfer found in the scan range. If the scan
range is too short to see the wallet's creation, the score will
look worse than it is — increase `--block-count`.

## 3. funding_dispersion (weight: 15)

**What it measures:** how many distinct addresses have funded
this wallet, and how concentrated the funding is.

| Pattern                                  | Score |
|------------------------------------------|-------|
| 1 funder, ≥ 2 transfers                  | 0.90  |
| u/n < 30% (concentrated)                 | 0.70  |
| u/n 30-70% (moderate)                    | 0.30  |
| u/n ≥ 70% (highly diverse)               | 0.05  |

A sybil wallet is typically funded by one source. A real user's
wallet receives funds from many sources (payroll, friends, CEX,
DEX, etc.).

## 4. dormancy_ratio (weight: 15)

**What it measures:** the ratio of inbound to outbound txs.

| Pattern                                        | Score |
|------------------------------------------------|-------|
| 0 outbound, ≥ 2 inbound                        | 0.95  |
| 0 outbound, 1 inbound                          | 0.80  |
| out < in/4                                     | 0.70  |
| out < in/2                                     | 0.40  |
| out ≥ in/2                                     | 0.10  |

The skill uses `eth_getTransactionCount` as a proxy, which gives
us an exact outbound count without indexing every tx. A
sophisticated sybil will have a few outbound txs (to satisfy
"engagement" checks) but the ratio is still skewed.

## 5. activity_regularity (weight: 15)

**What it measures:** variance in the time gap between outbound
txs. Bot wallets often transact at near-equal intervals.

| CV of gaps  | Score | Rationale                                |
|-------------|-------|------------------------------------------|
| < 0.2       | 0.85  | Extremely regular. Likely automated.     |
| 0.2-0.5     | 0.60  | Somewhat regular.                        |
| 0.5-1.0     | 0.30  | Human-like.                              |
| ≥ 1.0       | 0.10  | Strongly human.                          |

CV is the population standard deviation divided by the mean. The
skill walks the last `--block-count` blocks looking for the
wallet as the `from` field, then computes CV across the
inter-block gaps. With < 4 outbound txs, the signal is too
noisy and returns 0.5 ("don't know").

## 6. asset_variety (weight: 10)

**What it measures:** the number of distinct ERC-20 contracts
that have ever sent tokens to the wallet.

| Distinct ERC-20s  | Score |
|-------------------|-------|
| 0                 | 0.70  |
| 1                 | 0.40  |
| 2-3               | 0.25  |
| ≥ 4               | 0.05  |

A sybil wallet typically only holds the airdrop-relevant token
plus dust. A real user accumulates random tokens from airdrops,
DEX trades, friends, and earnings over time.

## Limitations

- All signals are on-chain only. A real user with a clean wallet
  but a high `funding_dispersion` from a "refund farm" looks
  sybil-ish; combine with off-chain context (GitHub, Twitter,
  Discord age) for the final call.
- The activity-regularity signal can flag power users who
  schedule their txs. Always look at the *combination* of
  signals, not the highest single one.
- For a sybil that's funded by a *new* CEX subaccount, the
  funding-source signal will say "active EOA" — adding a
  `Binance/OKX/Bybit internal cluster` map to `--known-funders`
  would help here.
