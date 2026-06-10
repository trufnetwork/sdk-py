from typing import Optional, Sequence, Union

from eth_hash.auto import keccak

import trufnetwork_sdk_c_bindings.exports as truf_sdk

# Modular Agent Address (MAA) derivation.
#
# These three pure functions let a caller compute an agent wallet's identifiers OFF-CHAIN, before the
# wallet exists on-chain — so a creator can publish a rule_id and a funder can know the exact MAA
# address to fund before sending a single token. They are a byte-exact mirror of the node precompiles
# (tn_utils.compute_rules_hash / derive_rule_id / derive_maa_address, migration 048) and every other SDK:
#
#   compute_rules_hash(...)  -> keccak256(RULES_PREIMAGE)            32 bytes (token-agnostic, NO bridge)
#   derive_rule_id(...)      -> keccak256(RULE_ID_PREIMAGE)          32 bytes, NOT truncated (an identifier)
#   derive_maa_address(...)  -> keccak256(ADDRESS_PREIMAGE)[12:32]   20-byte ETH address that holds funds
#
# The exact byte layout is frozen network-wide: one byte of disagreement derives a different address and
# would send funds to the wrong wallet. keccak here is Ethereum/legacy Keccak (eth_hash), NOT NIST
# SHA3-256. Hashing is always over RAW bytes.

_MAA_VERSION = 0x01
_MAX_UINT256 = (1 << 256) - 1

BytesLike = Union[bytes, bytearray, str, None]


def generate_stream_id(name: str) -> str:
    """
    Create a hash from a name, to be used as a stream ID. Must be unique among a dataprovider's streams.
    """
    return truf_sdk.GenerateStreamId(name)


def _to_bytes(value: BytesLike) -> bytes:
    """Normalize bytes / a 0x-hex string (with or without prefix) / None to raw bytes."""
    if value is None:
        return b""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            return b""
        if s.startswith(("0x", "0X")):
            s = s[2:]
        return bytes.fromhex(s)
    raise TypeError(f"expected bytes or hex string, got {type(value).__name__}")


def compute_rules_hash(
    fee_mode: str,
    fee_bps: int,
    fee_flat: Union[int, str],
    namespaces: Optional[Sequence[str]] = None,
    actions: Optional[Sequence[str]] = None,
    body_hashes: Optional[Sequence[BytesLike]] = None,
) -> bytes:
    """
    Build the canonical RULES_PREIMAGE and return its keccak256 (32 bytes).

    Layout: version(0x01) | fee_mode(0x00 bps / 0x01 flat) | fee_bps(uint32 BE) | fee_flat(uint256 BE,
    32 bytes) | count(uint16 BE) | for each canonical entry: u8len+namespace | u8len+action |
    has_body(0x00 absent / 0x01 present) | [body_hash 32 bytes if present]. Entries are canonicalized by
    (1) deduplicating on (namespace, action) — last write wins for the body_hash — then (2) sorting
    ascending bytewise on the raw UTF-8 namespace, then action. fee_flat is a base-unit integer or
    decimal string.

    body_hashes may be omitted/None for a non-empty allow-list (all unpinned); otherwise it must be the
    same length as namespaces/actions (a None/empty element is an unpinned entry).
    """
    ns_list = list(namespaces or [])
    act_list = list(actions or [])
    if not body_hashes:
        bh_list: list = [None] * len(ns_list)
    else:
        bh_list = list(body_hashes)
    if not (len(ns_list) == len(act_list) == len(bh_list)):
        raise ValueError(
            "namespaces/actions/body_hashes must be equal length "
            f"({len(ns_list)}/{len(act_list)}/{len(bh_list)})"
        )

    if fee_mode == "bps":
        fee_mode_byte = 0x00
    elif fee_mode == "flat":
        fee_mode_byte = 0x01
    else:
        raise ValueError(f"fee_mode must be 'bps' or 'flat', got {fee_mode!r}")

    fee_bps = int(fee_bps)
    if fee_bps < 0 or fee_bps > 0xFFFFFFFF:
        raise ValueError(f"fee_bps out of uint32 range: {fee_bps}")

    fee_flat_int = 0 if fee_flat in (None, "") else int(fee_flat)
    if fee_flat_int < 0:
        raise ValueError(f"fee_flat must be non-negative: {fee_flat}")
    if fee_flat_int > _MAX_UINT256:
        raise ValueError(f"fee_flat exceeds 2^256: {fee_flat}")

    # Canonicalize: dedup by (namespace, action) last-write-wins, then sort bytewise on raw UTF-8.
    dedup: dict = {}
    for ns, act, bh in zip(ns_list, act_list, bh_list):
        bh_bytes = _to_bytes(bh)
        if len(bh_bytes) not in (0, 32):
            raise ValueError(f"body_hash for {ns}.{act} must be 32 bytes, got {len(bh_bytes)}")
        dedup[(ns, act)] = (ns, act, bh_bytes)
    entries = sorted(dedup.values(), key=lambda e: (e[0].encode("utf-8"), e[1].encode("utf-8")))
    if len(entries) > 0xFFFF:
        raise ValueError(f"too many allow-list entries: {len(entries)}")

    buf = bytearray()
    buf.append(_MAA_VERSION)
    buf.append(fee_mode_byte)
    buf += fee_bps.to_bytes(4, "big")
    buf += fee_flat_int.to_bytes(32, "big")
    buf += len(entries).to_bytes(2, "big")
    for ns, act, bh_bytes in entries:
        ns_bytes = ns.encode("utf-8")
        act_bytes = act.encode("utf-8")
        if len(ns_bytes) > 0xFF:
            raise ValueError(f"namespace exceeds 255 bytes: {ns!r}")
        if len(act_bytes) > 0xFF:
            raise ValueError(f"action exceeds 255 bytes: {act!r}")
        buf.append(len(ns_bytes))
        buf += ns_bytes
        buf.append(len(act_bytes))
        buf += act_bytes
        if len(bh_bytes) == 0:
            buf.append(0x00)
        else:
            buf.append(0x01)
            buf += bh_bytes

    return keccak(bytes(buf))


def derive_rule_id(restricted: BytesLike, rules_hash: BytesLike, salt: BytesLike = None) -> bytes:
    """
    Build RULE_ID_PREIMAGE = version(0x01) | restricted(20) | rules_hash(32) | salt and return the FULL
    32-byte keccak256. rule_id is an identifier (the handle a funder passes to maa_join), not a fundable
    address, so it is NOT truncated. salt may be empty.
    """
    r = _to_bytes(restricted)
    rh = _to_bytes(rules_hash)
    s = _to_bytes(salt)
    if len(r) != 20:
        raise ValueError(f"restricted must be 20 bytes, got {len(r)}")
    if len(rh) != 32:
        raise ValueError(f"rules_hash must be 32 bytes, got {len(rh)}")
    return keccak(bytes([_MAA_VERSION]) + r + rh + s)


def derive_maa_address(unrestricted: BytesLike, restricted: BytesLike, rule_id: BytesLike) -> bytes:
    """
    Build ADDRESS_PREIMAGE = version(0x01) | unrestricted(20) | restricted(20) | rule_id(32) and return
    the low 20 bytes of its keccak256 — the Ethereum-style MAA address that holds funds. The composite
    (unrestricted, restricted, rule_id) means one rule can be funded by many owners, each producing a
    distinct wallet.
    """
    u = _to_bytes(unrestricted)
    r = _to_bytes(restricted)
    rid = _to_bytes(rule_id)
    if len(u) != 20:
        raise ValueError(f"unrestricted must be 20 bytes, got {len(u)}")
    if len(r) != 20:
        raise ValueError(f"restricted must be 20 bytes, got {len(r)}")
    if len(rid) != 32:
        raise ValueError(f"rule_id must be 32 bytes, got {len(rid)}")
    full = keccak(bytes([_MAA_VERSION]) + u + r + rid)
    return full[12:32]


def derive_maa_address_hex(unrestricted: BytesLike, restricted: BytesLike, rule_id: BytesLike) -> str:
    """Convenience: the 0x-prefixed lowercase hex of derive_maa_address."""
    return "0x" + derive_maa_address(unrestricted, restricted, rule_id).hex()
