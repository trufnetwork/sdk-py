import pytest
from trufnetwork_sdk_py import TNClient, STREAM_TYPE_PRIMITIVE, STREAM_TYPE_COMPOSED, StreamDefinitionInput, StreamLocatorInput, StreamExistsResult
from trufnetwork_sdk_py.utils import generate_stream_id as sdk_generate_stream_id
import uuid

# Define a standard private key for test client initialization
TEST_PRIVATE_KEY = "1111111111111111111111111111111111111111111111111111111111111111" # Example test key

# Helper to generate unique stream IDs for testing using the SDK's formatter
# This now generates a unique NAME, which is then passed to the SDK's ID generator.
def generate_unique_formatted_stream_id(prefix: str) -> str:
    unique_name = f"{prefix}-{uuid.uuid4().hex[:8]}"
    return sdk_generate_stream_id(unique_name) # Use the SDK utility

@pytest.fixture(scope="module")
def client(tn_node, grant_network_writer) -> TNClient:
    """Provides a TNClient instance configured for the test TSN node."""
    node_url = tn_node # tn_node fixture yields the URL string
    # Ensure your TNClient can be initialized with url and token (private_key)
    # The TNClient constructor is `__init__(self, url: str, token: str)`
    # where token is the private key.
    client = TNClient(url=node_url, token=TEST_PRIVATE_KEY)
    # enable this client to deploy streams
    grant_network_writer(client)
    return client

class TestBatchOperations:

    def test_batch_deploy_streams_success(self, client: TNClient):
        print("Starting test_batch_deploy_streams_success")
        dp_address = client.get_current_account()
        stream_id_1 = generate_unique_formatted_stream_id("batch-prim")
        stream_id_2 = generate_unique_formatted_stream_id("batch-comp")
        stream_id_3 = generate_unique_formatted_stream_id("batch-prim-2")

        definitions: List[StreamDefinitionInput] = [
            {"stream_id": stream_id_1, "stream_type": STREAM_TYPE_PRIMITIVE},
            {"stream_id": stream_id_2, "stream_type": STREAM_TYPE_COMPOSED},
            {"stream_id": stream_id_3, "stream_type": STREAM_TYPE_PRIMITIVE},
        ]

        # Deploy
        try:
            print(f"Deploying batch: {definitions}")
            tx_hash = client.batch_deploy_streams(definitions=definitions, wait=False)
            assert tx_hash, "batch_deploy_streams should return a transaction hash"
            print(f"Batch deploy tx_hash: {tx_hash}, waiting for confirmation...")
            client.wait_for_tx(tx_hash)
            print("Batch deploy transaction confirmed.")
        except Exception as e:
            pytest.fail(f"batch_deploy_streams failed during deployment: {e}")

        # Verify existence
        locators_to_check: List[StreamLocatorInput] = [
            {"stream_id": stream_id_1, "data_provider": dp_address},
            {"stream_id": stream_id_2, "data_provider": dp_address},
            {"stream_id": stream_id_3, "data_provider": dp_address},
        ]
        try:
            print(f"Checking existence for: {locators_to_check}")
            existence_results = client.batch_stream_exists(locators=locators_to_check)
            print(f"Existence results: {existence_results}")
            assert len(existence_results) == len(definitions)
            for result in existence_results:
                assert result["exists"] is True, f"Stream {result['stream_id']} should exist."

                # Check type as well
                original_def = next(d for d in definitions if d["stream_id"] == result["stream_id"])
                actual_type = client.get_type(stream_id=result["stream_id"], data_provider=dp_address)
                assert actual_type == original_def["stream_type"], \
                    f"Stream {result['stream_id']} type mismatch. Expected {original_def['stream_type']}, got {actual_type}"
        except Exception as e:
            pytest.fail(f"batch_stream_exists or get_type failed during verification: {e}")
        finally:
            # Cleanup
            print("Cleaning up deployed streams...")
            for definition in definitions:
                try:
                    print(f"Destroying stream: {definition['stream_id']}")
                    client.destroy_stream(stream_id=definition["stream_id"], wait=True)
                    print(f"Stream {definition['stream_id']} destroyed.")
                except Exception as e:
                    print(f"Error destroying stream {definition['stream_id']}: {e}")
        print("Finished test_batch_deploy_streams_success")

    def test_batch_deploy_streams_empty_input(self, client: TNClient):
        print("Starting test_batch_deploy_streams_empty_input")
        with pytest.raises(Exception) as exc_info: # Go side should error, Python might wrap it
            client.batch_deploy_streams(definitions=[], wait=True)
        # Check if the error message from Go is propagated (e.g., "no stream definitions provided")
        # This depends on how Go errors are surfaced through the bindings.
        # For now, just checking an exception is raised.
        # We need to ensure the error is not from Python itself due to [] being invalid before bindings.
        # The Go binding for BatchDeployStreams should handle empty []types.StreamDefinition gracefully or error as per its spec.
        assert exc_info is not None, "batch_deploy_streams with empty list should raise an exception"
        # e.g. assert "no stream definitions provided" in str(exc_info.value).lower()
        print(f"Caught expected exception: {exc_info.value}")
        print("Finished test_batch_deploy_streams_empty_input")

    def test_batch_deploy_streams_duplicate_in_batch(self, client: TNClient):
        print("Starting test_batch_deploy_streams_duplicate_in_batch")
        dp_address = client.get_current_account()
        # Generate the name first, then the ID. The ID itself (a hash) is what needs to be used.
        existing_stream_name = f"batch-dup-exist-{uuid.uuid4().hex[:4]}" # Unique name for the first stream
        existing_stream_id = sdk_generate_stream_id(existing_stream_name)
        
        new_stream_name = f"batch-dup-new-{uuid.uuid4().hex[:4]}" # Unique name for the second stream
        new_stream_id = sdk_generate_stream_id(new_stream_name)

        # Pre-deploy one stream
        try:
            print(f"Pre-deploying stream: {existing_stream_id}")
            client.deploy_stream(stream_id=existing_stream_id, stream_type=STREAM_TYPE_PRIMITIVE, wait=True)
            print(f"Stream {existing_stream_id} pre-deployed.")
        except Exception as e:
            pytest.fail(f"Failed to pre-deploy stream {existing_stream_id}: {e}")

        definitions: List[StreamDefinitionInput] = [
            {"stream_id": existing_stream_id, "stream_type": STREAM_TYPE_PRIMITIVE}, # Duplicate
            {"stream_id": new_stream_id, "stream_type": STREAM_TYPE_COMPOSED},
        ]

        # Attempt to deploy batch with duplicate
        # The Go SDK's BatchDeployStreams itself might not error on submission,
        # but the transaction should fail on-chain.
        tx_hash = None
        try:
            print(f"Attempting batch deploy with duplicate: {definitions}")
            tx_hash = client.batch_deploy_streams(definitions=definitions, wait=False)
            assert tx_hash, "batch_deploy_streams (with duplicate) should return a transaction hash"
            print(f"Batch deploy with duplicate tx_hash: {tx_hash}, expecting tx failure...")
            # Expect WaitForTx to raise an error or indicate tx failure
            with pytest.raises(Exception) as exc_info:
                client.wait_for_tx(tx_hash)
            assert exc_info is not None, "Transaction with duplicate stream should fail and raise in wait_for_tx"
            # Further check error message if possible, e.g., contains "transaction failed" or specific Kwil error
            print(f"Caught expected transaction failure: {exc_info.value}")

        except Exception as e:
            # This might catch errors from batch_deploy_streams if it fails client-side, 
            # but the primary check is the transaction failure via wait_for_tx.
            pytest.fail(f"Error during batch_deploy_streams call (with duplicate): {e}")
        finally:
            # Cleanup
            print("Cleaning up streams for duplicate test...")
            try:
                client.destroy_stream(stream_id=existing_stream_id, wait=True)
                print(f"Stream {existing_stream_id} destroyed.")
            except Exception as e:
                print(f"Error destroying existing stream {existing_stream_id}: {e}")
            try:
                # Check if new_stream_id was created (it shouldn't have been)
                exists_results = client.batch_stream_exists(locators=[
                    {"stream_id": new_stream_id, "data_provider": dp_address}
                ])
                if exists_results and exists_results[0]["exists"]:
                    print(f"Unexpected: stream {new_stream_id} was created, attempting destroy.")
                    client.destroy_stream(stream_id=new_stream_id, wait=True)
                else:
                    print(f"Stream {new_stream_id} correctly not created or already cleaned.")
            except Exception as e:
                print(f"Error during cleanup check for new stream {new_stream_id}: {e}")
        print("Finished test_batch_deploy_streams_duplicate_in_batch")

    def test_batch_stream_exists_mixed(self, client: TNClient):
        print("Starting test_batch_stream_exists_mixed")
        dp_address = client.get_current_account()
        other_dp_address = "0x1234567890123456789012345678901234567890" # Dummy, non-owned address

        prim_id = generate_unique_formatted_stream_id("bse-prim")
        comp_id = generate_unique_formatted_stream_id("bse-comp")
        non_exist_id_1 = generate_unique_formatted_stream_id("bse-nonexist1") # This will be a valid hash format
        non_exist_id_2 = generate_unique_formatted_stream_id("bse-nonexist2") # So will this

        # Deploy some streams
        deployed_streams = [prim_id, comp_id]
        try:
            print(f"Deploying stream: {prim_id}")
            client.deploy_stream(stream_id=prim_id, stream_type=STREAM_TYPE_PRIMITIVE, wait=True)
            print(f"Deploying stream: {comp_id}")
            client.deploy_stream(stream_id=comp_id, stream_type=STREAM_TYPE_COMPOSED, wait=True)
            print("Streams for mixed existence test deployed.")
        except Exception as e:
            pytest.fail(f"Failed to deploy streams for mixed existence test: {e}")

        locators: List[StreamLocatorInput] = [
            {"stream_id": prim_id, "data_provider": dp_address},          # Exists
            {"stream_id": comp_id, "data_provider": dp_address},          # Exists
            {"stream_id": non_exist_id_1, "data_provider": dp_address},   # Doesn't exist (ID)
            {"stream_id": prim_id, "data_provider": other_dp_address},    # Doesn't exist (Owner)
            {"stream_id": non_exist_id_2, "data_provider": dp_address},   # Doesn't exist (ID)
        ]

        expected_existence = [True, True, False, False, False]

        try:
            print(f"Checking mixed existence for: {locators}")
            results = client.batch_stream_exists(locators=locators)
            print(f"Mixed existence results: {results}")
            assert len(results) == len(locators)
            for i, res_item in enumerate(results):
                # Verify all keys are present
                assert "stream_id" in res_item
                assert "data_provider" in res_item
                assert "exists" in res_item
                # Match the specific locator and its expected existence
                # This is a bit more robust if order is not guaranteed, though it should be.
                matched_locator = next(loc for loc in locators if loc["stream_id"] == res_item["stream_id"] and loc["data_provider"] == res_item["data_provider"])
                original_index = locators.index(matched_locator)
                assert res_item["exists"] == expected_existence[original_index], \
                    f"Existence mismatch for {res_item['stream_id']} with DP {res_item['data_provider']}. Expected {expected_existence[original_index]}, got {res_item['exists']}"
        except Exception as e:
            pytest.fail(f"batch_stream_exists (mixed) failed: {e}")
        finally:
            # Cleanup
            print("Cleaning up streams for mixed existence test...")
            for stream_id_to_clean in deployed_streams:
                try:
                    client.destroy_stream(stream_id=stream_id_to_clean, wait=True)
                    print(f"Stream {stream_id_to_clean} destroyed.")
                except Exception as e:
                    print(f"Error destroying stream {stream_id_to_clean}: {e}")
        print("Finished test_batch_stream_exists_mixed")

    def test_batch_stream_exists_empty_input(self, client: TNClient):
        print("Starting test_batch_stream_exists_empty_input")
        results = client.batch_stream_exists(locators=[])
        assert results == [], "batch_stream_exists with empty list should return empty list"
        print("Finished test_batch_stream_exists_empty_input")

    def test_batch_filter_streams_by_existence_return_existing(self, client: TNClient):
        print("Starting test_batch_filter_streams_by_existence_return_existing")
        dp_address = client.get_current_account()
        s_existing_1 = generate_unique_formatted_stream_id("bfse-exist1")
        s_existing_2 = generate_unique_formatted_stream_id("bfse-exist2")
        s_non_existing_1 = generate_unique_formatted_stream_id("bfse-nonexist1")

        deployed_streams = [s_existing_1, s_existing_2]
        try:
            print(f"Deploying stream: {s_existing_1}")
            client.deploy_stream(stream_id=s_existing_1, stream_type=STREAM_TYPE_PRIMITIVE, wait=True)
            print(f"Deploying stream: {s_existing_2}")
            client.deploy_stream(stream_id=s_existing_2, stream_type=STREAM_TYPE_COMPOSED, wait=True)
            print("Streams for filter (existing) test deployed.")
        except Exception as e:
            pytest.fail(f"Failed to deploy streams for filter (existing) test: {e}")
        
        loc_existing_1: StreamLocatorInput = {"stream_id": s_existing_1, "data_provider": dp_address}
        loc_existing_2: StreamLocatorInput = {"stream_id": s_existing_2, "data_provider": dp_address}
        loc_non_existing_1: StreamLocatorInput = {"stream_id": s_non_existing_1, "data_provider": dp_address}

        all_locators = [loc_existing_1, loc_non_existing_1, loc_existing_2]
        expected_filtered_locators = [loc_existing_1, loc_existing_2] # Order might vary, sort for comparison

        try:
            print(f"Filtering for existing from: {all_locators}")
            filtered_results = client.batch_filter_streams_by_existence(
                locators=all_locators, 
                return_existing=True
            )
            print(f"Filtered (existing) results: {filtered_results}")
            # Sort results for comparison as order isn't guaranteed
            filtered_results_sorted = sorted(filtered_results, key=lambda x: x["stream_id"])
            expected_filtered_locators_sorted = sorted(expected_filtered_locators, key=lambda x: x["stream_id"])
            assert filtered_results_sorted == expected_filtered_locators_sorted, \
                "Filtered existing streams mismatch"
        except Exception as e:
            pytest.fail(f"batch_filter_streams_by_existence (return_existing=True) failed: {e}")
        finally:
            print("Cleaning up streams for filter (existing) test...")
            for stream_id_to_clean in deployed_streams:
                try:
                    client.destroy_stream(stream_id=stream_id_to_clean, wait=True)
                    print(f"Stream {stream_id_to_clean} destroyed.")
                except Exception as e:
                    print(f"Error destroying stream {stream_id_to_clean}: {e}")
        print("Finished test_batch_filter_streams_by_existence_return_existing")

    def test_batch_filter_streams_by_existence_return_non_existing(self, client: TNClient):
        print("Starting test_batch_filter_streams_by_existence_return_non_existing")
        dp_address = client.get_current_account()
        s_existing_1 = generate_unique_formatted_stream_id("bfse-exist-for-non")
        s_non_existing_1 = generate_unique_formatted_stream_id("bfse-nonexist-for-non1")
        s_non_existing_2 = generate_unique_formatted_stream_id("bfse-nonexist-for-non2")

        deployed_streams = [s_existing_1]
        try:
            print(f"Deploying stream: {s_existing_1}")
            client.deploy_stream(stream_id=s_existing_1, stream_type=STREAM_TYPE_PRIMITIVE, wait=True)
            print("Stream for filter (non-existing) test deployed.")
        except Exception as e:
            pytest.fail(f"Failed to deploy stream for filter (non-existing) test: {e}")

        loc_existing_1: StreamLocatorInput = {"stream_id": s_existing_1, "data_provider": dp_address}
        loc_non_existing_1: StreamLocatorInput = {"stream_id": s_non_existing_1, "data_provider": dp_address}
        loc_non_existing_2: StreamLocatorInput = {"stream_id": s_non_existing_2, "data_provider": dp_address}

        all_locators = [loc_existing_1, loc_non_existing_1, loc_non_existing_2]
        expected_filtered_locators = [loc_non_existing_1, loc_non_existing_2]

        try:
            print(f"Filtering for non-existing from: {all_locators}")
            filtered_results = client.batch_filter_streams_by_existence(
                locators=all_locators, 
                return_existing=False
            )
            print(f"Filtered (non-existing) results: {filtered_results}")
            filtered_results_sorted = sorted(filtered_results, key=lambda x: x["stream_id"])
            expected_filtered_locators_sorted = sorted(expected_filtered_locators, key=lambda x: x["stream_id"])
            assert filtered_results_sorted == expected_filtered_locators_sorted, \
                "Filtered non-existing streams mismatch"
        except Exception as e:
            pytest.fail(f"batch_filter_streams_by_existence (return_existing=False) failed: {e}")
        finally:
            print("Cleaning up streams for filter (non-existing) test...")
            for stream_id_to_clean in deployed_streams:
                try:
                    client.destroy_stream(stream_id=stream_id_to_clean, wait=True)
                    print(f"Stream {stream_id_to_clean} destroyed.")
                except Exception as e:
                    print(f"Error destroying stream {stream_id_to_clean}: {e}")
        print("Finished test_batch_filter_streams_by_existence_return_non_existing")

    def test_batch_filter_streams_empty_input(self, client: TNClient):
        print("Starting test_batch_filter_streams_empty_input")
        results_existing = client.batch_filter_streams_by_existence(locators=[], return_existing=True)
        assert results_existing == [], "batch_filter_streams_by_existence (empty, existing=True) should return empty list"
        
        results_non_existing = client.batch_filter_streams_by_existence(locators=[], return_existing=False)
        assert results_non_existing == [], "batch_filter_streams_by_existence (empty, existing=False) should return empty list"
        print("Finished test_batch_filter_streams_empty_input")

# Note: StreamTypePrimitive and StreamTypeComposed are constants (likely strings or ints)
# that should be imported or defined appropriately. If they are strings like "primitive", "composed",
# ensure they match what the Go binding expects or what NewStreamDefinitionForBinding processes.
# Assuming they are available from trufnetwork_sdk_py (e.g., as string constants).
# For this draft, I'm using StreamTypePrimitive and StreamTypeComposed directly as if they are defined variables.
# Ensure your conftest.py provides a working `client` fixture.

# Need to import List from typing for type hints
from typing import List 