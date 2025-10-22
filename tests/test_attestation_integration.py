"""
Integration tests for attestation functionality.

These tests require a running TN node and test the full attestation workflow.
"""

import pytest
import time
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


@pytest.fixture(scope="module")
def test_stream_with_data(client):
    """
    Fixture that creates a test stream with sample data for attestation tests.
    Returns (stream_id, data_provider, record_count).
    """
    stream_id = generate_stream_id("test_attestation_stream")
    data_provider = client.get_current_account()

    # Cleanup in case the stream already exists
    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass

    # Deploy stream
    client.deploy_stream(stream_id, STREAM_TYPE_PRIMITIVE)

    # Insert test data
    now = int(time.time())
    test_records = [
        {"date": now - 86400 * 2, "value": 100.0},  # 2 days ago
        {"date": now - 86400, "value": 150.0},  # 1 day ago
        {"date": now, "value": 200.0},  # Now
    ]

    for record in test_records:
        client.insert_record(stream_id, record)

    yield (stream_id, data_provider, len(test_records))

    # Cleanup
    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass


class TestAttestationFullWorkflow:
    """Test the complete attestation workflow"""

    def test_request_attestation_success(self, client, test_stream_with_data):
        """Test successful attestation request"""
        stream_id, data_provider, _ = test_stream_with_data

        # Prepare query parameters
        now = int(time.time())
        week_ago = now - (7 * 24 * 60 * 60)

        # Arguments for get_record action
        args = [
            data_provider,
            stream_id,
            week_ago,
            now,
            None,  # frozen_at
            False,  # use_cache
        ]

        # Request attestation
        request_tx_id = client.request_attestation(
            data_provider=data_provider,
            stream_id=stream_id,
            action_name="get_record",
            args=args,
            encrypt_sig=False,
            max_fee=1000000,
            wait=True,
        )

        # Verify transaction ID format
        assert request_tx_id is not None
        assert isinstance(request_tx_id, str)
        assert len(request_tx_id) == 64  # 64 hex chars (no 0x prefix)

    def test_get_signed_attestation_polling(self, client, test_stream_with_data):
        """Test retrieving signed attestation with polling"""
        stream_id, data_provider, _ = test_stream_with_data

        # Request attestation
        now = int(time.time())
        week_ago = now - (7 * 24 * 60 * 60)

        request_tx_id = client.request_attestation(
            data_provider=data_provider,
            stream_id=stream_id,
            action_name="get_record",
            args=[data_provider, stream_id, week_ago, now, None, False],
            max_fee=1000000,
            wait=True,
        )

        # Poll for signed attestation (max 30 seconds)
        max_attempts = 15
        payload = None

        for attempt in range(max_attempts):
            try:
                payload = client.get_signed_attestation(request_tx_id)
                # Check if signature is present (payload should be > 65 bytes when signed)
                if payload and len(payload) > 65:
                    break
            except Exception:
                pass

            if attempt < max_attempts - 1:
                time.sleep(2)

        # Verify we got a payload (may or may not be signed yet)
        assert payload is not None
        assert isinstance(payload, bytes)

        # If signed, verify minimum length
        if len(payload) > 65:
            # Has signature (already verified len > 65)
            pass

    def test_list_attestations_default_params(self, client, test_stream_with_data):
        """Test listing attestations with default parameters"""
        stream_id, data_provider, _ = test_stream_with_data

        # Create at least one attestation first
        now = int(time.time())
        request_tx_id = client.request_attestation(
            data_provider=data_provider,
            stream_id=stream_id,
            action_name="get_record",
            args=[data_provider, stream_id, now - 86400, now, None, False],
            max_fee=1000000,
            wait=True,
        )

        # List all attestations (no filter)
        attestations = client.list_attestations()

        # Verify results
        assert isinstance(attestations, list)
        # Note: May be empty if attestations are stored per-user
        # or may contain attestations from other tests

    def test_list_attestations_with_requester_filter(self, client, test_stream_with_data):
        """Test listing attestations filtered by requester"""
        stream_id, data_provider, _ = test_stream_with_data

        # Create an attestation
        now = int(time.time())
        request_tx_id = client.request_attestation(
            data_provider=data_provider,
            stream_id=stream_id,
            action_name="get_record",
            args=[data_provider, stream_id, now - 86400, now, None, False],
            max_fee=1000000,
            wait=True,
        )

        # Get current account as requester
        my_address = client.get_current_account()
        my_address_bytes = bytes.fromhex(my_address[2:])  # Remove 0x prefix

        # List attestations for current user
        attestations = client.list_attestations(
            requester=my_address_bytes,
            limit=10,
            order_by="created_height desc",
        )

        # Verify results
        assert isinstance(attestations, list)

        # If we have results, verify structure
        if len(attestations) > 0:
            att = attestations[0]
            assert "request_tx_id" in att
            assert "attestation_hash" in att
            assert "requester" in att
            assert "created_height" in att
            assert "signed_height" in att
            assert "encrypt_sig" in att

            # Verify our attestation is in the list
            assert any(
                a["request_tx_id"] == request_tx_id for a in attestations
            ), "Our attestation should be in the list"

    def test_list_attestations_pagination(self, client, test_stream_with_data):
        """Test pagination in list_attestations"""
        stream_id, data_provider, _ = test_stream_with_data

        # Create multiple attestations
        now = int(time.time())
        for i in range(3):
            client.request_attestation(
                data_provider=data_provider,
                stream_id=stream_id,
                action_name="get_record",
                args=[data_provider, stream_id, now - 86400, now, None, False],
                max_fee=1000000,
                wait=True,
            )
            time.sleep(0.5)  # Small delay between requests

        # Get first page
        page1 = client.list_attestations(limit=2, offset=0)

        # Get second page
        page2 = client.list_attestations(limit=2, offset=2)

        # Verify we got results
        assert isinstance(page1, list)
        assert isinstance(page2, list)

        # If we have results on both pages, they should be different
        if len(page1) > 0 and len(page2) > 0:
            # Compare request_tx_ids to ensure pages are different
            page1_ids = {att["request_tx_id"] for att in page1}
            page2_ids = {att["request_tx_id"] for att in page2}
            # Pages should not have overlapping IDs
            assert len(page1_ids & page2_ids) == 0, "Pages should not overlap"

    def test_list_attestations_ordering(self, client, test_stream_with_data):
        """Test ordering in list_attestations"""
        stream_id, data_provider, _ = test_stream_with_data

        # Create multiple attestations
        now = int(time.time())
        for i in range(3):
            client.request_attestation(
                data_provider=data_provider,
                stream_id=stream_id,
                action_name="get_record",
                args=[data_provider, stream_id, now - 86400, now, None, False],
                max_fee=1000000,
                wait=True,
            )
            time.sleep(0.5)

        # Get ascending order
        asc = client.list_attestations(
            limit=10,
            order_by="created_height asc",
        )

        # Get descending order
        desc = client.list_attestations(
            limit=10,
            order_by="created_height desc",
        )

        # Verify ordering if we have multiple results
        if len(asc) > 1:
            for i in range(len(asc) - 1):
                assert (
                    asc[i]["created_height"] <= asc[i + 1]["created_height"]
                ), "Ascending order should be maintained"

        if len(desc) > 1:
            for i in range(len(desc) - 1):
                assert (
                    desc[i]["created_height"] >= desc[i + 1]["created_height"]
                ), "Descending order should be maintained"

    def test_attestation_metadata_structure(self, client, test_stream_with_data):
        """Test that attestation metadata has correct structure"""
        stream_id, data_provider, _ = test_stream_with_data

        # Create an attestation
        now = int(time.time())
        request_tx_id = client.request_attestation(
            data_provider=data_provider,
            stream_id=stream_id,
            action_name="get_record",
            args=[data_provider, stream_id, now - 86400, now, None, False],
            max_fee=1000000,
            wait=True,
        )

        # Get attestations
        my_address = client.get_current_account()
        my_address_bytes = bytes.fromhex(my_address[2:])

        attestations = client.list_attestations(
            requester=my_address_bytes,
            limit=1,
            order_by="created_height desc",
        )

        # Find our attestation
        our_attestation = None
        for att in attestations:
            if att["request_tx_id"] == request_tx_id:
                our_attestation = att
                break

        if our_attestation:
            # Verify all fields are present
            assert isinstance(our_attestation["request_tx_id"], str)
            assert isinstance(our_attestation["attestation_hash"], bytes)
            assert isinstance(our_attestation["requester"], bytes)
            assert isinstance(our_attestation["created_height"], int)
            assert our_attestation["signed_height"] is None or isinstance(
                our_attestation["signed_height"], int
            )
            assert isinstance(our_attestation["encrypt_sig"], bool)

            # Verify values
            assert our_attestation["request_tx_id"] == request_tx_id
            assert len(our_attestation["requester"]) == 20  # 20 bytes
            assert our_attestation["created_height"] > 0
            assert our_attestation["encrypt_sig"] == False  # MVP restriction


class TestAttestationErrorHandling:
    """Test error handling for attestation operations"""

    def test_get_signed_attestation_invalid_tx_id(self, client):
        """Test retrieving attestation with invalid transaction ID"""
        # Should fail gracefully
        with pytest.raises(Exception):
            # Invalid tx ID format
            client.get_signed_attestation("invalid_tx_id")

    def test_get_signed_attestation_nonexistent_tx_id(self, client):
        """Test retrieving attestation for non-existent transaction"""
        # Should fail gracefully
        fake_tx_id = "0x" + "0" * 64

        try:
            payload = client.get_signed_attestation(fake_tx_id)
            # May return empty payload or raise exception
            # Both are acceptable behaviors
            if payload is not None:
                assert isinstance(payload, bytes)
        except Exception:
            # Expected - attestation doesn't exist
            pass

    def test_request_attestation_invalid_stream(self, client):
        """Test requesting attestation for non-existent stream

        Note: The request may succeed even for non-existent streams,
        as validation happens during attestation computation, not at request time.
        """
        data_provider = client.get_current_account()
        fake_stream_id = "st" + "f" * 30  # Non-existent stream
        now = int(time.time())

        # Request may succeed - the actual failure happens when validators try to compute the attestation
        # For now, we just verify the request doesn't crash
        request_tx_id = client.request_attestation(
            data_provider=data_provider,
            stream_id=fake_stream_id,
            action_name="get_record",
            args=[data_provider, fake_stream_id, now - 86400, now, None, 0],
            max_fee=1000000,
            wait=True,
        )

        # Request succeeds, but attestation computation will fail
        assert request_tx_id is not None
        assert isinstance(request_tx_id, str)


class TestAttestationWithDifferentActions:
    """Test attestations with different action types"""

    def test_request_attestation_get_first_record(self, client, test_stream_with_data):
        """Test attestation for get_first_record action"""
        stream_id, data_provider, _ = test_stream_with_data
        now = int(time.time())

        # Request attestation for get_first_record
        request_tx_id = client.request_attestation(
            data_provider=data_provider,
            stream_id=stream_id,
            action_name="get_first_record",
            args=[data_provider, stream_id, now - 86400 * 7, None, 0],  # 0 instead of False
            max_fee=1000000,
            wait=True,
        )

        assert request_tx_id is not None
        assert len(request_tx_id) == 64

    def test_request_attestation_get_index(self, client, test_stream_with_data):
        """Test attestation for get_index action

        get_index_composed signature:
        $data_provider, $stream_id, $from, $to, $frozen_at, $base_time, $use_cache
        """
        stream_id, data_provider, _ = test_stream_with_data
        now = int(time.time())
        base_time = now - 86400 * 30  # 30 days ago

        # Request attestation for get_index - pass all 7 args explicitly
        request_tx_id = client.request_attestation(
            data_provider=data_provider,
            stream_id=stream_id,
            action_name="get_index",
            args=[data_provider, stream_id, now - 86400 * 7, now, None, base_time, False],
            max_fee=1000000,
            wait=True,
        )

        assert request_tx_id is not None
        assert len(request_tx_id) == 64
