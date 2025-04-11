from datetime import datetime, timezone
import pytest
from trufnetwork_sdk_py.client import TNClient
from trufnetwork_sdk_py.utils import generate_stream_id
import trufnetwork_sdk_c_bindings.exports as truf_sdk

# Test configuration
TEST_PROVIDER_URL = "http://localhost:8484"  
TEST_PRIVATE_KEY = (
    "0121234567890123456789012345678901234567890123456789012345178901"
)

@pytest.fixture(scope="module")
def client():
    """
    Pytest fixture to create a TNClient instance for testing.
    Uses the tn_node fixture to get a running server.
    """
    client = TNClient(TEST_PROVIDER_URL, TEST_PRIVATE_KEY)
    return client

def test_primitive_permissions(client):
    """
    Test primitive stream permissions
    """
    stream_id = generate_stream_id("test_primitive_permission")

    # Cleanup in case the stream already exists from a previous test run
    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass

    client.destroy_stream(stream_id)

def test_composed_permissions(client):
    """
    Test composed stream permissions
    """
    composed_stream_id = generate_stream_id("test_composed_permission")
    primitive_stream_id = generate_stream_id("test_primitive_permission")

    # Cleanup in case the stream already exists from a previous test run
    try:
        client.destroy_stream(composed_stream_id)
        client.destroy_stream(primitive_stream_id)
    except Exception:
        pass

    client.destroy_stream(composed_stream_id)
    client.destroy_stream(primitive_stream_id)

def test_stream_composition_permissions(client):
    """
    Test composed stream permissions
    """
    composed_stream_id = generate_stream_id("test_composed_permission")
    primitive_stream_id = generate_stream_id("test_primitive_permission")

    # Cleanup in case the stream already exists from a previous test run
    try:
        client.destroy_stream(composed_stream_id)
        client.destroy_stream(primitive_stream_id)
    except Exception:
        pass

    client.destroy_stream(composed_stream_id)
    client.destroy_stream(primitive_stream_id)