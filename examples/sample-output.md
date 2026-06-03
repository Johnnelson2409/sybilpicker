# Example: Sybil Score Report

> Generated against a sample sybil-likely wallet on Pharos
> mainnet. See `SKILL.md` for the full command line.

```
================================================================
  SYBIL SCORE — 0xSybilishWallet
  Chain ID: 1672
================================================================

  First seen:    block 100 (3.5d ago)
  First funder:  0xFunder  [NATIVE]
  Total inbound: 5
  Unique funder(s): 1

  Per-signal scores (0 = human, 1 = sybil)
  ------------------------------------------------------------
  funding_source         [█████████████████░░░] 0.85
                           First funder is a known Funder contract. Strong sybil signal.
  wallet_age             [█████████████████░░░] 0.85
                           Wallet is 3.0 days old. Strong sybil signal.
  funding_dispersion     [██████████████████░░] 0.90
                           Single funder sent 5 transfers. Strong sybil signal.
  dormancy_ratio         [███████████████████░] 0.95
                           Wallet has 0 outbound txs but 5 inbound. Almost certainly sybil.
  activity_regularity    [██████████░░░░░░░░░░] 0.50
                           Only 1 outbound txs; insufficient for a regularity check.
  asset_variety          [██████████████░░░░░░] 0.70
                           Wallet only ever received native. Limited asset variety.

  >>> SYBIL SCORE: 80 / 100  (LIKELY_SYBIL) <<<
      Reject. Almost certainly a farmed account.
      Dominant signal: funding_source (0.85)
```

## Reading the report

- **Sybil score** is 0–100, higher is more sybil-likely. 80 →
  `LIKELY_SYBIL`.
- **Funding source** is the single most predictive signal: a
  known Funder contract is almost always a sybil indicator.
- **Wallet age** of 3 days is also a strong signal; legitimate
  users rarely fund and immediately use a brand-new wallet.
- **Dormancy ratio** of 0 outbound vs 5 inbound is the canonical
  sybil pattern — receive, never spend.
- **Dominant signal** surfaces the signal that contributed most
  to the score, so you know what to investigate.

## Next steps for the user

1. **`HUMAN` / `LOW_RISK`** — allow. Maybe a light review.
2. **`MEDIUM_RISK`** — manual review; check the per-signal
   breakdown for the dominant signal.
3. **`HIGH_RISK` / `LIKELY_SYBIL`** — reject. If the wallet has
   a legitimate explanation (e.g. it's a known project grant
   recipient), override the score with off-chain context.
