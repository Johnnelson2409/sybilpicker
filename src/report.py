"""
report.py - Format a sybil score report for human or agent consumption.

Input: a JSON object with these top-level keys:
  - wallet, chain_id
  - first_seen_block, first_seen_ts, first_inbound
  - total_inbound_count, unique_funder_count
  - signals: [{name, score, detail}, ...]
  - score: int 0-100
  - label: "HUMAN" / "LOW_RISK" / "MEDIUM_RISK" / "HIGH_RISK" / "LIKELY_SYBIL"
  - action: human-readable recommendation
  - dominant_signal: {name, score, detail}
"""
from __future__ import annotations
import argparse
import json
import sys
from typing import Any, Dict


def _short_addr(a: str, head: int = 6, tail: int = 4) -> str:
    if not a or len(a) < head + tail + 2:
        return a or ""
    return f"{a[:2+head]}…{a[-tail:]}"


def _fmt_age(ts: int, head_ts: int) -> str:
    if ts <= 0:
        return "unknown"
    days = (head_ts - ts) / 86400
    if days < 1:
        return f"{(head_ts - ts) / 3600:.1f}h"
    if days < 30:
        return f"{days:.1f}d"
    if days < 365:
        return f"{days/30:.1f}mo"
    return f"{days/365:.1f}y"


def _bar(score_01: float, width: int = 20) -> str:
    n = int(round(score_01 * width))
    return "█" * n + "░" * (width - n)


LABEL_COLOR = {
    "HUMAN":         "\033[32m",  # green
    "LOW_RISK":      "\033[36m",  # cyan
    "MEDIUM_RISK":   "\033[33m",  # yellow
    "HIGH_RISK":     "\033[31m",  # red
    "LIKELY_SYBIL":  "\033[35m",  # magenta
}
RESET = "\033[0m"


def render_text(r: Dict[str, Any], use_color: bool = True) -> str:
    head_ts = r.get("head_ts", 0)
    color = LABEL_COLOR.get(r["label"], "") if use_color else ""
    reset = RESET if use_color else ""
    first_inb = r.get("first_inbound")
    lines = []
    lines.append("=" * 64)
    lines.append(f"  SYBIL SCORE — {r['wallet']}")
    lines.append(f"  Chain ID: {r['chain_id']}")
    lines.append("=" * 64)
    lines.append("")
    if first_inb:
        lines.append(f"  First seen:    block {first_inb.get('block', '?')} "
                     f"({_fmt_age(first_inb.get('timestamp', 0), head_ts)} ago)")
        lines.append(f"  First funder:  {_short_addr(first_inb.get('from_addr',''))}  "
                     f"[{first_inb.get('asset_label','?')}]")
    else:
        lines.append("  First seen:    (no inbound transfers in range)")
    lines.append(f"  Total inbound: {r.get('total_inbound_count', 0)}")
    lines.append(f"  Unique funder(s): {r.get('unique_funder_count', 0)}")
    lines.append("")
    lines.append("  Per-signal scores (0 = human, 1 = sybil)")
    lines.append("  " + "-" * 60)
    for s in r.get("signals", []):
        lines.append(f"  {s['name']:<22} [{_bar(s['score'])}] {s['score']:.2f}")
        lines.append(f"  {'':<22}   {s['detail']}")
    lines.append("")
    lines.append(f"  >>> SYBIL SCORE: {r['score']} / 100  ({color}{r['label']}{reset}) <<<")
    lines.append(f"      {r['action']}")
    dom = r.get("dominant_signal")
    if dom:
        lines.append(f"      Dominant signal: {dom['name']} ({dom['score']:.2f})")
    return "\n".join(lines) + "\n"


def render_markdown(r: Dict[str, Any]) -> str:
    head_ts = r.get("head_ts", 0)
    first_inb = r.get("first_inbound")
    lines = []
    lines.append(f"# Sybil Score — `{r['wallet']}`")
    lines.append("")
    lines.append(f"- **Chain ID:** {r['chain_id']}")
    if first_inb:
        lines.append(f"- **First seen:** block {first_inb.get('block','?')} "
                     f"({_fmt_age(first_inb.get('timestamp', 0), head_ts)} ago)")
        lines.append(f"- **First funder:** `{first_inb.get('from_addr','')}` [{first_inb.get('asset_label','?')}]")
    else:
        lines.append(f"- **First seen:** (no inbound transfers in range)")
    lines.append(f"- **Total inbound:** {r.get('total_inbound_count', 0)}")
    lines.append(f"- **Unique funder(s):** {r.get('unique_funder_count', 0)}")
    lines.append("")
    lines.append(f"## 🎯 Sybil score: **{r['score']} / 100** ({r['label']})")
    lines.append("")
    lines.append(f"> {r['action']}")
    lines.append("")
    lines.append("## Per-signal scores")
    lines.append("")
    lines.append("| Signal | Score (0=human, 1=sybil) | Detail |")
    lines.append("|--------|--------------------------|--------|")
    for s in r.get("signals", []):
        lines.append(f"| `{s['name']}` | {s['score']:.2f} | {s['detail']} |")
    return "\n".join(lines) + "\n"


def render_html(r: Dict[str, Any]) -> str:
    head_ts = r.get("head_ts", 0)
    first_inb = r.get("first_inbound")
    label_color = {
        "HUMAN":         "#1e8e3e",
        "LOW_RISK":      "#0b8043",
        "MEDIUM_RISK":   "#f9ab00",
        "HIGH_RISK":     "#d93025",
        "LIKELY_SYBIL":  "#a50e0e",
    }.get(r["label"], "#202124")
    rows = "".join(
        f"<tr><td><code>{s['name']}</code></td>"
        f"<td style='width:40%;'><div style='background:linear-gradient(to right, #d93025 {s['score']*100:.0f}%, #f1f3f4 {s['score']*100:.0f}%); "
        f"height:14px; border-radius:3px;'></div></td>"
        f"<td style='font-family:monospace; text-align:right;'>{s['score']:.2f}</td>"
        f"<td style='font-size:13px;'>{s['detail']}</td></tr>"
        for s in r.get("signals", [])
    )
    first_seen = (
        f"block {first_inb.get('block','?')} ({_fmt_age(first_inb.get('timestamp', 0), head_ts)} ago)"
        if first_inb else "(no inbound in range)"
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>Sybil Score — {r['wallet']}</title>
<style>
  body {{ font: 14px/1.4 system-ui, sans-serif; max-width: 900px; margin: 32px auto; padding: 0 16px; color: #202124; }}
  h1 {{ border-bottom: 2px solid #202124; padding-bottom: 4px; }}
  .score {{ font-size: 36px; font-weight: 800; color: {label_color}; margin: 12px 0 4px; }}
  .action {{ font-size: 16px; color: #5f6368; margin-bottom: 16px; }}
  .meta {{ background: #f8f9fa; border-left: 3px solid #1a73e8; padding: 8px 12px; font-size: 13px; margin-bottom: 16px; }}
  .meta ul {{ margin: 0; padding-left: 18px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 8px; }}
  th, td {{ border: 1px solid #dadce0; padding: 6px 8px; text-align: left; font-size: 13px; vertical-align: middle; }}
  th {{ background: #f8f9fa; }}
  code {{ background: #f1f3f4; padding: 1px 4px; border-radius: 3px; }}
</style></head><body>
<h1>Sybil Score</h1>
<p class="score">{r['score']} / 100</p>
<p class="action">{r['label']} &middot; {r['action']}</p>

<div class="meta">
<ul>
<li><strong>Wallet:</strong> <code>{r['wallet']}</code></li>
<li><strong>Chain ID:</strong> {r['chain_id']}</li>
<li><strong>First seen:</strong> {first_seen}</li>
<li><strong>Total inbound:</strong> {r.get('total_inbound_count', 0)}</li>
<li><strong>Unique funder(s):</strong> {r.get('unique_funder_count', 0)}</li>
</ul>
</div>

<h2>Per-signal scores</h2>
<table>
<thead><tr><th>Signal</th><th>Bar</th><th>Score</th><th>Detail</th></tr></thead>
<tbody>
{rows or "<tr><td colspan='4'>No signals computed</td></tr>"}
</tbody>
</table>
</body></html>
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="input", default="-")
    p.add_argument("--format", choices=["text", "markdown", "html", "json"], default="text")
    p.add_argument("--out", default="-")
    p.add_argument("--no-color", action="store_true")
    args = p.parse_args()

    raw = sys.stdin.read() if args.input == "-" else open(args.input).read()
    r = json.loads(raw)

    if args.format == "json":
        out = json.dumps(r, indent=2)
    elif args.format == "markdown":
        out = render_markdown(r)
    elif args.format == "html":
        out = render_html(r)
    else:
        out = render_text(r, use_color=not args.no_color)

    if args.out == "-":
        sys.stdout.write(out)
    else:
        with open(args.out, "w") as f:
            f.write(out)


if __name__ == "__main__":
    main()
