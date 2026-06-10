"""
Golden vectors for the Modular Agent Address (MAA) derivation.

They are frozen network-wide and are asserted byte-for-byte by the node precompiles and every SDK — a
mismatch here means this SDK would derive a different agent-wallet address than the chain, sending funds
to the wrong wallet. Keep these in lockstep with node extensions/tn_utils/maa_test.go and the spec.

This is a pure unit test: no network, no node, no fixtures.
"""

import pytest

from trufnetwork_sdk_py.utils import (
    compute_rules_hash,
    derive_maa_address,
    derive_maa_address_hex,
    derive_rule_id,
)

RESTRICTED = b"\x11" * 20
UNRESTRICTED = b"\x22" * 20

RULES_HASH_A = "df0555d336647bec5e9fe1f6f613086bddf53548b67c52393aef6db4cbef062d"
RULE_ID_A = "a0b517da759b794e2484dc8b9dba8f5211a53dcdf26448f19c7c68699ff7bcf1"
MAA_A = "84da4dbca14d429c719d65a0bb76bd7fa3c5c349"

RULES_HASH_B = "0b1edb0ad70fb94287e50c7b3deaea7bba4e500c4ae6a764ed9021faf091274a"
RULE_ID_B = "21f40fbf0fd537f85d283cf7b5f2fe8602c1f4b910aad96ad2dad9f6e82b1ca5"
MAA_B = "cb009e348c3ad795aa6d7d81177f0daee4583128"


def test_compute_rules_hash_golden_vectors():
    # Vector A — bps fee, two actions (one body-pinned). Input order place,cancel proves the canonical
    # sort (cancel < place) is applied regardless of order. Token-agnostic (no bridge).
    rh_a = compute_rules_hash(
        "bps",
        250,
        "0",
        ["main", "main"],
        ["ob_place_order", "ob_cancel_order"],
        [b"\xcc" * 32, None],
    )
    assert rh_a.hex() == RULES_HASH_A

    # Vector B — flat fee 1e18, empty allow-list.
    rh_b = compute_rules_hash("flat", 0, "1000000000000000000", [], [], [])
    assert rh_b.hex() == RULES_HASH_B


def test_derive_rule_id_golden_vectors():
    id_a = derive_rule_id(RESTRICTED, bytes.fromhex(RULES_HASH_A), b"\xab" * 32)
    assert id_a.hex() == RULE_ID_A
    assert len(id_a) == 32  # untruncated identifier

    id_b = derive_rule_id(RESTRICTED, bytes.fromhex(RULES_HASH_B), None)  # empty salt
    assert id_b.hex() == RULE_ID_B


def test_derive_maa_address_golden_vectors():
    addr_a = derive_maa_address(UNRESTRICTED, RESTRICTED, bytes.fromhex(RULE_ID_A))
    assert addr_a.hex() == MAA_A
    assert len(addr_a) == 20

    addr_b = derive_maa_address(UNRESTRICTED, RESTRICTED, bytes.fromhex(RULE_ID_B))
    assert addr_b.hex() == MAA_B


def test_end_to_end_derivation_accepts_hex_strings():
    # The path a funder uses: raw inputs (as 0x-hex) through to the wallet to fund.
    rules_hash = compute_rules_hash(
        "bps",
        250,
        "0",
        ["main", "main"],
        ["ob_place_order", "ob_cancel_order"],
        ["0x" + "cc" * 32, None],
    )
    rule_id = derive_rule_id("0x" + "11" * 20, rules_hash, "0x" + "ab" * 32)
    assert derive_maa_address_hex("0x" + "22" * 20, "0x" + "11" * 20, rule_id) == "0x" + MAA_A


def test_compute_rules_hash_order_independent_and_dedup():
    base = compute_rules_hash(
        "bps", 250, "0", ["main", "main"], ["ob_place_order", "ob_cancel_order"], [b"\xcc" * 32, None]
    )
    # Reversed input order must produce the same hash (canonical sort).
    reordered = compute_rules_hash(
        "bps", 250, "0", ["main", "main"], ["ob_cancel_order", "ob_place_order"], [None, b"\xcc" * 32]
    )
    assert reordered == base
    # Duplicate (namespace, action) with a conflicting body_hash: the LAST occurrence wins.
    last_wins = compute_rules_hash(
        "bps",
        250,
        "0",
        ["main", "main", "main"],
        ["ob_place_order", "ob_cancel_order", "ob_place_order"],
        [b"\xdd" * 32, None, b"\xcc" * 32],
    )
    assert last_wins == base


def test_dedup_key_no_collision():
    # ("a b","c") and ("a","b c") are DISTINCT pairs and must not collide in the dedup key (the Python
    # impl keys on the (ns, action) tuple, which is collision-safe). If they collided, `both` would
    # collapse to the last entry and equal `only_second`. Locks cross-language parity.
    both = compute_rules_hash("bps", 0, "0", ["a b", "a"], ["c", "b c"])
    only_second = compute_rules_hash("bps", 0, "0", ["a"], ["b c"])
    assert both != only_second


def test_compute_rules_hash_validation():
    with pytest.raises(ValueError):
        compute_rules_hash("bogus", 0, "0")
    with pytest.raises(ValueError):
        compute_rules_hash("bps", 0, "-1")
    with pytest.raises(ValueError):
        compute_rules_hash("bps", 0, "0", ["main"], ["a"], [b"\x00" * 31])
    with pytest.raises(ValueError):
        compute_rules_hash("bps", 0, "0", ["main"], ["a", "b"], [None])


def test_derive_rejects_bad_lengths():
    with pytest.raises(ValueError):
        derive_rule_id(b"\x11" * 19, b"\x33" * 32, None)
    with pytest.raises(ValueError):
        derive_rule_id(b"\x11" * 20, b"\x33" * 31, None)
    with pytest.raises(ValueError):
        derive_maa_address(b"\x22" * 19, b"\x11" * 20, b"\x33" * 32)
    with pytest.raises(ValueError):
        derive_maa_address(b"\x22" * 20, b"\x11" * 20, b"\x33" * 31)


def test_funder_disambiguates_wallet():
    rule_id = b"\x33" * 32
    a1 = derive_maa_address(b"\x22" * 20, RESTRICTED, rule_id)
    a2 = derive_maa_address(b"\x44" * 20, RESTRICTED, rule_id)
    assert a1 != a2  # different funder -> different wallet under the same rule
    assert a1 == derive_maa_address(b"\x22" * 20, RESTRICTED, rule_id)  # deterministic
