# Index-Change Market Example

Creates a set of prediction markets that settle on **how far an index moved**, rather than on the
level it published.

## Why this action exists

A stream that publishes an index *level* — CPI at ~335, PCE at ~131 — cannot back an inflation-rate
market through the value actions. Those compare a level against a rate, and the two are not the same
number. `get_index_change` computes the rate but returns a series, and multi-row actions cannot be
attested.

`index_change_in_range` computes the same percentage and returns a single boolean, so a market can
be struck on the *rate* while reading a stream that only publishes *levels*.

## What the example does

1. Reads the stream's latest year-over-year change, so you can see the number such a market settles
   against. The observation point is read from the stream rather than hardcoded, so it stays honest
   as the stream advances. A published index is not a live price — CPI-style data lands monthly — so
   the latest reading is routinely weeks old, and the example prints which day it belongs to. Plain
   reads, cost nothing.
2. Builds three buckets and decodes them locally, without touching the network. This is where the
   encoding contract is easiest to see.
3. Creates the same three markets on testnet.

## Buckets, bounds and open tails

The three buckets share an observation time and an interval and differ only in where they are
struck, so exactly one of them can settle YES:

| Question | `min_change` | `max_change` |
|---|---|---|
| below 2% | `None` | `"2"` |
| between 2% and 3% | `"2"` | `"3"` |
| 3% or more | `"3"` | `None` |

Two things follow from that table.

**Bounds are half-open, `[min, max)`.** A change landing exactly on a boundary belongs to the bucket
*above* it. That is what lets a set tile the number line without two buckets settling YES at once.

**`None` strikes an open tail**, which is how the outer two buckets are always struck. Passing `None`
for both is rejected — it would be every outcome at once. An empty string is rejected too: `""` is
the sentinel the bindings read as an open tail, so it would be accepted as one rather than caught.

An open tail decodes back as an **empty string holding its slot**, not as a shorter list:

```text
below 2%             thresholds=['', '2.000000000000000000']
3% or more           thresholds=['3.000000000000000000', '']
```

Dropping the empty entry would slide the surviving bound into the other position and turn
"below 2%" into "2% and up". `bucket_bounds_from_market_data` reads both slots and returns `None`
for the open side.

## Prerequisites

- Python 3.12+
- `trufnetwork-sdk-py` installed (`pip install -e ".[dev]"` from the repository root)
- A node carrying **migration 055**, which is what defines `index_change_in_range`. The public
  testnet the example points at has it. **Mainnet does not yet** — repointing `TESTNET_URL` there
  today fails with an unknown action, and it will keep failing until the migration is applied.

Otherwise nothing: the example points at `https://gateway.testnet.truf.network` and ships with a
throwaway testnet wallet.

## Running it

```bash
python examples/index_change_market/main.py
```

To create the markets from your own wallet instead:

```bash
PRIVATE_KEY=your_private_key_here python examples/index_change_market/main.py
```

## Cost

Each market costs a **2 TRUF creation fee**, so a run of this example costs 6 TRUF. The fee is
always taken from the wallet's `hoodi_tt` balance, whatever bridge the market uses for collateral —
this example collateralises in `hoodi_tt2`.

The bundled wallet is `0x32a46917DF74808b9aDD7DC6eF0c34520412FDF3`, the same OBMarketCreator wallet
the [order book examples](../order_book) use. It is a **throwaway testnet key**: do not use it in
production or hold anything of value in it. If it runs out of TRUF, pass your own `PRIVATE_KEY`.

## Expected output

```text
=== Index-change prediction markets ===
Endpoint: https://gateway.testnet.truf.network
Wallet:   0x32a46917df74808b9add7dc6ef0c34520412fdf3

--- What such a market measures ---
Stream st9f212b7c208afd83705cc0dbdadfe8 moved -33.659022158930734676% over the year ending 2026-07-06,
which is its latest reading, not today's date.

--- The bucket set, built and decoded locally ---
  below 2%             type=change_between thresholds=['', '2.000000000000000000'] bounds=[open, 2)
  between 2% and 3%    type=change_between thresholds=['2.000000000000000000', '3.000000000000000000'] bounds=[2, 3)
  3% or more           type=change_between thresholds=['3.000000000000000000', ''] bounds=[3, open)

--- Creating the set on testnet (2 TRUF each) ---
  below 2%             tx 4965b4e7400fa0ae486f86eacb16a10b4d9d3b4b6177472b7ae56062a4889e3c
  between 2% and 3%    tx 872d3c415fe48c8194da6dba0fb036eaa98dc4354b2cb266b0d8f11654f4464b
  3% or more           tx 59cd412522616e4f1608cfd1ccec52e9f82dd341fa0dc85430b3e902ee359246

Settles at 2026-08-26 13:13:41 UTC.
```

## Notes

- Each run uses a fresh settlement time. A market's identity is a hash of its query components, so
  re-creating an identical market is refused rather than duplicated.
- The market observes the stream at its settlement time, so it cannot be resolved before then.
- `$use_cache` is passed as `None` rather than `False` on purpose. `call_procedure` sends every
  argument as a string and the binding infers int, float or text from it, so there is no way to send
  a boolean; `None` becomes SQL NULL, which the action treats as "no cache".
- `index_change_in_range` cannot be called read-only: it goes through
  `validate_not_before_timestamp`, which needs a writer connection. Reading a truth value means
  requesting an attestation. Every binary attestation action behaves this way, not just this one.
- To read markets back off the network, see [`../decode_market_example`](../decode_market_example).
