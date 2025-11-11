"""
Integration tests for transaction ledger query functionality.

These tests verify that transaction events are correctly queried from the ledger.
"""

import pytest
from trufnetwork_sdk_py.client import TNClient, STREAM_TYPE_PRIMITIVE
from trufnetwork_sdk_py.utils import generate_stream_id

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


@pytest.fixture
def deployed_stream(client):
    """
    Deploy a test stream and automatically clean it up after the test.

    Yields:
        tuple: (stream_id, tx_hash) of the deployed stream
    """
    stream_id = generate_stream_id(f"test_stream_{id(client)}")
    tx_hash = client.deploy_stream(stream_id, STREAM_TYPE_PRIMITIVE, wait=True)

    yield stream_id, tx_hash

    # Cleanup: Always destroy the stream, even if test fails
    try:
        client.destroy_stream(stream_id, wait=True)
    except Exception:
        # Ignore errors during cleanup (stream might already be destroyed)
        pass


class TestTransactionLedger:
    """Test transaction ledger query functionality"""

    def test_get_transaction_event_success(self, client, deployed_stream):
        """Test fetching transaction event for a deployStream transaction"""
        stream_id, tx_hash = deployed_stream

        # Fetch transaction event
        tx_event = client.get_transaction_event(tx_hash)

        # Validate response structure
        assert tx_event is not None
        assert "tx_id" in tx_event
        assert "method" in tx_event
        assert "caller" in tx_event
        assert "fee_amount" in tx_event
        assert "block_height" in tx_event
        assert "fee_distributions" in tx_event

        # Validate transaction details
        # Normalize tx hashes for comparison (remove 0x prefix for comparison)
        tx_id_normalized = tx_event["tx_id"].lower().replace("0x", "")
        tx_hash_normalized = tx_hash.lower().replace("0x", "")
        assert tx_id_normalized == tx_hash_normalized

        assert tx_event["method"] == "deployStream"

        # Caller should match current account
        current_account = client.get_current_account()
        assert tx_event["caller"].lower() == current_account.lower()

        assert tx_event["block_height"] > 0

        # Fee amount should be present (may be "0" if wallet is fee-exempt)
        assert tx_event["fee_amount"] is not None

        # Fee distributions should be a list
        assert isinstance(tx_event["fee_distributions"], list)

        print(f"✅ Successfully fetched transaction event:")
        print(f"   TX: {tx_event['tx_id']}")
        print(f"   Method: {tx_event['method']}")
        print(f"   Fee: {tx_event['fee_amount']} wei")
        print(f"   Block: {tx_event['block_height']}")

    def test_get_transaction_event_without_prefix(self, client, deployed_stream):
        """Test that transaction query works without 0x prefix"""
        stream_id, tx_hash = deployed_stream

        # Remove 0x prefix if present
        tx_hash_no_prefix = tx_hash.replace("0x", "") if tx_hash.startswith("0x") else tx_hash

        # Query without prefix
        tx_event = client.get_transaction_event(tx_hash_no_prefix)

        # Should succeed
        assert tx_event is not None
        assert tx_event["method"] == "deployStream"

        print(f"✅ Successfully queried without 0x prefix")

    def test_get_transaction_event_not_found(self, client):
        """Test error handling for non-existent transaction"""
        fake_tx_hash = "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"

        with pytest.raises(Exception) as exc_info:
            client.get_transaction_event(fake_tx_hash)

        # Error message should mention "not found"
        assert "not found" in str(exc_info.value).lower()

        print(f"✅ Correctly raised error for non-existent transaction")

    def test_get_transaction_event_empty_tx_id(self, client):
        """Test validation for empty tx_id"""
        with pytest.raises(ValueError) as exc_info:
            client.get_transaction_event("")

        assert "tx_id is required" in str(exc_info.value)

        print(f"✅ Correctly validated empty tx_id")

    def test_list_transaction_fees_paid_mode(self, client, deployed_stream):
        """Test listing fees paid by wallet"""
        stream_id, tx_hash = deployed_stream

        # Get current wallet
        wallet = client.get_current_account()

        # List fees paid by this wallet
        entries = client.list_transaction_fees(wallet, mode="paid", limit=20)

        # Should have at least one entry (the deployment we just made)
        assert len(entries) > 0

        # Find our deployment transaction
        found = False
        for entry in entries:
            # Normalize tx hashes for comparison
            entry_tx_normalized = entry["tx_id"].lower().replace("0x", "")
            tx_hash_normalized = tx_hash.lower().replace("0x", "")

            if entry_tx_normalized == tx_hash_normalized:
                found = True
                assert entry["method"] == "deployStream"
                assert entry["caller"].lower() == wallet.lower()
                assert entry["total_fee"] is not None
                assert entry["block_height"] > 0
                assert isinstance(entry["distribution_sequence"], int)

                print(f"✅ Found deployment transaction in fee list:")
                print(f"   TX: {entry['tx_id']}")
                print(f"   Fee: {entry['total_fee']} wei")
                break

        assert found, "Deployment transaction should be in paid fees list"

    def test_list_transaction_fees_both_mode(self, client):
        """Test listing fees with 'both' mode"""
        wallet = client.get_current_account()

        entries = client.list_transaction_fees(wallet, mode="both", limit=10)

        # Should succeed (may return empty list if no transactions)
        assert isinstance(entries, list)

        print(f"✅ Listed {len(entries)} fee entries in 'both' mode")

    def test_list_transaction_fees_pagination(self, client):
        """Test pagination parameters"""
        wallet = client.get_current_account()

        # Test with limit
        entries_limit_5 = client.list_transaction_fees(wallet, mode="both", limit=5)
        assert len(entries_limit_5) <= 5

        # Test with offset
        if len(entries_limit_5) > 2:
            entries_offset_2 = client.list_transaction_fees(
                wallet, mode="both", limit=5, offset=2
            )
            assert len(entries_offset_2) <= 5

            # First entry with offset should match third entry without offset
            if len(entries_offset_2) > 0 and len(entries_limit_5) > 2:
                assert entries_offset_2[0]["tx_id"] == entries_limit_5[2]["tx_id"]

        print(f"✅ Pagination works correctly")

    def test_list_transaction_fees_invalid_mode(self, client):
        """Test validation for invalid mode"""
        wallet = client.get_current_account()

        with pytest.raises(ValueError) as exc_info:
            client.list_transaction_fees(wallet, mode="invalid_mode")

        assert "mode must be one of" in str(exc_info.value)

        print(f"✅ Correctly validated invalid mode")

    def test_list_transaction_fees_invalid_limit(self, client):
        """Test validation for invalid limit"""
        wallet = client.get_current_account()

        with pytest.raises(ValueError) as exc_info:
            client.list_transaction_fees(wallet, mode="paid", limit=2000)

        assert "limit must be between 1 and 1000" in str(exc_info.value)

        print(f"✅ Correctly validated invalid limit")

    def test_list_transaction_fees_empty_wallet(self, client):
        """Test validation for empty wallet"""
        with pytest.raises(ValueError) as exc_info:
            client.list_transaction_fees("", mode="paid")

        assert "wallet is required" in str(exc_info.value)

        print(f"✅ Correctly validated empty wallet")

    def test_multiple_transactions(self, client):
        """Test fetching events for multiple transactions"""
        # Create multiple streams
        stream_ids = [
            generate_stream_id("test_multi_1"),
            generate_stream_id("test_multi_2"),
        ]

        tx_hashes = []
        try:
            for stream_id in stream_ids:
                tx_hash = client.deploy_stream(stream_id, STREAM_TYPE_PRIMITIVE, wait=True)
                tx_hashes.append(tx_hash)

            # Fetch all transaction events
            tx_events = []
            for tx_hash in tx_hashes:
                tx_event = client.get_transaction_event(tx_hash)
                tx_events.append(tx_event)
                assert tx_event["method"] == "deployStream"

            assert len(tx_events) == len(tx_hashes)

            print(f"✅ Successfully fetched {len(tx_events)} transaction events")

        finally:
            # Cleanup: Always destroy streams, even if test fails
            for stream_id in stream_ids:
                try:
                    client.destroy_stream(stream_id, wait=True)
                except Exception:
                    # Ignore errors during cleanup
                    pass
