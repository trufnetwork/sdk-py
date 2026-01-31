# Order Book Examples

End-to-end examples for the TRUF.NETWORK prediction market order book system.

## Overview

These examples demonstrate how to create and interact with binary prediction markets on TRUF.NETWORK. Markets are settled automatically based on real-world data from trusted data providers.

## Prerequisites

- Python 3.8+
- TRUF.NETWORK SDK installed: `pip install trufnetwork-sdk-py`
- PostgreSQL client (for state verification): `psql`
- Access to TRUF.NETWORK testnet

## Example Scripts

### 1. Create Market (`01_create_market.py`)

Creates a new binary prediction market with the question: "Will Bitcoin be above $X at settlement time?"

```bash
python 01_create_market.py
```

**What it does:**
- Connects to the testnet with the market creator wallet
- Creates a market with a 30-minute settlement window
- Saves the `query_id` for use in subsequent steps

### 2. Place Orders (`02_place_orders.py`)

Market maker provides liquidity by placing orders on both sides of the market.

```bash
python 02_place_orders.py
```

**What it does:**
- Places split limit orders (creates YES holdings, sells NO shares)
- Places buy orders for YES at various price levels
- Establishes initial market liquidity

### 3. Take Orders (`03_take_orders.py`)

Takers execute trades against the market maker's orders.

```bash
python 03_take_orders.py
```

**What it does:**
- Buyer taker purchases YES shares
- Seller taker sells YES shares via split limit orders
- Demonstrates order matching mechanics

### 4. Verify State (`04_verify_state.py`)

Queries the database directly to show the final state of positions and the order book.

```bash
python 04_verify_state.py
```

**Requirements:** PostgreSQL tunnel to the node (default port 5433)

## Market Lifecycle

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Create Market  │────▶│  Place Orders   │────▶│  Take Orders    │
│  (01_create)    │     │  (02_place)     │     │  (03_take)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Payouts Sent   │◀────│  Auto-Settle    │◀────│  Wait for       │
│  to Winners     │     │  (Scheduler)    │     │  Settlement     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Settlement

Markets are settled **automatically** by the network scheduler:

1. **Scheduler polls** for markets past their settlement time (runs on cron schedule)
2. **Attestation requested** from the data provider's stream
3. **TEE signs** the attestation cryptographically
4. **Settlement executes** - determines winner based on attestation result
5. **Payouts distributed** - winners receive collateral, losers forfeit

No manual intervention is required for settlement.

## Key Concepts

### Price Representation

- Prices are in **cents** (1-99)
- A YES price of 60 means 60 cents, implying 60% probability
- The complementary NO price is always `100 - YES_price`

### Order Types

| Order Type | Price | Description |
|------------|-------|-------------|
| Buy Order | Negative (-1 to -99) | Bid to buy shares at this price |
| Holding | 0 | Shares owned by participant |
| Sell Order | Positive (1 to 99) | Ask to sell shares at this price |

### Split Limit Orders

A split limit order atomically:
1. Locks collateral
2. Mints a YES/NO share pair
3. Keeps YES shares as holdings
4. Places NO shares as a sell order

This is the primary way to provide liquidity.

## Collateral

- All markets use **hoodi_tt2** (testnet USDC) as collateral
- 1 share pair = 1 USDC collateral
- Winners receive 1 USDC per winning share
- Collateral from losing positions is distributed to winners

## Configuration

The examples use pre-funded testnet wallets:

| Role | Address |
|------|---------|
| Market Creator | `0x32a46917DF74808b9aDD7DC6eF0c34520412FDF3` |
| Market Maker | `0xc11Ff6d3cC60823EcDCAB1089F1A4336053851EF` |
| Buyer Taker | `0x1c6790935a3a1A6B914399Ba743BEC8C41Fe89Fb` |
| Seller Taker | `0x51125FD33c366595d24aa42229085D30c95a62dA` |

## Troubleshooting

### "Market not found"
Run `01_create_market.py` first to create a market and save the query_id.

### "Insufficient balance"
Ensure the wallet has sufficient hoodi_tt2 (USDC) balance on testnet.

### "Settlement time not reached"
Wait until the market's settlement time has passed before expecting settlement.

## Related Documentation

- [Order Book API Reference](../../docs/api-reference.md#order-book-operations)