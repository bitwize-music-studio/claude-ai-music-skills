"""Split a collected test session into deterministic shards for CI.

CI runs each OS's suite as several parallel jobs. With ``PYTEST_SHARD="i/n"``,
a run keeps every n-th collected test, starting at position i (1-based).
Round-robin by collection position, rather than hashing node ids, spreads each
file's tests across the shards. A file of uniformly slow tests (the
master_album flows) is therefore split evenly instead of landing on one shard.

Every xdist worker collects the same items in the same order, so all workers
of a shard agree on its contents.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")

ENV_VAR = "PYTEST_SHARD"


def parse_shard(spec: str) -> tuple[int, int]:
    """Parse ``"i/n"`` into ``(i, n)``, 1-based, with ``1 <= i <= n``."""
    try:
        index_text, total_text = spec.split("/")
        index, total = int(index_text), int(total_text)
    except ValueError:
        raise ValueError(f"{ENV_VAR} must look like 'i/n', got {spec!r}") from None
    if total < 1 or not 1 <= index <= total:
        raise ValueError(f"{ENV_VAR}={spec!r}: need 1 <= i <= n")
    return index, total


def split(items: Sequence[T], index: int, total: int) -> tuple[list[T], list[T]]:
    """Return ``(kept, dropped)``: every ``total``-th item from position ``index``."""
    kept: list[T] = []
    dropped: list[T] = []
    for position, item in enumerate(items):
        (kept if position % total == index - 1 else dropped).append(item)
    return kept, dropped
