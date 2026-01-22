"""
Unit tests for Order Book functionality.

These tests verify SDK-PY order book input validation and error handling.
They focus on client-side validation without requiring node infrastructure.

COMPLEX SCENARIOS (tested at node level only):
- Matching engine logic: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/matching_engine_test.go
- Settlement with attestations: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/settlement_test.go
- Fee distribution: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/fee_distribution_test.go
- LP rewards: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/rewards_test.go

Full node test reference: https://github.com/trufnetwork/node/tree/main/tests/streams/order_book
"""

import pytest
import hashlib
import time
from trufnetwork_sdk_py.client import TNClient

# Test configuration
TEST_PRIVATE_KEY = "0121234567890123456789012345678901234567890123456789012345178901"


@pytest.fixture(scope="module")
def client(tn_node, grant_network_writer):
    """
    Pytest fixture to create a TNClient instance for testing.
    Uses the tn_node fixture to get a running server.
    """
    client = TNClient(tn_node, TEST_PRIVATE_KEY)
    grant_network_writer(client)
    return client


# ═══════════════════════════════════════════════════════════════
# MARKET OPERATIONS TESTS
# ═══════════════════════════════════════════════════════════════
#
# MARKET CREATION & QUERY OPERATIONS:
# These operations require the ethereum_bridge namespace for funding to create
# and interact with markets.
#
# Operations tested at node level:
#   - CreateMarket: Creates a new prediction market
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/market_creation_test.go#L47
#
#   - GetMarketInfo: Retrieves market details by ID
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/market_creation_test.go#L99
#
#   - GetMarketByHash: Retrieves market details by query hash
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/market_creation_test.go#L131
#
#   - ListMarkets: Returns paginated list of markets with optional filtering
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/market_creation_test.go#L171
#
#   - MarketExists: Checks if market exists by hash (lightweight)
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/market_creation_test.go#L229
#
#   - ValidateMarketCollateral: Checks binary token parity and vault balance
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/validate_market_collateral_test.go
#
# SDK-PY VALIDATION TESTS (below) verify input validation without requiring node infrastructure.
# ═══════════════════════════════════════════════════════════════


class TestMarketOperationsValidation:
    """Test input validation for market operations"""

    # ==========================================
    #     create_market() validation
    # ==========================================

    def test_create_market_invalid_hash_length_short(self, client):
        """Test that query_hash must be exactly 32 bytes"""
        with pytest.raises(ValueError, match="query_hash must be exactly 32 bytes"):
            client.create_market(
                query_hash=b"short",  # Too short
                settle_time=int(time.time()) + 3600,
                max_spread=5,
                min_order_size=100,
            )

    def test_create_market_invalid_hash_length_long(self, client):
        """Test that query_hash must be exactly 32 bytes"""
        with pytest.raises(ValueError, match="query_hash must be exactly 32 bytes"):
            client.create_market(
                query_hash=b"x" * 64,  # Too long
                settle_time=int(time.time()) + 3600,
                max_spread=5,
                min_order_size=100,
            )

    def test_create_market_invalid_max_spread_too_low(self, client):
        """Test that max_spread must be at least 1"""
        with pytest.raises(ValueError, match="max_spread must be between 1 and 50"):
            client.create_market(
                query_hash=hashlib.sha256(b"test").digest(),
                settle_time=int(time.time()) + 3600,
                max_spread=0,  # Too low
                min_order_size=100,
            )

    def test_create_market_invalid_max_spread_too_high(self, client):
        """Test that max_spread must be at most 50"""
        with pytest.raises(ValueError, match="max_spread must be between 1 and 50"):
            client.create_market(
                query_hash=hashlib.sha256(b"test").digest(),
                settle_time=int(time.time()) + 3600,
                max_spread=51,  # Too high
                min_order_size=100,
            )

    def test_create_market_invalid_min_order_size(self, client):
        """Test that min_order_size must be positive"""
        with pytest.raises(ValueError, match="min_order_size must be positive"):
            client.create_market(
                query_hash=hashlib.sha256(b"test").digest(),
                settle_time=int(time.time()) + 3600,
                max_spread=5,
                min_order_size=0,  # Zero
            )

    def test_create_market_invalid_min_order_size_negative(self, client):
        """Test that min_order_size must be positive"""
        with pytest.raises(ValueError, match="min_order_size must be positive"):
            client.create_market(
                query_hash=hashlib.sha256(b"test").digest(),
                settle_time=int(time.time()) + 3600,
                max_spread=5,
                min_order_size=-100,  # Negative
            )

    # ==========================================
    #     get_market_by_hash() validation
    # ==========================================

    def test_get_market_by_hash_invalid_length(self, client):
        """Test that query_hash must be exactly 32 bytes"""
        with pytest.raises(ValueError, match="query_hash must be exactly 32 bytes"):
            client.get_market_by_hash(b"short")

    # ==========================================
    #     market_exists() validation
    # ==========================================

    def test_market_exists_invalid_hash_length(self, client):
        """Test that query_hash must be exactly 32 bytes"""
        with pytest.raises(ValueError, match="query_hash must be exactly 32 bytes"):
            client.market_exists(b"invalid")


# ═══════════════════════════════════════════════════════════════
# ORDER OPERATIONS TESTS
# ═══════════════════════════════════════════════════════════════
#
# ORDER PLACEMENT & MODIFICATION OPERATIONS:
# These operations require the ethereum_bridge namespace for funding test wallets,
# which is only available in the full node test infrastructure.
#
# Operations tested at node level:
#   - PlaceBuyOrder: Place buy orders for YES or NO shares
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/buy_order_test.go
#
#   - PlaceSellOrder: Sell shares you own
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/sell_order_test.go
#
#   - PlaceSplitLimitOrder: Mint binary pairs and list unwanted side for sale
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/split_limit_order_test.go
#
#   - CancelOrder: Cancel open buy or sell orders
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/cancel_order_test.go
#
#   - ChangeBid: Atomically modify buy order price and amount
#   - ChangeAsk: Atomically modify sell order price and amount
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/change_order_test.go
#
# SDK-PY VALIDATION TESTS (below) verify input validation without requiring node infrastructure.
# ═══════════════════════════════════════════════════════════════


class TestOrderOperationsValidation:
    """Test input validation for order operations"""

    # ==========================================
    #     place_buy_order() validation
    # ==========================================

    def test_place_buy_order_invalid_price_too_low(self, client):
        """Test that price must be at least 1 cent"""
        with pytest.raises(ValueError, match="price must be between 1 and 99 cents"):
            client.place_buy_order(
                query_id=1,
                outcome=True,
                price=0,  # Too low
                amount=100,
            )

    def test_place_buy_order_invalid_price_too_high(self, client):
        """Test that price must be at most 99 cents"""
        with pytest.raises(ValueError, match="price must be between 1 and 99 cents"):
            client.place_buy_order(
                query_id=1,
                outcome=True,
                price=100,  # Too high
                amount=100,
            )

    def test_place_buy_order_invalid_amount_zero(self, client):
        """Test that amount must be positive"""
        with pytest.raises(ValueError, match="amount must be positive"):
            client.place_buy_order(
                query_id=1,
                outcome=True,
                price=56,
                amount=0,  # Zero
            )

    def test_place_buy_order_invalid_amount_negative(self, client):
        """Test that amount must be positive"""
        with pytest.raises(ValueError, match="amount must be positive"):
            client.place_buy_order(
                query_id=1,
                outcome=True,
                price=56,
                amount=-100,  # Negative
            )

    # ==========================================
    #     place_sell_order() validation
    # ==========================================

    def test_place_sell_order_invalid_price_too_low(self, client):
        """Test that price must be at least 1 cent"""
        with pytest.raises(ValueError, match="price must be between 1 and 99 cents"):
            client.place_sell_order(
                query_id=1,
                outcome=True,
                price=0,  # Too low
                amount=100,
            )

    def test_place_sell_order_invalid_price_too_high(self, client):
        """Test that price must be at most 99 cents"""
        with pytest.raises(ValueError, match="price must be between 1 and 99 cents"):
            client.place_sell_order(
                query_id=1,
                outcome=True,
                price=100,  # Too high
                amount=100,
            )

    def test_place_sell_order_invalid_amount(self, client):
        """Test that amount must be positive"""
        with pytest.raises(ValueError, match="amount must be positive"):
            client.place_sell_order(
                query_id=1,
                outcome=True,
                price=56,
                amount=0,  # Zero
            )

    # ==========================================
    #     place_split_limit_order() validation
    # ==========================================

    def test_place_split_limit_order_invalid_price_too_low(self, client):
        """Test that true_price must be at least 1 cent"""
        with pytest.raises(ValueError, match="true_price must be between 1 and 99 cents"):
            client.place_split_limit_order(
                query_id=1,
                true_price=0,  # Too low
                amount=100,
            )

    def test_place_split_limit_order_invalid_price_too_high(self, client):
        """Test that true_price must be at most 99 cents"""
        with pytest.raises(ValueError, match="true_price must be between 1 and 99 cents"):
            client.place_split_limit_order(
                query_id=1,
                true_price=100,  # Too high
                amount=100,
            )

    def test_place_split_limit_order_invalid_amount(self, client):
        """Test that amount must be positive"""
        with pytest.raises(ValueError, match="amount must be positive"):
            client.place_split_limit_order(
                query_id=1,
                true_price=56,
                amount=0,  # Zero
            )

    # ==========================================
    #     cancel_order() validation
    # ==========================================

    def test_cancel_order_cannot_cancel_holdings(self, client):
        """Test that holdings (price=0) cannot be cancelled"""
        with pytest.raises(
            ValueError, match=r"Cannot cancel holdings.*use place_sell_order instead"
        ):
            client.cancel_order(
                query_id=1,
                outcome=True,
                price=0,  # Holdings
            )

    def test_cancel_order_invalid_price_too_low(self, client):
        """Test that price must be >= -99"""
        with pytest.raises(ValueError, match="price must be between -99 and 99"):
            client.cancel_order(
                query_id=1,
                outcome=True,
                price=-100,  # Too low
            )

    def test_cancel_order_invalid_price_too_high(self, client):
        """Test that price must be <= 99"""
        with pytest.raises(ValueError, match="price must be between -99 and 99"):
            client.cancel_order(
                query_id=1,
                outcome=True,
                price=100,  # Too high
            )

    # ==========================================
    #     change_bid() validation
    # ==========================================

    def test_change_bid_old_price_not_negative(self, client):
        """Test that old_price must be negative (buy orders)"""
        with pytest.raises(ValueError, match="bid prices must be negative"):
            client.change_bid(
                query_id=1,
                outcome=True,
                old_price=50,  # Positive (should be negative)
                new_price=-55,
                new_amount=100,
            )

    def test_change_bid_new_price_not_negative(self, client):
        """Test that new_price must be negative (buy orders)"""
        with pytest.raises(ValueError, match="bid prices must be negative"):
            client.change_bid(
                query_id=1,
                outcome=True,
                old_price=-50,
                new_price=55,  # Positive (should be negative)
                new_amount=100,
            )

    def test_change_bid_invalid_amount(self, client):
        """Test that new_amount must be positive"""
        with pytest.raises(ValueError, match="new_amount must be positive"):
            client.change_bid(
                query_id=1,
                outcome=True,
                old_price=-50,
                new_price=-55,
                new_amount=0,  # Zero
            )

    # ==========================================
    #     change_ask() validation
    # ==========================================

    def test_change_ask_old_price_not_positive(self, client):
        """Test that old_price must be positive (sell orders)"""
        with pytest.raises(ValueError, match="ask prices must be positive"):
            client.change_ask(
                query_id=1,
                outcome=True,
                old_price=-50,  # Negative (should be positive)
                new_price=55,
                new_amount=100,
            )

    def test_change_ask_new_price_not_positive(self, client):
        """Test that new_price must be positive (sell orders)"""
        with pytest.raises(ValueError, match="ask prices must be positive"):
            client.change_ask(
                query_id=1,
                outcome=True,
                old_price=50,
                new_price=-55,  # Negative (should be positive)
                new_amount=100,
            )

    def test_change_ask_invalid_amount(self, client):
        """Test that new_amount must be positive"""
        with pytest.raises(ValueError, match="new_amount must be positive"):
            client.change_ask(
                query_id=1,
                outcome=True,
                old_price=50,
                new_price=55,
                new_amount=0,  # Zero
            )


# ═══════════════════════════════════════════════════════════════
# QUERY OPERATIONS TESTS
# ═══════════════════════════════════════════════════════════════
#
# QUERY OPERATIONS:
# These are read-only operations that query market and position state.
#
# Operations tested at node level:
#   - GetOrderBook: Retrieves all buy/sell orders for a market outcome
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/order_book_queries_test.go#L47
#
#   - GetUserPositions: Retrieves caller's portfolio across all markets
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/order_book_queries_test.go#L124
#
#   - GetMarketDepth: Returns aggregated volume per price level
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/order_book_queries_test.go#L201
#
#   - GetBestPrices: Returns current bid/ask spread
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/order_book_queries_test.go#L256
#
#   - GetUserCollateral: Returns caller's total locked collateral value
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/order_book_queries_test.go#L311
#
# SDK-PY VALIDATION TESTS (below):
# Query operations have minimal client-side validation (just parameter types),
# so most testing happens at the node level.
# ═══════════════════════════════════════════════════════════════


class TestQueryOperationsValidation:
    """Test input validation for query operations"""

    # Query operations have minimal validation since they're read-only
    # Most validation happens at the node level

    def test_query_operations_exist(self, client):
        """Verify all query methods are available"""
        assert hasattr(client, "get_order_book")
        assert hasattr(client, "get_user_positions")
        assert hasattr(client, "get_market_depth")
        assert hasattr(client, "get_best_prices")
        assert hasattr(client, "get_user_collateral")


# ═══════════════════════════════════════════════════════════════
# SETTLEMENT & REWARDS TESTS
# ═══════════════════════════════════════════════════════════════
#
# SETTLEMENT & REWARDS OPERATIONS:
# These operations handle market settlement and LP reward distribution.
#
# Operations tested at node level:
#   - SettleMarket: Settles a market using attestation results
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/settlement_test.go
#
#   - SampleLPRewards: Samples liquidity provider rewards for a block
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/rewards_test.go#L47
#
#   - GetDistributionSummary: Retrieves fee distribution summary for a market
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/rewards_test.go#L124
#
#   - GetDistributionDetails: Retrieves per-LP reward details
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/rewards_test.go#L178
#
#   - GetParticipantRewardHistory: Retrieves reward history for a wallet
#     Reference: https://github.com/trufnetwork/node/blob/main/tests/streams/order_book/rewards_test.go#L235
#
# SDK-PY VALIDATION TESTS (below):
# Settlement operations have minimal client-side validation,
# so most testing happens at the node level.
# ═══════════════════════════════════════════════════════════════


class TestSettlementOperationsValidation:
    """Test input validation for settlement and rewards operations"""

    def test_settlement_operations_exist(self, client):
        """Verify all settlement methods are available"""
        assert hasattr(client, "settle_market")
        assert hasattr(client, "sample_lp_rewards")
        assert hasattr(client, "get_distribution_summary")
        assert hasattr(client, "get_distribution_details")
        assert hasattr(client, "get_participant_reward_history")


# ═══════════════════════════════════════════════════════════════
# TYPE DEFINITIONS TEST
# ═══════════════════════════════════════════════════════════════


class TestTypeDefinitions:
    """Test that all type definitions are available"""

    def test_order_book_types_exist(self):
        """Verify all OrderBook TypedDict definitions are available"""
        from trufnetwork_sdk_py.client import (
            MarketInfo,
            MarketSummary,
            MarketValidation,
            OrderBookEntry,
            UserPosition,
            DepthLevel,
            BestPrices,
            UserCollateral,
            DistributionSummary,
            LPRewardDetail,
            RewardHistory,
        )

        # If imports succeed, types are defined
        assert MarketInfo is not None
        assert MarketSummary is not None
        assert MarketValidation is not None
        assert OrderBookEntry is not None
        assert UserPosition is not None
        assert DepthLevel is not None
        assert BestPrices is not None
        assert UserCollateral is not None
        assert DistributionSummary is not None
        assert LPRewardDetail is not None
        assert RewardHistory is not None
