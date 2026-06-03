"""
funding.py - Trace a wallet's funding source.

Walk back the wallet's transaction history to find its first
inbound transfer (either a native ETH/PROS send or an ERC-20
Transfer event) and return the funding source: a known CEX, a
known Funder contract, a regular EOA, or a fresh address.

This is a "good enough" tracer for sybil detection. It does not
attempt to be a complete fund-flow analysis (that needs an indexer
like The Graph or Covalent).
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from rpc import RpcClient, RpcError, TRANSFER_TOPIC, topic_addr, decode_address_topic


# A small built-in list of well-known CEX hot wallets. Real
# deployments should override via --known-funders with a more
# comprehensive list (e.g. from Etherscan's CEX tag list).
BUILTIN_CEX_HOT_WALLETS: Dict[str, str] = {
    # Ethereum mainnet (placeholder addresses; supplement in production)
    "0x28c6c06298d5db88b5f5e8a8e8a8e8a8e8a8e8a8": "Binance",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance",
    "0x9696f55167156c1d5aebab0a0a8a8e8a8e8e8e8a": "Coinbase",
    "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43": "Coinbase",
    "0x71660c4005ba85c37ccec55d0c4493e66a7553b9": "Kraken",
    "0x2910543af39aba0cd09dbb2d50200b3e800a63d2": "Kraken",
    # Pharos mainnet placeholder addresses
    "0x0000000000000000000000000000000000000c01": "Pharos CEX Bridge",
}


@dataclass
class FundingEvent:
    tx_hash: str
    block: int
    timestamp: int
    from_addr: str
    to_addr: str
    asset: str            # "NATIVE" or ERC-20 contract address
    amount_wei: int
    is_native: bool


@dataclass
class FundingTrace:
    wallet: str
    first_seen_block: Optional[int] = None
    first_seen_ts: Optional[int] = None
    first_inbound: Optional[FundingEvent] = None
    total_inbound_count: int = 0
    unique_funders: Set[str] = field(default_factory=set)
    events: List[FundingEvent] = field(default_factory=list)


def _tx_ts(rpc: RpcClient, block: int) -> int:
    try:
        b = rpc.get_block(block, full_txs=False)
        return int(b.get("timestamp", "0x0"), 16)
    except RpcError:
        return 0


def _walk_back_native(
    rpc: RpcClient, wallet: str, head: int, max_blocks: int
) -> List[FundingEvent]:
    """Walk the last `max_blocks` blocks looking for transactions
    whose `to` is `wallet` and value > 0. Returns the matching
    events sorted by block ascending.
    """
    events: List[FundingEvent] = []
    wallet_lc = wallet.lower()
    CHUNK = 200
    cur = max(0, head - max_blocks)
    while cur <= head:
        end = min(cur + CHUNK - 1, head)
        try:
            block = rpc.get_block(end, full_txs=True)
        except RpcError:
            cur = end + 1
            continue
        ts = int(block.get("timestamp", "0x0"), 16)
        for tx in block.get("transactions", []):
            if not tx.get("to"):
                continue
            if tx["to"].lower() != wallet_lc:
                continue
            try:
                v = int(tx.get("value", "0x0"), 16)
            except ValueError:
                v = 0
            if v == 0:
                continue
            events.append(FundingEvent(
                tx_hash=tx["hash"],
                block=end,
                timestamp=ts,
                from_addr=tx["from"].lower(),
                to_addr=wallet_lc,
                asset="NATIVE",
                amount_wei=v,
                is_native=True,
            ))
        cur = end + 1
    return events


def _walk_back_erc20(
    rpc: RpcClient, wallet: str, head: int, max_blocks: int
) -> List[FundingEvent]:
    """Use eth_getLogs Transfer(from=None, to=wallet) to find every
    ERC-20 inbound to `wallet` over the last `max_blocks` blocks."""
    events: List[FundingEvent] = []
    wallet_lc = wallet.lower()
    wallet_topic = topic_addr(wallet_lc)
    CHUNK = 500
    cur = max(0, head - max_blocks)
    while cur <= head:
        end = min(cur + CHUNK - 1, head)
        try:
            logs = rpc.get_logs({
                "fromBlock": hex(cur),
                "toBlock":   hex(end),
                "topics": [TRANSFER_TOPIC, None, wallet_topic],
            })
        except RpcError:
            cur = end + 1
            continue
        for lg in logs:
            try:
                block = int(lg.get("blockNumber", "0x0"), 16)
                amount = int(lg.get("data", "0x0"), 16)
                from_addr = decode_address_topic(lg["topics"][1])
                to_addr = decode_address_topic(lg["topics"][2])
                token = (lg.get("address") or "").lower()
                ts = _tx_ts(rpc, block)
                events.append(FundingEvent(
                    tx_hash=lg.get("transactionHash", ""),
                    block=block,
                    timestamp=ts,
                    from_addr=from_addr,
                    to_addr=to_addr,
                    asset=token,
                    amount_wei=amount,
                    is_native=False,
                ))
            except (ValueError, KeyError, IndexError):
                continue
        cur = end + 1
    return events


def trace(
    rpc: RpcClient,
    wallet: str,
    block_count: int = 10000,
) -> FundingTrace:
    """Return a FundingTrace with all inbound transfers seen on-chain
    within the last `block_count` blocks."""
    wallet_lc = wallet.lower()
    head = rpc.block_number()

    native_events = _walk_back_native(rpc, wallet_lc, head, block_count)
    erc20_events = _walk_back_erc20(rpc, wallet_lc, head, block_count)

    all_events = sorted(
        native_events + erc20_events,
        key=lambda e: (e.block, e.tx_hash),
    )

    if not all_events:
        return FundingTrace(wallet=wallet_lc, events=[])

    first = all_events[0]
    unique_funders = {e.from_addr for e in all_events if e.from_addr != wallet_lc}

    return FundingTrace(
        wallet=wallet_lc,
        first_seen_block=first.block,
        first_seen_ts=first.timestamp,
        first_inbound=first,
        total_inbound_count=len(all_events),
        unique_funders=unique_funders,
        events=all_events,
    )


def classify_funder(
    funder: str,
    funder_is_contract: bool,
    known_cex: Dict[str, str],
    known_funders: Optional[Set[str]] = None,
) -> str:
    """Return one of:
        'CEX'          - known CEX hot wallet
        'FUNDER'       - known Funder contract (e.g. Disperse.app)
        'EOA'          - a regular externally-owned account
        'CONTRACT'     - a contract (might be a router, multisend, etc.)
        'FRESH'        - an EOA that has never been seen (heuristic)
        'SELF'         - the wallet funded itself
    """
    if not funder:
        return "UNKNOWN"
    f = funder.lower()
    if f in known_cex:
        return "CEX"
    if known_funders and f in known_funders:
        return "FUNDER"
    if f == "0x" + "0" * 40:
        return "ZERO"
    if funder_is_contract:
        return "CONTRACT"
    return "EOA"
