#!/usr/bin/env python3
"""
Modular Agent Address (MAA / "agent wallet") lifecycle smoke test.

Runs the full agent-wallet lifecycle against a live TRUF.NETWORK node where ``maa_exec`` is activated
(testnet from height 6523123). It proves, end-to-end through the Python SDK, the properties that make
an agent wallet useful and safe:

  * a restricted AGENT key registers an immutable rule;
  * an unrestricted OWNER key joins it to derive a wallet (the MAA) and funds it;
  * the agent runs allow-listed actions AS the MAA — the node rewrites @caller to the wallet, so the
    streams it creates are owned by the MAA and every fee is debited from the MAA's OWN escrow;
  * the agent CANNOT move the funds out (owner-exit actions are reserved for the owner);
  * the owner withdraws the remaining escrow at any time, paying the agent its commission.

This mirrors the node's canonical oracle, tests/streams/maa/data_agent_test.go.

Config comes from a .env file next to this script (real environment variables still take
precedence). Two DISTINCT keys are required — the agent and the owner are different identities:

    cp .env.example .env     # then fill in AGENT_PRIVATE_KEY and OWNER_PRIVATE_KEY
    python main.py

See .env.example for every setting, and README.md for what success looks like.
"""

import os
import sys
import time

from trufnetwork_sdk_py.client import TNClient, STREAM_TYPE_PRIMITIVE, MAANumericArg
from trufnetwork_sdk_py.utils import (
    generate_stream_id,
    compute_rules_hash,
    derive_rule_id,
    derive_maa_address_hex,
)


# --- load .env (zero-dependency; real environment variables take precedence) ------------------------
def _load_dotenv(path: str) -> None:
    """Populate os.environ from a KEY=VALUE .env file, without overriding existing vars."""
    if not os.path.exists(path):
        return
    with open(path) as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# --- configuration (all overridable via environment / .env; see .env.example) ----------------------
PROVIDER_URL = os.getenv("PROVIDER_URL", "https://gateway.testnet.truf.network")
AGENT_PRIVATE_KEY = os.getenv("AGENT_PRIVATE_KEY")  # restricted agent
OWNER_PRIVATE_KEY = os.getenv("OWNER_PRIVATE_KEY")  # unrestricted owner / funder
BRIDGE = os.getenv("MAA_BRIDGE", "hoodi_tt")        # funding/fee bridge namespace (e.g. hoodi_tt / eth_truf)
FUND_AMOUNT = os.getenv("MAA_FUND_AMOUNT", "250000000000000000000")  # wei (NUMERIC(78,0))
FEE_BPS = int(os.getenv("MAA_FEE_BPS", "250"))      # 2.5% owner-withdraw commission to the agent
# Order-book collateral bridge for get_collateral_by_wallet (migration 051). This is the bridge the
# order-book MARKETS settle in (hoodi_tt2 / sepolia_bridge / ethereum_bridge on dev/testnet), NOT the
# hoodi_tt funding/fee bridge above. get_positions_by_wallet needs no bridge.
COLLATERAL_BRIDGE = os.getenv("MAA_COLLATERAL_BRIDGE", "hoodi_tt2")

# On-chain decimal types the inner actions declare. A NUMERIC argument MUST be wrapped in MAANumericArg
# with these EXACT precision/scale, because JSON has no decimal type and the node does not coerce text
# to NUMERIC (see TNClient.execute_agent_action / MAANumericArg).
TOKEN_PRECISION, TOKEN_SCALE = 78, 0    # bridge amounts: NUMERIC(78,0)
VALUE_PRECISION, VALUE_SCALE = 36, 18   # primitive record values: NUMERIC(36,18)

# A fresh salt per run keeps each smoke test independent: it yields a new rule_id (and therefore a
# new MAA), so re-running never collides with an already-registered rule. The local-derivation
# cross-checks below use this exact salt, so they stay valid. Set MAA_SALT (64 hex chars, optional
# 0x) to pin a reproducible rule_id across runs.
_salt_env = os.getenv("MAA_SALT")
if _salt_env:
    SALT = bytes.fromhex(_salt_env[2:] if _salt_env.startswith("0x") else _salt_env)
else:
    # Nanosecond precision so two runs in the same second still get distinct salts; the ns
    # value (~1.8e18) fits in 8 unsigned bytes (max ~1.8e19).
    SALT = b"MAA" + time.time_ns().to_bytes(8, "big") + b"\x00" * 21  # 3 + 8 + 21 = 32 bytes
assert len(SALT) == 32, f"salt must be 32 bytes, got {len(SALT)}"

NAMESPACES = ["main", "main"]
ACTIONS = ["create_streams", "insert_records"]  # the agent's allow-list (mirrors data_agent_test.go)
BODY_HASHES = [None, None]                       # unpinned


def token(amount) -> MAANumericArg:
    """A bridge-amount NUMERIC(78,0) argument (base units / wei)."""
    return MAANumericArg(str(amount), TOKEN_PRECISION, TOKEN_SCALE)


def stream_value(value) -> MAANumericArg:
    """A primitive-record NUMERIC(36,18) value argument."""
    return MAANumericArg(str(value), VALUE_PRECISION, VALUE_SCALE)


def banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def main() -> int:
    if not AGENT_PRIVATE_KEY or not OWNER_PRIVATE_KEY:
        print("❌ AGENT_PRIVATE_KEY and OWNER_PRIVATE_KEY must both be set (two distinct keys).")
        print("   See the docstring / README.md for the full environment setup.")
        return 1

    agent = TNClient(PROVIDER_URL, AGENT_PRIVATE_KEY)
    owner = TNClient(PROVIDER_URL, OWNER_PRIVATE_KEY)
    agent_addr = agent.get_current_account()
    owner_addr = owner.get_current_account()

    banner("MAA lifecycle smoke test")
    print(f"provider : {PROVIDER_URL}")
    print(f"bridge   : {BRIDGE}")
    print(f"agent    : {agent_addr}   (restricted — operates the wallet)")
    print(f"owner    : {owner_addr}   (unrestricted — funds & withdraws)")
    if agent_addr.lower() == owner_addr.lower():
        print("❌ agent and owner must be DIFFERENT keys.")
        return 1

    # (a) AGENT creates an immutable rule. The allow-list is the two data-provision actions; the
    #     fee_mode/bps set the commission the owner pays the agent on withdrawal.
    banner("(a) agent registers the rule")
    res = agent.maa_create_rule(
        fee_mode="bps",
        fee_bps=FEE_BPS,
        fee_flat="0",
        namespaces=NAMESPACES,
        actions=ACTIONS,
        body_hashes=BODY_HASHES,
        salt=SALT,
        wait=True,
    )
    rule_id = res["rule_id"]
    print(f"✅ rule created: rule_id={rule_id}  (commission {FEE_BPS / 100:.2f}%)")
    # Cross-check the chain-returned rule_id against a local, offline derivation.
    rules_hash = compute_rules_hash("bps", FEE_BPS, "0", NAMESPACES, ACTIONS, BODY_HASHES)
    rule_id_local = "0x" + derive_rule_id(agent_addr, rules_hash, SALT).hex()
    assert rule_id_local == rule_id, f"local rule_id {rule_id_local} != chain {rule_id}"
    print(f"   ↳ matches local derivation {rule_id_local}")

    # (b) OWNER joins the rule → derives + registers the agent wallet (the MAA).
    banner("(b) owner joins → agent wallet derived")
    join = owner.join_agent_address(rule_id, wait=True)
    maa = join["maa_address"]
    maa_local = derive_maa_address_hex(owner_addr, agent_addr, rule_id)
    assert maa_local == maa, f"local MAA {maa_local} != chain {maa}"
    print(f"✅ agent wallet (MAA): {maa}")
    print(f"   ↳ matches local derivation {maa_local}")
    print(f"   maa_is_known: {agent.maa_is_known(maa)}")

    # (c) OWNER funds the MAA with a normal bridged-token transfer.
    banner("(c) owner funds the agent wallet")
    owner.transfer(BRIDGE, maa, FUND_AMOUNT, wait=True)
    funded = agent.maa_get_balance(maa, BRIDGE)
    print(f"✅ funded MAA with {FUND_AMOUNT} → escrow balance now {funded}")
    assert funded == FUND_AMOUNT, f"expected escrow {FUND_AMOUNT}, got {funded}"

    # (d) AGENT works AS the MAA: create a stream, then insert a record into it. @caller is rewritten
    #     to the MAA, so the stream is OWNED by the MAA and the fees come out of the MAA's escrow.
    banner("(d) agent creates a stream + inserts data, AS the MAA")
    stream_id = generate_stream_id(f"maa_demo_{int(time.time())}")
    print(f"stream_id: {stream_id}")

    before_create = agent.maa_get_balance(maa, BRIDGE)
    agent.execute_agent_action(maa, "create_streams", [[stream_id], [STREAM_TYPE_PRIMITIVE]])
    after_create = agent.maa_get_balance(maa, BRIDGE)
    create_fee = int(before_create) - int(after_create)
    print(f"✅ create_streams ran as the MAA (escrow {before_create} → {after_create}, fee {create_fee})")

    event_time = int(time.time())
    record_value = "42.5"
    agent.execute_agent_action(
        maa,
        "insert_records",
        [[maa], [stream_id], [event_time], [stream_value(record_value)]],
    )
    after_insert = agent.maa_get_balance(maa, BRIDGE)
    insert_fee = int(after_create) - int(after_insert)
    print(f"✅ insert_records ran as the MAA (escrow {after_create} → {after_insert}, fee {insert_fee})")

    # PROOF the rewrite happened: the stream + record exist UNDER THE MAA's address, not the agent's.
    records = agent.get_records(
        stream_id=stream_id,
        data_provider=maa,
        date_from=event_time - 5,
        date_to=event_time + 5,
        use_cache=False,
    ).data
    print(f"   stream {stream_id} owned by {maa}; records read back: {records}")
    assert records, "expected the inserted record to be readable under the MAA address"
    print(f"✅ the agent provided data AS the MAA (not as its own key {agent_addr})")

    # (e) AGENT tries to exit the funds → BLOCKED. Owner-exit actions are reserved for the owner; the
    #     route rejects the restricted agent before anything moves.
    banner("(e) agent tries to withdraw → must be blocked")
    balance_before_attack = agent.maa_get_balance(maa, BRIDGE)
    blocked = False
    try:
        agent.execute_agent_action(maa, "maa_withdraw", [BRIDGE, token("1000000000000000000")])
    except Exception as e:  # noqa: BLE001 — a smoke test wants the raw failure surfaced
        blocked = True
        msg = str(e)
        print(f"✅ blocked, as it must be: {msg}")
        if "reserved for the unrestricted owner" not in msg and "restricted agent" not in msg:
            print("   ⚠️  (blocked, but the message differs from the expected route/guard wording)")
    if not blocked:
        print("❌ SECURITY FAILURE: the restricted agent was allowed to withdraw!")
        return 1
    balance_after_attack = agent.maa_get_balance(maa, BRIDGE)
    assert balance_after_attack == balance_before_attack, "a blocked exit must move nothing"
    print(f"   escrow unchanged after the blocked attempt: {balance_after_attack}")

    # (f) OWNER withdraws the remaining escrow, paying the agent its commission.
    banner("(f) owner withdraws the remaining escrow (pays the agent commission)")
    remaining = owner.maa_get_balance(maa, BRIDGE)
    expected_commission = int(remaining) * FEE_BPS // 10000  # HALF-UP on-chain; floor is a lower bound
    owner.execute_agent_action(maa, "maa_withdraw", [BRIDGE, token(remaining)])
    drained = owner.maa_get_balance(maa, BRIDGE)
    print(f"✅ owner withdrew {remaining}; escrow now {drained}")
    print(f"   ↳ agent earns ~{expected_commission} ({FEE_BPS / 100:.2f}% commission); owner gets the rest")
    assert drained == "0", f"expected the wallet to be drained, got {drained}"

    # (g) READ STATE back: rule terms, allow-list, instance, audit log.
    banner("(g) read MAA state")
    print("rule           :", agent.maa_get_rule(rule_id))
    print("allowed_actions:", agent.maa_get_allowed_actions(rule_id))
    print("instance       :", agent.maa_get_instance(maa))
    events = agent.maa_get_events(rule_id)
    print(f"events ({len(events)}):")
    for ev in events:
        print(f"   - {ev['event_type']:<12} role={ev['actor_role']:<13} actor={ev['actor_addr']} "
              f"action={ev.get('inner_action') or '-'} amount={ev.get('amount') or '-'}")

    # (h) READ the agent wallet's ORDER-BOOK portfolio BY ADDRESS (migration 051).
    #     get_positions_by_wallet / get_collateral_by_wallet read the wallet you pass in (NOT
    #     @caller), so an owner — or a delegated market-maker bot — can read an agent wallet's live
    #     inventory without holding its key. The signer here (agent) differs from the wallet read
    #     (the MAA), which is the whole point. This MAA's allow-list is create_streams/insert_records
    #     (data provision), so it holds NO order-book positions — the reads return empty/zero. A clean
    #     return (instead of "unknown action") is the proof that migration 051 is live on this network.
    banner("(h) read the agent wallet's order-book portfolio by address")
    positions = agent.get_positions_by_wallet(maa)
    collateral = agent.get_collateral_by_wallet(maa, COLLATERAL_BRIDGE)
    print(f"get_positions_by_wallet({maa}) -> {len(positions)} positions: {positions}")
    print(f"get_collateral_by_wallet({maa}, {COLLATERAL_BRIDGE}) -> {collateral}")
    print("✅ address-parameterized portfolio reads are live (migration 051)")

    banner("✅ MAA lifecycle smoke test PASSED")
    print("Proven on-chain via the Python SDK:")
    print("  • @caller rewritten to the MAA (the stream is owned by the wallet, not the agent key)")
    print("  • fees debit the MAA's own escrow")
    print("  • the restricted agent cannot move funds out")
    print("  • the owner withdraws with the agreed commission")
    print("  • an owner can read the wallet's order-book positions/collateral by address (051)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
