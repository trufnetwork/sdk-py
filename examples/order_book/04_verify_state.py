"""
Order Book E2E Test - Step 4: Verify Final State

Queries postgres directly to show the final state of the order book.

Note: This script uses hardcoded credentials for local development only.
The database connection is for a tunneled PostgreSQL instance.
"""

import os
import subprocess


def get_query_id():
    """Read query_id from file created by 01_create_market.py."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    query_id_file = os.path.join(script_dir, ".query_id")
    try:
        with open(query_id_file, "r") as f:
            return int(f.read().strip())
    except FileNotFoundError:
        print(f"Warning: {query_id_file} not found. Run 01_create_market.py first.")
        raise SystemExit(1) from None


QUERY_ID = get_query_id()


def run_query(query: str, description: str):
    """Run a postgres query and print results."""
    print(f"\n--- {description} ---")
    cmd = [
        "psql",
        "-h", "localhost",
        "-p", "5433",
        "-U", "kwild",
        "-d", "kwild",
        "-c", query,
    ]
    env = {**os.environ, "PGPASSWORD": "kwild"}
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    print(result.stdout)
    if result.stderr:
        print(f"Error: {result.stderr}")
    if result.returncode != 0:
        print(f"Query failed with return code: {result.returncode}")


def main():
    print("=" * 70)
    print("Order Book E2E Test - Step 4: Verify Final State")
    print("=" * 70)

    print(f"Checking Market ID: {QUERY_ID}")

    # Market info
    run_query(f"""
        SELECT
            id as query_id,
            to_timestamp(settle_time) as settlement,
            settled,
            bridge
        FROM main.ob_queries
        WHERE id = {QUERY_ID};
    """, "Market Info")

    # Positions by participant
    run_query("""
        SELECT
            CASE
                WHEN encode(part.wallet_address, 'hex') = 'c11ff6d3cc60823ecdcab1089f1a4336053851ef' THEN 'MarketMaker'
                WHEN encode(part.wallet_address, 'hex') = '1c6790935a3a1a6b914399ba743bec8c41fe89fb' THEN 'BuyerTaker'
                WHEN encode(part.wallet_address, 'hex') = '51125fd33c366595d24aa42229085d30c95a62da' THEN 'SellerTaker'
                WHEN encode(part.wallet_address, 'hex') = '32a46917df74808b9add7dc6ef0c34520412fdf3' THEN 'MarketCreator'
                ELSE '0x' || encode(part.wallet_address, 'hex')
            END as participant,
            CASE WHEN p.outcome THEN 'YES' ELSE 'NO' END as outcome,
            p.price,
            p.amount,
            CASE
                WHEN p.price = 0 THEN 'HOLDING'
                WHEN p.price < 0 THEN 'BUY'
                ELSE 'SELL'
            END as order_type
        FROM main.ob_positions p
        JOIN main.ob_participants part ON p.participant_id = part.id
        ORDER BY participant, outcome DESC, price;
    """, "All Positions by Participant")

    # Order book view (buys and sells only, no holdings)
    run_query("""
        SELECT
            CASE WHEN p.outcome THEN 'YES' ELSE 'NO' END as side,
            CASE WHEN p.price < 0 THEN 'BUY' ELSE 'SELL' END as order_type,
            ABS(p.price) as price_cents,
            SUM(p.amount) as total_shares
        FROM main.ob_positions p
        WHERE p.price != 0
        GROUP BY p.outcome, CASE WHEN p.price < 0 THEN 'BUY' ELSE 'SELL' END, ABS(p.price)
        ORDER BY side DESC, order_type, price_cents;
    """, "Aggregated Order Book")

    # Summary of holdings
    run_query("""
        SELECT
            CASE
                WHEN encode(part.wallet_address, 'hex') = 'c11ff6d3cc60823ecdcab1089f1a4336053851ef' THEN 'MarketMaker'
                WHEN encode(part.wallet_address, 'hex') = '1c6790935a3a1a6b914399ba743bec8c41fe89fb' THEN 'BuyerTaker'
                WHEN encode(part.wallet_address, 'hex') = '51125fd33c366595d24aa42229085d30c95a62da' THEN 'SellerTaker'
                WHEN encode(part.wallet_address, 'hex') = '32a46917df74808b9add7dc6ef0c34520412fdf3' THEN 'MarketCreator'
                ELSE '0x' || encode(part.wallet_address, 'hex')
            END as participant,
            SUM(CASE WHEN p.outcome AND p.price = 0 THEN p.amount ELSE 0 END) as yes_holdings,
            SUM(CASE WHEN NOT p.outcome AND p.price = 0 THEN p.amount ELSE 0 END) as no_holdings
        FROM main.ob_positions p
        JOIN main.ob_participants part ON p.participant_id = part.id
        WHERE p.price = 0
        GROUP BY part.wallet_address
        ORDER BY participant;
    """, "Holdings Summary")

    print("\n" + "=" * 70)
    print("Test Complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
