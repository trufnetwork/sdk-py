"""
Unit tests for attestation functionality.

These tests focus on input validation and error handling.
"""

import pytest
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


class TestAttestationInputValidation:
    """Test input validation for attestation methods"""

    # ==========================================
    #     request_attestation() validation
    # ==========================================

    def test_request_attestation_invalid_data_provider_length(self, client):
        """Test that data_provider must be exactly 42 characters"""
        with pytest.raises(ValueError, match="data_provider must be 42 characters"):
            client.request_attestation(
                data_provider="0x1234",  # Too short
                stream_id="st" + "0" * 30,
                action_name="get_record",
                args=[],
                wait=False,
            )

    def test_request_attestation_missing_0x_prefix(self, client):
        """Test that data_provider must start with 0x"""
        # Length check happens first, so use correct length without 0x
        with pytest.raises(ValueError, match="data_provider must start with '0x'"):
            client.request_attestation(
                data_provider="47" + "1" * 40,  # 42 chars but missing 0x
                stream_id="st" + "0" * 30,
                action_name="get_record",
                args=[],
                wait=False,
            )

    def test_request_attestation_invalid_stream_id_length(self, client):
        """Test that stream_id must be exactly 32 characters"""
        with pytest.raises(ValueError, match="stream_id must be 32 characters"):
            client.request_attestation(
                data_provider="0x" + "1" * 40,
                stream_id="st123",  # Too short
                action_name="get_record",
                args=[],
                wait=False,
            )

    def test_request_attestation_empty_action_name(self, client):
        """Test that action_name cannot be empty"""
        with pytest.raises(ValueError, match="action_name cannot be empty"):
            client.request_attestation(
                data_provider="0x" + "1" * 40,
                stream_id="st" + "0" * 30,
                action_name="",  # Empty
                args=[],
                wait=False,
            )

    def test_request_attestation_encryption_not_supported(self, client):
        """Test that signature encryption is not supported in MVP"""
        with pytest.raises(
            ValueError, match="Signature encryption is not supported in MVP"
        ):
            client.request_attestation(
                data_provider="0x" + "1" * 40,
                stream_id="st" + "0" * 30,
                action_name="get_record",
                args=[],
                encrypt_sig=True,  # Not supported
                wait=False,
            )

    def test_request_attestation_negative_max_fee(self, client):
        """Test that max_fee must be a valid numeric string"""
        with pytest.raises(ValueError, match="max_fee must be a numeric string"):
            client.request_attestation(
                data_provider="0x" + "1" * 40,
                stream_id="st" + "0" * 30,
                action_name="get_record",
                args=[],
                max_fee="-100",  # Invalid: contains non-digit characters
                wait=False,
            )

    # ==========================================
    #   get_signed_attestation() validation
    # ==========================================

    def test_get_signed_attestation_empty_request_tx_id(self, client):
        """Test that request_tx_id cannot be empty"""
        with pytest.raises(ValueError, match="request_tx_id cannot be empty"):
            client.get_signed_attestation("")

    # ==========================================
    #     list_attestations() validation
    # ==========================================

    def test_list_attestations_requester_too_long(self, client):
        """Test that requester must be at most 20 bytes"""
        with pytest.raises(ValueError, match="requester must be at most 20 bytes"):
            client.list_attestations(requester=b"x" * 21)

    def test_list_attestations_invalid_limit_zero(self, client):
        """Test that limit must be at least 1"""
        with pytest.raises(ValueError, match="limit must be between 1 and 5000"):
            client.list_attestations(limit=0)

    def test_list_attestations_invalid_limit_too_high(self, client):
        """Test that limit cannot exceed 5000"""
        with pytest.raises(ValueError, match="limit must be between 1 and 5000"):
            client.list_attestations(limit=5001)

    def test_list_attestations_negative_offset(self, client):
        """Test that offset must be non-negative"""
        with pytest.raises(ValueError, match="offset must be non-negative"):
            client.list_attestations(offset=-1)

    def test_list_attestations_invalid_order_by(self, client):
        """Test that order_by must be from allowed list"""
        with pytest.raises(ValueError, match="order_by must be one of"):
            client.list_attestations(order_by="invalid_column asc")

    def test_list_attestations_valid_order_by_values(self, client):
        """Test that all valid order_by values are accepted (case-insensitive)"""
        # These should not raise exceptions (they'll fail later trying to connect)
        valid_values = [
            "created_height asc",
            "created_height desc",
            "signed_height asc",
            "signed_height desc",
            "CREATED_HEIGHT ASC",  # Case insensitive
            "Signed_Height Desc",  # Mixed case
        ]

        for order_by in valid_values:
            # We expect this to fail with connection error, not validation error
            try:
                client.list_attestations(order_by=order_by, limit=1)
            except ValueError as e:
                # Should not be a validation error about order_by
                assert "order_by must be one of" not in str(e)
            except Exception:
                # Connection or other errors are fine - we just want to pass validation
                pass


class TestAttestationTypeConversions:
    """Test type handling and conversions"""

    def test_list_attestations_requester_none(self, client):
        """Test that requester=None is handled correctly"""
        # Should not raise validation error
        try:
            client.list_attestations(requester=None, limit=1)
        except ValueError as e:
            # Should not be a validation error about requester
            assert "requester" not in str(e).lower()
        except Exception:
            # Connection errors are fine
            pass

    def test_list_attestations_defaults(self, client):
        """Test that None defaults are handled correctly"""
        # Should not raise validation error
        try:
            client.list_attestations()
        except ValueError:
            pytest.fail("Should not raise ValueError with default arguments")
        except Exception:
            # Connection errors are fine
            pass

    def test_request_attestation_args_as_list(self, client):
        """Test that args parameter accepts a list"""
        args = ["value1", 123, True, None]

        # Should not raise validation error
        try:
            client.request_attestation(
                data_provider="0x" + "1" * 40,
                stream_id="st" + "0" * 30,
                action_name="get_record",
                args=args,
                wait=False,
            )
        except ValueError as e:
            # Should not be a validation error
            assert "data_provider" not in str(e)
            assert "stream_id" not in str(e)
            assert "action_name" not in str(e)
        except Exception:
            # Connection errors are fine
            pass


class TestAttestationEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_request_attestation_valid_min_values(self, client):
        """Test minimum valid values"""
        try:
            client.request_attestation(
                data_provider="0x" + "0" * 40,
                stream_id="st" + "0" * 30,
                action_name="a",  # Single character
                args=[],
                max_fee="0",  # Zero fee
                wait=False,
            )
        except ValueError as e:
            # Should not be validation errors
            if any(
                keyword in str(e)
                for keyword in ["data_provider", "stream_id", "action_name", "max_fee"]
            ):
                pytest.fail(f"Should accept minimum valid values: {e}")
        except Exception:
            # Connection errors are fine
            pass

    def test_list_attestations_valid_boundary_values(self, client):
        """Test boundary values for limit and offset"""
        try:
            # Minimum limit
            client.list_attestations(limit=1, offset=0)
        except ValueError as e:
            if "limit" in str(e) or "offset" in str(e):
                pytest.fail(f"Should accept minimum boundary values: {e}")
        except Exception:
            pass

        try:
            # Maximum limit
            client.list_attestations(limit=5000)
        except ValueError as e:
            if "limit" in str(e):
                pytest.fail(f"Should accept maximum limit: {e}")
        except Exception:
            pass

    def test_list_attestations_requester_exactly_20_bytes(self, client):
        """Test that requester with exactly 20 bytes is accepted"""
        try:
            client.list_attestations(requester=b"x" * 20)
        except ValueError as e:
            if "requester" in str(e):
                pytest.fail(f"Should accept exactly 20 bytes: {e}")
        except Exception:
            # Connection errors are fine
            pass

    def test_list_attestations_requester_less_than_20_bytes(self, client):
        """Test that requester with less than 20 bytes is accepted"""
        try:
            client.list_attestations(requester=b"x" * 10)
        except ValueError as e:
            if "requester" in str(e):
                pytest.fail(f"Should accept less than 20 bytes: {e}")
        except Exception:
            # Connection errors are fine
            pass
