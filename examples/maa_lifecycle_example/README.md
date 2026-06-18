# MAA Lifecycle Smoke Test

A runnable, end-to-end proof of **Modular Agent Addresses** ("agent wallets") through the Python SDK,
against a live TRUF.NETWORK node where `maa_exec` is activated (testnet from height `6523123`).

An MAA lets a token holder (the **owner**) hand a constrained **agent** key a wallet it can *operate*
but provably cannot *drain*. This example drives the whole lifecycle and asserts the properties that
make that safe, mirroring the node's canonical oracle `tests/streams/maa/data_agent_test.go`.

## What it proves

1. **`@caller` rewrite** — the agent runs `create_streams` / `insert_records` *as the MAA*, so the
   stream it creates is owned by the **MAA address**, not the agent's own key. The example reads the
   record back under the MAA address to confirm.
2. **Fees debit the MAA's own escrow** — each action's fee comes out of the wallet's bridge balance
   (printed before/after every step).
3. **The agent cannot exfiltrate** — when the restricted agent attempts `maa_withdraw`, the node
   rejects it ("reserved for the unrestricted owner") and the escrow is unchanged.
4. **The owner withdraws with commission** — the owner drains the remaining escrow; the agent earns
   the rule's `fee_bps` commission.
5. **Local derivation matches the chain** — `rule_id` and the MAA address are derived offline
   (`compute_rules_hash` / `derive_rule_id` / `derive_maa_address_hex`) and asserted equal to what the
   node returns.

## Two identities (required)

The agent and the owner are **different keys**:

| Role | Env var | Signs | Becomes |
|------|---------|-------|---------|
| **Restricted agent** | `AGENT_PRIVATE_KEY` | `maa_create_rule`, runs allow-listed actions as the MAA | the `restricted` address baked into `rule_id` |
| **Unrestricted owner** | `OWNER_PRIVATE_KEY` | `join_agent_address`, funds, withdraws | the `unrestricted` address; controls the funds |

## Run

```bash
# from the repo root
uv venv .venv && source .venv/bin/activate && uv pip install -e ".[dev]"

cd examples/maa_lifecycle_example

export PROVIDER_URL="https://gateway.testnet.truf.network"   # the testnet RPC/gateway
export AGENT_PRIVATE_KEY=0x...        # restricted agent
export OWNER_PRIVATE_KEY=0x...        # unrestricted owner (must hold bridged TRUF)
export MAA_BRIDGE="hoodi_tt"          # token bridge namespace on this network
export MAA_FUND_AMOUNT="250000000000000000000"   # wei to fund the MAA with
# optional: export MAA_FEE_BPS=250    # owner-withdraw commission to the agent (2.5%)

python main.py
```

### Environment variables

| Variable | Default | Notes |
|----------|---------|-------|
| `PROVIDER_URL` | `https://gateway.testnet.truf.network` | The testnet RPC/gateway. **Confirm the real URL for your network.** |
| `AGENT_PRIVATE_KEY` | — (required) | Restricted agent key. |
| `OWNER_PRIVATE_KEY` | — (required) | Unrestricted owner key; must hold ≥ `MAA_FUND_AMOUNT` + fees of bridged token. |
| `MAA_BRIDGE` | `hoodi_tt` | Token bridge namespace. dev = `hoodi_tt`/`hoodi_tt2`, mainnet = `eth_truf`/`eth_usdc`. **Confirm which exists on testnet.** |
| `MAA_FUND_AMOUNT` | `250000000000000000000` (250 TRUF) | Must cover the action fees (`create_streams` may cost 100 TRUF where the fee is active). |
| `MAA_FEE_BPS` | `250` (2.5%) | Owner-withdraw commission paid to the agent. |

## Open items to confirm before the first run

These can't be derived from code — set them for your testnet:

1. **Provider URL** — the public testnet RPC/gateway endpoint.
2. **Two funded keys** — the owner key in particular needs enough bridged token to fund the MAA.
3. **Bridge namespace** — which of `hoodi_tt` / `eth_truf` / … is registered on this network.
4. **Fee schedule** — whether the 100-TRUF `create_streams` fee is active (drives `MAA_FUND_AMOUNT`).
   The script reads balances around each step, so it works whether or not fees are active.

## NUMERIC arguments (why `MAANumericArg`)

`execute_agent_action` serializes the inner action's arguments to JSON, and JSON has no decimal type.
The node does **not** coerce text to `NUMERIC` — it requires a `NUMERIC` parameter to receive a value
whose precision/scale match exactly. So token amounts (`maa_withdraw`'s `$amount NUMERIC(78,0)`) and
record values (`insert_records`' `$value NUMERIC(36,18)[]`) are wrapped in `MAANumericArg(value,
precision, scale)`; plain `str`/`int`/`bool` and nested integer arrays (`INT8[]`) pass through as-is.

```python
from trufnetwork_sdk_py import MAANumericArg

client.execute_agent_action(maa, "maa_withdraw", ["hoodi_tt", MAANumericArg("110000000000000000000", 78, 0)])
client.execute_agent_action(
    maa, "insert_records",
    [[provider], [stream_id], [event_time], [MAANumericArg("42.5", 36, 18)]],
)
```

## What success looks like

Each step prints a `✅`, balances move as expected, the agent's withdrawal is blocked, the owner's
succeeds, and the run ends with `✅ MAA lifecycle smoke test PASSED`. A non-zero exit or a missing `✅`
means a step failed — the raw node error is printed inline.

## Oracle

The Go equivalents (same semantics, exercised directly against the engine) live in the node repo:
`tests/streams/maa/data_agent_test.go`, `withdraw_test.go`, `lp_vault_test.go`, and
`docs/modular-agent-addresses.md`.
