"""Tests for the CI shard selection in tests/sharding.py."""

import pytest

from tests import sharding


@pytest.mark.parametrize("total", [1, 2, 3, 4])
def test_shards_partition_the_session_exactly(total):
    """Across all shards, every test runs exactly once."""
    items = [f"test_{i}" for i in range(11)]
    seen = []
    for index in range(1, total + 1):
        kept, dropped = sharding.split(items, index, total)
        assert sorted(kept + dropped) == sorted(items)
        seen += kept
    assert sorted(seen) == sorted(items)
    assert len(seen) == len(set(seen))


def test_neighbouring_tests_go_to_different_shards():
    """A file's tests sit together in collection order and must be spread out."""
    items = ["slow_1", "slow_2", "slow_3", "slow_4"]
    assert sharding.split(items, 1, 2)[0] == ["slow_1", "slow_3"]
    assert sharding.split(items, 2, 2)[0] == ["slow_2", "slow_4"]


@pytest.mark.parametrize("spec, expected", [("1/1", (1, 1)), ("1/2", (1, 2)), ("2/2", (2, 2)), ("3/5", (3, 5))])
def test_parse_shard_accepts_i_of_n(spec, expected):
    assert sharding.parse_shard(spec) == expected


@pytest.mark.parametrize("spec", ["", "1", "0/2", "3/2", "a/b", "1/0", "1/2/3", "-1/2"])
def test_parse_shard_rejects_malformed_specs(spec):
    with pytest.raises(ValueError):
        sharding.parse_shard(spec)
