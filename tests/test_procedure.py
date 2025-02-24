import pytest
from trufnetwork_sdk_py.client import TNClient
from trufnetwork_sdk_py.utils import generate_stream_id
import trufnetwork_sdk_c_bindings.exports as truf_sdk


@pytest.fixture(scope="module")
def client(tn_node: str):
    """
    Fixture to create a TNClient instance from the tn_node fixture.
    """
    # tn_node is provided by the test environment (see other tests)
    # Use a default private key to initialize the client.
    DEFAULT_TN_PRIVATE_KEY = "0121234567890123456789012345678901234567890123456789012345178901"
    return TNClient(tn_node, DEFAULT_TN_PRIVATE_KEY)

def test_get_type(client: TNClient):
    """
    Test that gets the type of the stream.
    """
    # deploy primitive stream
    stream_id = generate_stream_id("stream_for_proc")
    client.deploy_stream(stream_id, stream_type=truf_sdk.StreamTypePrimitive, wait=True)
    client.init_stream(stream_id=stream_id, wait=True)

    # deploy composed stream
    composed_stream_id = generate_stream_id("composed_stream_for_proc")
    client.deploy_stream(composed_stream_id, stream_type=truf_sdk.StreamTypeComposed, wait=True)
    client.init_stream(stream_id=composed_stream_id, wait=True)

    # deploy unitialized stream
    uninitialized_stream_id = generate_stream_id("uninitialized_stream_for_proc")
    client.deploy_stream(uninitialized_stream_id, stream_type=truf_sdk.StreamTypePrimitive, wait=True)

    stream_type = client.get_type(stream_id, client.get_current_account())
    assert stream_type == truf_sdk.StreamTypePrimitive, "Stream type should be primitive"

    stream_type = client.get_type(composed_stream_id, client.get_current_account())
    assert stream_type == truf_sdk.StreamTypeComposed, "Stream type should be composed"

    with pytest.raises(Exception, match="no type found"):
        client.get_type(uninitialized_stream_id, client.get_current_account())

@pytest.mark.skip(reason="Doesn't work correctly from the SDK")
def test_is_wallet_allowed_to_write(client: TNClient):
    """
    Test that calls the procedure "is_wallet_allowed_to_write" using the client's own wallet
    as an argument. It deploys a helper contract stream, calls the procedure, and asserts
    that the response indicates the wallet is allowed to write.
    """
    # Generate a stream id for the helper contract
    test_stream_id = generate_stream_id("stream_for_proc")
    try:
        # Deploy the helper contract stream using the helper stream type.
        client.deploy_stream(test_stream_id, stream_type=truf_sdk.StreamTypePrimitive, wait=True)        

        # initialize the stream
        client.init_stream(stream_id=test_stream_id, wait=True)

        # Get the client's own wallet address.
        own_wallet = client.get_current_account()
        assert own_wallet, "Wallet address should not be empty"

        # Call the procedure "is_wallet_allowed_to_write" passing the client's own wallet
        result = client.call_procedure(
            stream_id=test_stream_id,
            data_provider=own_wallet,
            procedure="is_wallet_allowed_to_write",
            args=[own_wallet]
        )
        # result is expected to be a list of dictionaries
        assert isinstance(result, list), "Expected procedure return type to be a list"
        assert len(result) > 0, "Procedure call should return at least one record"
        
        record = result[0]
        assert "allowed" in record, "Response record should contain key 'allowed'"
        allowed = record["allowed"]
        # Convert to boolean if necessary (could be a boolean or string)
        if isinstance(allowed, str):
            allowed_bool = allowed.lower() in ("true", "1")
        else:
            allowed_bool = bool(allowed)
        assert allowed_bool is True, "Wallet should be allowed to write"
    finally:
        # Clean up: destroy the helper contract stream after the test
        client.destroy_stream(test_stream_id) 