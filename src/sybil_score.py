"""
sybil_score.py - CLI entry point.

Usage:
  python sybil_score.py --wallet 0x... --rpc-url https://...
                         [--block-count 10000] [--format json]
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from typing import Any, Dict, List, Optional, Set

from rpc import RpcClient, RpcError
from funding import trace as trace_funding, BUILTIN_CEX_HOT_WALLETS, FundingTrace
from signals import compute_all, SignalResult
from scorer import score, label, action, dominant_signal, WEIGHTS


def _trace_to_dict(t: FundingTrace) -> Dict[str, Any]:
    if t.first_inbound is None:
        first = None
    else:
        e = t.first_inbound
        asset_label = "NATIVE" if e.is_native else f"ERC-20 {e.asset[:10]}…"
        first = {
            "tx_hash":   e.tx_hash,
            "block":     e.block,
            "timestamp": e.timestamp,
            "from_addr": e.from_addr,
            "to_addr":   e.to_addr,
            "asset":     e.asset,
            "asset_label": asset_label,
            "amount_wei": e.amount_wei,
            "is_native": e.is_native,
        }
    return {
        "first_inbound":      first,
        "first_seen_block":   t.first_seen_block,
        "first_seen_ts":      t.first_seen_ts,
        "total_inbound_count": t.total_inbound_count,
        "unique_funder_count": len(t.unique_funders),
        "events": [
            {
                "tx_hash": e.tx_hash,
                "block":   e.block,
                "ts":      e.timestamp,
                "from":    e.from_addr,
                "to":      e.to_addr,
                "asset":   e.asset,
                "amount_wei": e.amount_wei,
                "is_native": e.is_native,
            }
            for e in t.events[:200]  # cap to keep the JSON small
        ],
    }


def _signals_to_dict(signals: List[SignalResult]) -> List[Dict[str, Any]]:
    return [{"name": s.name, "score": s.score, "detail": s.detail} for s in signals]


def run(args: argparse.Namespace) -> Dict[str, Any]:
    rpc = RpcClient(args.rpc_url)
    try:
        chain_id = rpc.chain_id()
    except RpcError as e:
        raise SystemExit(f"error: cannot reach RPC: {e}")

    # Build known-funder set
    known_cex = dict(BUILTIN_CEX_HOT_WALLETS)
    known_funders: Optional[Set[str]] = None
    if args.known_funders:
        try:
            with open(args.known_funders) as f:
                raw = json.load(f)
            if isinstance(raw, list):
                known_funders = {x.lower() for x in raw if isinstance(x, str)}
            elif isinstance(raw, dict):
                # { "name": "0xaddr" }
                known_funders = {v.lower() for v in raw.values() if isinstance(v, str)}
        except Exception as e:  # noqa: BLE001
            print(f"[!] could not read known-funders: {e}", file=sys.stderr)

    # Trace funding
    print(f"[+] Tracing funding for {args.wallet} (last {args.block_count} blocks)…", file=sys.stderr)
    t = trace_funding(rpc, args.wallet, args.block_count)

    # Compute signals
    head_ts = int(time.time())
    signals = compute_all(rpc, args.wallet, t, known_cex, known_funders, head_ts=head_ts)

    s = score(signals)
    lab = label(s)
    act = action(lab)
    dom = dominant_signal(signals)

    payload = {
        "wallet":     args.wallet,
        "chain_id":   chain_id,
        "head_ts":    head_ts,
        **_trace_to_dict(t),
        "signals":    _signals_to_dict(signals),
        "score":      s,
        "label":      lab,
        "action":     act,
        "dominant_signal": (
            {"name": dom.name, "score": dom.score, "detail": dom.detail}
            if dom is not None else None
        ),
        "weights":    WEIGHTS,
    }
    return payload


def main():
    p = argparse.ArgumentParser(description="Estimate the sybil score of a wallet.")
    p.add_argument("--wallet", required=True, help="0x address to analyze")
    p.add_argument("--rpc-url", required=True, help="JSON-RPC endpoint")
    p.add_argument("--block-count", type=int, default=10000, help="How many recent blocks to scan")
    p.add_argument("--known-funders", default=None,
                   help="Path to JSON list of known Funder contract addresses")
    p.add_argument("--format", choices=["text", "json", "markdown", "html"], default="text")
    p.add_argument("--out", default="-")
    args = p.parse_args()

    payload = run(args)

    if args.format == "json":
        out = json.dumps(payload, indent=2)
    elif args.format == "markdown":
        from report import render_markdown
        out = render_markdown(payload)
    elif args.format == "html":
        from report import render_html
        out = render_html(payload)
    else:
        from report import render_text
        out = render_text(payload, use_color=sys.stdout.isatty())

    if args.out == "-":
        sys.stdout.write(out)
    else:
        with open(args.out, "w") as f:
            f.write(out)


if __name__ == "__main__":
    main()
