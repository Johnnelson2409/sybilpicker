"""
rpc.py - JSON-RPC client for sybil detection.

Uses plain HTTP + eth_getLogs / eth_getBlockByNumber / eth_call.
No web3 framework dependency.
"""
from __future__ import annotations
import time
import requests
from typing import Any, Dict, List, Optional


class RpcError(Exception):
    pass


class RpcClient:
    def __init__(self, url: str, timeout: int = 30, max_retries: int = 4):
        self.url = url
        self.timeout = timeout
        self.max_retries = max_retries
        self._id = 0

    def call(self, method: str, params: List[Any]) -> Any:
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                r = requests.post(self.url, json=payload, timeout=self.timeout)
                if r.status_code == 429 or r.status_code >= 500:
                    raise RpcError(f"HTTP {r.status_code}: {r.text[:200]}")
                data = r.json()
                if "error" in data:
                    raise RpcError(data["error"].get("message", "rpc error"))
                return data.get("result")
            except (requests.RequestException, RpcError) as e:
                last_err = e
                time.sleep(0.4 * (2 ** attempt))
        raise RpcError(f"RPC {method} failed after {self.max_retries} attempts: {last_err}")

    def block_number(self) -> int:
        return int(self.call("eth_blockNumber", []), 16)

    def get_block(self, num: int, full_txs: bool = True) -> Dict[str, Any]:
        return self.call("eth_getBlockByNumber", [hex(num), full_txs])

    def get_tx(self, tx_hash: str) -> Dict[str, Any]:
        return self.call("eth_getTransactionByHash", [tx_hash])

    def get_tx_receipt(self, tx_hash: str) -> Dict[str, Any]:
        return self.call("eth_getTransactionReceipt", [tx_hash])

    def get_logs(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.call("eth_getLogs", [params])

    def get_code(self, addr: str) -> str:
        return self.call("eth_getCode", [addr, "latest"]) or "0x"

    def chain_id(self) -> int:
        return int(self.call("eth_chainId", []), 16)


# ERC-20 Transfer event topic
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def topic_addr(a: str) -> str:
    """Convert an address to a 32-byte topic (left-padded with zeros)."""
    a = a.lower()
    if a.startswith("0x"):
        a = a[2:]
    return "0x" + a.rjust(64, "0")


def decode_address_topic(topic: str) -> str:
    return "0x" + topic[-40:].lower()
