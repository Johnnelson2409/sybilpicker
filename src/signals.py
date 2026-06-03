"""
signals.py - Per-signal sybil scoring.

Each signal returns a SignalResult with a score in [0, 1] (0 =
looks human, 1 = looks sybil) and a human-readable detail string.

Six signals:
  1. funding_source  - first funder classification
  2. wallet_age      - time since first on-chain activity
  3. funding_dispersion - unique-funder concentration
  4. dormancy_ratio  - share of inbound transfers that never lead
                       to outbound activity
  5. activity_regularity - variance in tx timing (lower variance
                           = more bot-like)
  6. asset_variety   - ERC-20 transfer count vs repeat funder
                       patterns
"""
from __future__ import annotations
import time
import statistics
from dataclasses import dataclass
from typing import List, Optional, Set

from funding import FundingTrace, classify_funder
from rpc import RpcClient, RpcError


@dataclass
class SignalResult:
    name: str
    score: float             # 0..1
    detail: str


# ---- 1. Funding source ----

def signal_funding_source(
    rpc: RpcClient,
    trace: FundingTrace,
    known_cex: dict,
    known_funders: Optional[Set[str]] = None,
) -> SignalResult:
    if trace.first_inbound is None:
        return SignalResult("funding_source", 0.5,
                            "No inbound transfers seen; unable to classify.")
    funder = trace.first_inbound.from_addr
    try:
        is_contract = bool(rpc.get_code(funder)) and (rpc.get_code(funder) != "0x")
    except RpcError:
        is_contract = False
    cls = classify_funder(funder, is_contract, known_cex, known_funders)

    if cls == "CEX":
        return SignalResult("funding_source", 0.05,
                            f"First funder is a known CEX ({known_cex.get(funder.lower(), 'CEX')}). Strong human signal.")
    if cls == "FUNDER":
        return SignalResult("funding_source", 0.85,
                            f"First funder is a known Funder contract. Strong sybil signal.")
    if cls == "CONTRACT":
        return SignalResult("funding_source", 0.7,
                            "First funder is a contract (e.g. multisend or exchange withdrawal). Mild sybil signal.")
    if cls == "EOA":
        # An EOA funder: ambiguous. If the funder has its own
        # history, treat as more human; if not, mild sybil.
        try:
            funder_tx_count = rpc.call("eth_getTransactionCount", [funder, "latest"])
            funder_nonce = int(funder_tx_count, 16)
        except RpcError:
            funder_nonce = 0
        if funder_nonce >= 50:
            return SignalResult("funding_source", 0.1,
                                f"First funder is an active EOA ({funder_nonce} txs). Looks human.")
        if funder_nonce >= 5:
            return SignalResult("funding_source", 0.3,
                                f"First funder is a lightly-used EOA ({funder_nonce} txs). Ambiguous.")
        return SignalResult("funding_source", 0.75,
                            f"First funder is a near-fresh EOA ({funder_nonce} txs). Strong sybil signal.")
    if cls == "ZERO":
        return SignalResult("funding_source", 1.0,
                            "First funder is the zero address (likely a self-mint). Almost certainly sybil.")
    return SignalResult("funding_source", 0.5, f"First funder classification: {cls}.")


# ---- 2. Wallet age ----

def signal_wallet_age(trace: FundingTrace, head_ts: int) -> SignalResult:
    if trace.first_seen_ts is None or trace.first_seen_ts == 0:
        return SignalResult("wallet_age", 0.5, "No first-seen timestamp; ambiguous.")
    age_seconds = max(0, head_ts - trace.first_seen_ts)
    age_days = age_seconds / 86400.0
    if age_days < 1:
        return SignalResult("wallet_age", 0.95, f"Wallet is < 1 day old. Strong sybil signal.")
    if age_days < 7:
        return SignalResult("wallet_age", 0.85, f"Wallet is {age_days:.1f} days old. Strong sybil signal.")
    if age_days < 30:
        return SignalResult("wallet_age", 0.6, f"Wallet is {age_days:.0f} days old. Mild sybil signal.")
    if age_days < 180:
        return SignalResult("wallet_age", 0.25, f"Wallet is {age_days:.0f} days old. Looks human.")
    return SignalResult("wallet_age", 0.05, f"Wallet is {age_days:.0f} days old. Strong human signal.")


# ---- 3. Funding dispersion ----

def signal_funding_dispersion(trace: FundingTrace) -> SignalResult:
    n = trace.total_inbound_count
    u = len(trace.unique_funders)
    if n == 0:
        return SignalResult("funding_dispersion", 0.5, "No inbound transfers seen.")
    if u == 1 and n >= 2:
        return SignalResult("funding_dispersion", 0.9,
                            f"Single funder sent {n} transfers. Strong sybil signal.")
    if u / n < 0.3:
        return SignalResult("funding_dispersion", 0.7,
                            f"Funding concentrated: {u} funder(s) for {n} transfers ({u/n:.0%} diversity).")
    if u / n < 0.7:
        return SignalResult("funding_dispersion", 0.3,
                            f"Funding moderately diverse: {u} funder(s) for {n} transfers ({u/n:.0%} diversity).")
    return SignalResult("funding_dispersion", 0.05,
                        f"Funding highly diverse: {u} funder(s) for {n} transfers ({u/n:.0%} diversity).")


# ---- 4. Dormancy ratio ----
# We approximate "inbound that never led to outbound" as inbound
# transfers that landed in the same block as the wallet's other
# inbound transfers, or within a very short window with no
# subsequent outbound from the wallet. As a proxy we look at the
# gap (in blocks) between each inbound and the wallet's next
# outbound tx. If the next outbound is far away or absent, the
# inbound looks sybil-y.

def signal_dormancy_ratio(
    rpc: RpcClient,
    trace: FundingTrace,
    head_block: int,
) -> SignalResult:
    if not trace.events:
        return SignalResult("dormancy_ratio", 0.5, "No inbound transfers seen.")
    # Fetch the wallet's outbound tx count and a small recent
    # block window. This is a coarse approximation: we just check
    # if the wallet has any outbound activity at all.
    try:
        out_nonce = int(rpc.call("eth_getTransactionCount", [trace.wallet, "latest"]), 16)
    except RpcError:
        out_nonce = 0
    if out_nonce == 0 and trace.total_inbound_count >= 2:
        return SignalResult("dormancy_ratio", 0.95,
                            f"Wallet has 0 outbound txs but {trace.total_inbound_count} inbound. Almost certainly sybil.")
    if out_nonce == 0:
        return SignalResult("dormancy_ratio", 0.8,
                            "Wallet has 0 outbound txs. Probably sybil or freshly funded.")
    if out_nonce < trace.total_inbound_count / 4:
        return SignalResult("dormancy_ratio", 0.7,
                            f"Wallet has {out_nonce} outbound but {trace.total_inbound_count} inbound. Low activity ratio.")
    if out_nonce < trace.total_inbound_count / 2:
        return SignalResult("dormancy_ratio", 0.4,
                            f"Wallet has {out_nonce} outbound vs {trace.total_inbound_count} inbound. Moderate ratio.")
    return SignalResult("dormancy_ratio", 0.1,
                        f"Wallet has {out_nonce} outbound vs {trace.total_inbound_count} inbound. Healthy ratio.")


# ---- 5. Activity regularity ----
# A "bot" wallet will often have outbound txs spaced at near-equal
# intervals. We read the wallet's recent outbound txs, compute
# the gap between them, and use the coefficient of variation (CV)
# of those gaps. Low CV = bot-like. High CV = human-like.

def signal_activity_regularity(
    rpc: RpcClient,
    wallet: str,
    head: int,
    max_blocks: int = 5000,
) -> SignalResult:
    try:
        out_nonce = int(rpc.call("eth_getTransactionCount", [wallet, "latest"]), 16)
    except RpcError:
        out_nonce = 0
    if out_nonce < 4:
        return SignalResult("activity_regularity", 0.5,
                            f"Only {out_nonce} outbound txs; insufficient for a regularity check.")
    # Find the blocks of the last K outbound txs. We can't easily
    # enumerate nonce-ordered txs without an indexer, so we
    # walk blocks and look for the wallet as the `from` field.
    # Cheap but only works for low-nonce wallets.
    CHUNK = 200
    cur = max(0, head - max_blocks)
    found_blocks: List[int] = []
    while cur <= head and len(found_blocks) < 32:
        end = min(cur + CHUNK - 1, head)
        try:
            block = rpc.get_block(end, full_txs=True)
        except RpcError:
            cur = end + 1
            continue
        for tx in block.get("transactions", []):
            if tx.get("from", "").lower() == wallet.lower():
                found_blocks.append(end)
                if len(found_blocks) >= 32:
                    break
        cur = end + 1
    if len(found_blocks) < 4:
        return SignalResult("activity_regularity", 0.5,
                            f"Found {len(found_blocks)} outbound blocks in range; insufficient for a regularity check.")
    found_blocks.sort()
    gaps = [found_blocks[i+1] - found_blocks[i] for i in range(len(found_blocks)-1)]
    if not gaps:
        return SignalResult("activity_regularity", 0.5, "No inter-tx gaps.")
    mean = statistics.mean(gaps)
    if mean == 0:
        return SignalResult("activity_regularity", 0.9,
                            "Multiple outbound txs in the same block. Strong bot signal.")
    sd = statistics.pstdev(gaps)
    cv = sd / mean  # coefficient of variation
    if cv < 0.2:
        return SignalResult("activity_regularity", 0.85,
                            f"Tx gaps have very low variance (CV={cv:.2f}). Bot-like.")
    if cv < 0.5:
        return SignalResult("activity_regularity", 0.6,
                            f"Tx gaps have moderate variance (CV={cv:.2f}).")
    if cv < 1.0:
        return SignalResult("activity_regularity", 0.3,
                            f"Tx gaps have healthy variance (CV={cv:.2f}). Human-like.")
    return SignalResult("activity_regularity", 0.1,
                        f"Tx gaps have high variance (CV={cv:.2f}). Strong human signal.")


# ---- 6. Asset variety ----
# A sybil wallet will often hold only the airdrop-relevant token
# plus a dust amount of gas. A human wallet holds a broader
# variety. We approximate "variety" as the number of unique ERC-20
# contracts that have ever sent tokens to the wallet, weighted
# against how concentrated the funding is.

def signal_asset_variety(trace: FundingTrace) -> SignalResult:
    if not trace.events:
        return SignalResult("asset_variety", 0.5, "No inbound transfers seen.")
    unique_assets = {e.asset for e in trace.events if not e.is_native}
    n_native = sum(1 for e in trace.events if e.is_native)
    n_unique_tokens = len(unique_assets)
    if n_unique_tokens == 0 and n_native <= 1:
        return SignalResult("asset_variety", 0.7,
                            f"Wallet only ever received native. Limited asset variety.")
    if n_unique_tokens == 1:
        return SignalResult("asset_variety", 0.4,
                            f"Wallet received 1 ERC-20 + {n_native} native transfer(s).")
    if n_unique_tokens <= 3:
        return SignalResult("asset_variety", 0.25,
                            f"Wallet received {n_unique_tokens} ERC-20 + {n_native} native transfer(s).")
    return SignalResult("asset_variety", 0.05,
                        f"Wallet received {n_unique_tokens} distinct ERC-20s + {n_native} native transfer(s). Strong human signal.")


# ---- entry point ----

def compute_all(
    rpc: RpcClient,
    wallet: str,
    trace: FundingTrace,
    known_cex: dict,
    known_funders: Optional[Set[str]] = None,
    head_ts: Optional[int] = None,
) -> List[SignalResult]:
    head = rpc.block_number()
    head_ts = head_ts or int(time.time())
    return [
        signal_funding_source(rpc, trace, known_cex, known_funders),
        signal_wallet_age(trace, head_ts),
        signal_funding_dispersion(trace),
        signal_dormancy_ratio(rpc, trace, head),
        signal_activity_regularity(rpc, wallet, head),
        signal_asset_variety(trace),
    ]
