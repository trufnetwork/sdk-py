import pytest
from trufnetwork_sdk_py.client import TNClient
from trufnetwork_sdk_py.utils import generate_stream_id
from tests.fixtures.test_trufnetwork import tn_node

# Test configuration
TEST_PRIVATE_KEY = (
    "0121234567890123456789012345678901234567890123456789012345178901"
)

@pytest.fixture(scope="module")
def client(tn_node, grant_network_writer):
    """
    Pytest fixture to create a TNClient instance for testing.
    Uses the tn_node fixture to get a running server.
    """
    client = TNClient(tn_node, TEST_PRIVATE_KEY)
    grant_network_writer(client)
    return client

def test_list_streams(client):
    """
    Test list all streams
    """
    stream1 = generate_stream_id("test_stream_1")
    stream2 = generate_stream_id("test_stream_2")
    stream3 = generate_stream_id("test_stream_3")

    # Cleanup in case the stream already exists from a previous test run
    try:
        client.destroy_stream(stream1)
        client.destroy_stream(stream2)
        client.destroy_stream(stream3)
    except Exception:
        pass

    client.deploy_stream(stream1)
    client.deploy_stream(stream2)
    client.deploy_stream(stream3)

    streams = client.list_streams()
    assert streams is not None
    assert len(streams) == 3

    client.destroy_stream(stream1)
    client.destroy_stream(stream2)
    client.destroy_stream(stream3)