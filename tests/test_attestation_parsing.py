"""
Unit tests for attestation payload parsing functionality.

These tests verify input validation and error handling for the new
parse_attestation_payload() and verify_attestation_signature() methods.
"""

import pytest
from trufnetwork_sdk_py.client import TNClient, ParsedAttestationPayload

# Test private key used for client initialization
TEST_PRIVATE_KEY = "0121234567890123456789012345678901234567890123456789012345178901"


class TestAttestationPayloadParsing:
    """Unit tests for attestation payload parsing"""

    def test_parse_payload_validates_input_type(self, client):
        """Should reject non-bytes input"""
        with pytest.raises(ValueError, match="Payload must be bytes"):
            client.parse_attestation_payload("not bytes")  # type: ignore

    def test_parse_payload_rejects_empty(self, client):
        """Should reject empty payload"""
        with pytest.raises(ValueError, match="Payload cannot be empty"):
            client.parse_attestation_payload(b"")

    def test_parse_payload_rejects_malformed(self, client):
        """Should reject malformed payload"""
        with pytest.raises(Exception, match="Failed to parse"):
            client.parse_attestation_payload(b"\x00\x01\x02")  # Too short

    def test_verify_signature_validates_input_type(self, client):
        """Should reject non-bytes input"""
        with pytest.raises(ValueError, match="Payload must be bytes"):
            client.verify_attestation_signature("not bytes")  # type: ignore

    def test_verify_signature_rejects_short_payload(self, client):
        """Should reject payload shorter than 66 bytes"""
        with pytest.raises(ValueError, match="Payload too short"):
            client.verify_attestation_signature(b"\x00" * 65)  # Exactly 65, need 66+

    def test_verify_signature_provides_clear_error_message(self, client):
        """Error message should specify minimum length requirement"""
        with pytest.raises(
            ValueError, match="expected at least 66.*minimum 1 byte data.*65 bytes signature"
        ):
            client.verify_attestation_signature(b"\x00" * 50)


class TestAttestationPayloadTypes:
    """Tests for type structure and validation"""

    def test_parsed_payload_type_structure(self):
        """ParsedAttestationPayload should have correct fields"""
        payload = ParsedAttestationPayload(
            version=1,
            algorithm=0,
            block_height=12345,
            data_provider="0x4710a8d8f0d845da110086812a32de6d90d7ff5c",
            stream_id="stai0000000000000000000000000000",
            action_id=1,
            arguments=["arg1", 123],
            result=[{"values": ["1234567890", "100.5"]}],
        )

        assert payload.version == 1
        assert payload.algorithm == 0
        assert payload.block_height == 12345
        assert payload.data_provider == "0x4710a8d8f0d845da110086812a32de6d90d7ff5c"
        assert payload.stream_id == "stai0000000000000000000000000000"
        assert payload.action_id == 1
        assert len(payload.arguments) == 2
        assert len(payload.result) == 1

    def test_parsed_payload_defaults_to_empty_lists(self):
        """ParsedAttestationPayload should default to empty lists for optional fields"""
        payload = ParsedAttestationPayload(
            version=1,
            algorithm=0,
            block_height=12345,
            data_provider="0x4710a8d8f0d845da110086812a32de6d90d7ff5c",
            stream_id="stai0000000000000000000000000000",
            action_id=1,
        )

        assert payload.arguments == []
        assert payload.result == []

    def test_parsed_payload_accepts_complex_result_structures(self):
        """ParsedAttestationPayload should accept complex result data"""
        payload = ParsedAttestationPayload(
            version=1,
            algorithm=0,
            block_height=12345,
            data_provider="0x4710a8d8f0d845da110086812a32de6d90d7ff5c",
            stream_id="stai0000000000000000000000000000",
            action_id=1,
            result=[
                {"values": ["1234567890", "100.5"]},
                {"values": ["1234567891", "101.2"]},
                {"values": ["1234567892", "102.0"]},
            ],
        )

        assert len(payload.result) == 3
        assert payload.result[0]["values"][0] == "1234567890"
        assert payload.result[2]["values"][1] == "102.0"


@pytest.fixture(scope="module")
def client(tn_node):
    """Create a TNClient instance for testing"""
    client = TNClient(tn_node, TEST_PRIVATE_KEY)
    return client
