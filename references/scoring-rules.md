# Scoring rules

This file documents how `src/scorer.py` turns the six per-signal
scores into a single 0–100 sybil score plus a label.

## Method

Weighted average of the per-signal scores (each in [0, 1]):

```
sybil_score = round(100 * sum(weight * signal_score) / sum(weight))
```

The weights are calibrated so a wallet that triggers every sybil
signal scores 100, and a wallet that triggers none scores 0.

## Weights

| Signal                | Weight | Why this gets the most / least                  |
|-----------------------|--------|--------------------------------------------------|
| `funding_source`      | 25     | Single most predictive signal. CEX vs Funder is a 10× jump in sybil probability. |
| `wallet_age`          | 20     | New wallets are almost always sybil in airdrop contexts. |
| `funding_dispersion`  | 15     | Bulk funding is a structural sybil pattern.       |
| `dormancy_ratio`      | 15     | Receiving-without-sending is the canonical sybil. |
| `activity_regularity` | 15     | Bots have visible cadence.                        |
| `asset_variety`       | 10     | A tiebreaker; sybil wallets are usually mono-asset. |
| **Total**             | **100**|                                                    |

## Labels

| Range  | Label           | Recommended action                |
|--------|-----------------|-----------------------------------|
| 0–19   | `HUMAN`         | Allow. Looks like a normal user.  |
| 20–39  | `LOW_RISK`      | Allow with light review.          |
| 40–59  | `MEDIUM_RISK`   | Manual review before allowing.    |
| 60–79  | `HIGH_RISK`     | Reject unless strong counter-evidence. |
| 80–100 | `LIKELY_SYBIL`  | Reject. Almost certainly a farmed account. |

## Worked examples

### A human-like wallet

| Signal                | Weight | Score | Earned |
|-----------------------|--------|-------|--------|
| funding_source        | 25     | 0.05  | 1.25   |
| wallet_age            | 20     | 0.05  | 1.00   |
| funding_dispersion    | 15     | 0.05  | 0.75   |
| dormancy_ratio        | 15     | 0.10  | 1.50   |
| activity_regularity   | 15     | 0.30  | 4.50   |
| asset_variety         | 10     | 0.05  | 0.50   |
| **Total**             |        |       | **9.50 / 100** |

`sybil_score = round(100 * 9.5 / 100) = 10` → `HUMAN`.

### A sybil-like wallet

| Signal                | Weight | Score | Earned |
|-----------------------|--------|-------|--------|
| funding_source        | 25     | 0.85  | 21.25  |
| wallet_age            | 20     | 0.85  | 17.00  |
| funding_dispersion    | 15     | 0.90  | 13.50  |
| dormancy_ratio        | 15     | 0.95  | 14.25  |
| activity_regularity   | 15     | 0.50  | 7.50   |
| asset_variety         | 10     | 0.70  | 7.00   |
| **Total**             |        |       | **80.50 / 100** |

`sybil_score = round(100 * 80.5 / 100) = 80` → `LIKELY_SYBIL`.

## Tuning for your protocol

Different protocols weight sybil signals differently:

- **Airdrops** tend to weight `funding_source` and `wallet_age`
  more heavily; `asset_variety` matters less.
- **Governance** tends to weight `funding_dispersion` more
  heavily (one funder = one attack vector).
- **Reputation / credit** tends to weight `activity_regularity`
  and `asset_variety` more heavily.

Edit `WEIGHTS` in `src/scorer.py` to match your protocol's
risk model. The weights must sum to 100 for the score to be a
proper weighted average; the engine will still work if they
don't, but the math gets weird.

## Limitations

- The score is a single number; it loses information. A wallet
  with `funding_source=0.05, asset_variety=0.7` (CEX-funded but
  holds only one token) is a different risk profile from a
  wallet with `funding_source=0.7, asset_variety=0.05` (Funder-
  funded but diversified). The per-signal breakdown in the
  report preserves this — always read it before rejecting.
- The score does not model attack vectors. A coordinated
  cluster of 100 sybil wallets, each scoring `HUMAN`, will slip
  through. Cluster detection is out of scope for this skill.
- The built-in CEX list is small. Production deployments should
  bundle a more comprehensive tag list (e.g. from Etherscan,
  Chainalysis, or your own intel).
