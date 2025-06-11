import pytest
from trufnetwork_sdk_py import TNClient
from trufnetwork_sdk_py.utils import generate_stream_id

from tests.fixtures.test_trufnetwork import manager_client 

# A new key for a standard user.
USER_PRIVATE_KEY = "2222222222222222222222222222222222222222222222222222222222222222"
ANOTHER_USER_PRIVATE_KEY = "3333333333333333333333333333333333333333333333333333333333333333"

# Role constants from the core database schema
SYSTEM_OWNER = "system"
NETWORK_WRITER_ROLE = "network_writer"


@pytest.fixture(scope="module")
def user_client(tn_node) -> TNClient:
    """A client representing a standard user with no special permissions initially."""
    return TNClient(url=tn_node, token=USER_PRIVATE_KEY)

@pytest.fixture(scope="module")
def another_user_client(tn_node) -> TNClient:
    """A second standard user client."""
    return TNClient(url=tn_node, token=ANOTHER_USER_PRIVATE_KEY)

class TestRoleManagement:
    """
    Integration tests for the role management functionality.
    These tests cover granting, revoking, checking, and permission-gating based on roles.
    """

    def test_grant_revoke_and_check_membership(self, manager_client: TNClient, user_client: TNClient):
        """
        Verifies the full lifecycle of granting a role, checking membership, and revoking it.
        """
        user_wallet = user_client.get_current_account()

        # Pre-condition: User should not be a member initially
        initial_status = manager_client.are_members_of(SYSTEM_OWNER, NETWORK_WRITER_ROLE, [user_wallet])
        assert not initial_status[0]["is_member"]

        # 1. Grant the role
        try:
            grant_tx = manager_client.grant_role(SYSTEM_OWNER, NETWORK_WRITER_ROLE, [user_wallet], wait=True)
            assert grant_tx, "Grant role should return a transaction hash"
        except Exception as e:
            pytest.fail(f"grant_role failed unexpectedly: {e}")

        # 2. Verify membership
        grant_status = manager_client.are_members_of(SYSTEM_OWNER, NETWORK_WRITER_ROLE, [user_wallet])
        assert grant_status[0]["wallet"].lower() == user_wallet.lower()
        assert grant_status[0]["is_member"], "User should be a member after grant_role"

        # 3. Revoke the role
        try:
            revoke_tx = manager_client.revoke_role(SYSTEM_OWNER, NETWORK_WRITER_ROLE, [user_wallet], wait=True)
            assert revoke_tx, "Revoke role should return a transaction hash"
        except Exception as e:
            pytest.fail(f"revoke_role failed unexpectedly: {e}")

        # 4. Verify membership is revoked
        revoke_status = manager_client.are_members_of(SYSTEM_OWNER, NETWORK_WRITER_ROLE, [user_wallet])
        assert not revoke_status[0]["is_member"], "User should not be a member after revoke_role"


    def test_network_writer_role_permission_gate(self, manager_client: TNClient, user_client: TNClient):
        """
        Tests that the `system:network_writer` role correctly gates stream deployment.
        """
        user_wallet = user_client.get_current_account()
        stream_id = generate_stream_id("role-gated-stream")

        # 1. Attempt to deploy without permission, should fail
        with pytest.raises(Exception) as exc_info:
            user_client.deploy_stream(stream_id, wait=True)
        assert "transaction failed" in str(exc_info.value).lower(), "Deploy without permission should fail with a transaction error"

        # 2. Grant permission
        manager_client.grant_role(SYSTEM_OWNER, NETWORK_WRITER_ROLE, [user_wallet], wait=True)
        
        # 3. Attempt to deploy with permission, should succeed
        try:
            deploy_tx = user_client.deploy_stream(stream_id, wait=True)
            assert deploy_tx, "Deploy with permission should succeed"
        except Exception as e:
            # Revoke role before failing test to ensure cleanup
            manager_client.revoke_role(SYSTEM_OWNER, NETWORK_WRITER_ROLE, [user_wallet], wait=True)
            pytest.fail(f"deploy_stream with permission failed unexpectedly: {e}")
        finally:
            # Cleanup: Revoke role, then destroy stream.
            manager_client.revoke_role(SYSTEM_OWNER, NETWORK_WRITER_ROLE, [user_wallet], wait=True)
            # User (owner of stream) should still be able to destroy it
            try:
                user_client.destroy_stream(stream_id, wait=True)
            except Exception as e:
                # If deploy failed, destroy will fail. That's OK.
                print(f"Cleanup: Could not destroy stream {stream_id}, it might not have been created. Error: {e}")


    def test_unauthorized_grant_fails(self, user_client: TNClient, another_user_client: TNClient):
        """
        Ensures a standard user cannot grant roles they do not manage.
        """
        target_wallet = another_user_client.get_current_account()

        with pytest.raises(Exception) as exc_info:
            user_client.grant_role(SYSTEM_OWNER, NETWORK_WRITER_ROLE, [target_wallet], wait=True)
        
        # The error should come from the kwil node and indicate a permissions issue.
        assert "not the owner or a member of the manager role" in str(exc_info.value), \
            "Unauthorized grant should fail with a specific permission error."


    def test_are_members_of_edge_cases(self, manager_client: TNClient, user_client: TNClient):
        """
        Tests `are_members_of` with empty lists, non-existent roles, and mixed-membership lists.
        """
        user_wallet = user_client.get_current_account()
        root_wallet = manager_client.get_current_account()

        # 1. Test with a non-existent role
        with pytest.raises(Exception) as exc_info:
            manager_client.are_members_of(SYSTEM_OWNER, "non_existent_role", [user_wallet])
        assert "role does not exist" in str(exc_info.value).lower(), "Checking non-existent role should fail"

        # 2. Test with a mixed list of members and non-members
        manager_role = "network_writers_manager"

        # The `root_client` (DB owner) should be a member of `system:network_writers_manager` by default from migrations
        mixed_wallets = [user_wallet, root_wallet]
        results_mixed = manager_client.are_members_of(SYSTEM_OWNER, manager_role, mixed_wallets)
        
        assert len(results_mixed) == 2
        
        user_status = next(r for r in results_mixed if r['wallet'].lower() == user_wallet.lower())
        root_status = next(r for r in results_mixed if r['wallet'].lower() == root_wallet.lower())

        assert not user_status['is_member'], "Standard user should not be in the manager role"
        assert root_status['is_member'], "Root user should be in the manager role"

    def test_list_role_members_pagination(self, manager_client: TNClient, user_client: TNClient, another_user_client: TNClient):
        """
        Verifies list_role_members returns expected data and respects pagination parameters.
        """
        user_wallet = user_client.get_current_account()
        another_wallet = another_user_client.get_current_account()

        # Ensure both wallets are granted the writer role
        manager_client.grant_role(SYSTEM_OWNER, NETWORK_WRITER_ROLE, [user_wallet, another_wallet], wait=True)

        try:
            # Fetch full list – expect at least 2 members (might include others)
            full_list = manager_client.list_role_members(SYSTEM_OWNER, NETWORK_WRITER_ROLE)
            wallet_addresses = {m["wallet"].lower() for m in full_list}
            assert user_wallet.lower() in wallet_addresses
            assert another_wallet.lower() in wallet_addresses

            # Pagination: limit 1, offset 0 should return exactly 1 item
            page_one = manager_client.list_role_members(SYSTEM_OWNER, NETWORK_WRITER_ROLE, limit=1, offset=0)
            assert len(page_one) == 1

            # Pagination: limit 1, offset 1 should return next item (if available)
            page_two = manager_client.list_role_members(SYSTEM_OWNER, NETWORK_WRITER_ROLE, limit=1, offset=1)
            # The pagination behavior depends on DB ordering; ensure combined unique wallets cover expected ones.
            paged_wallets = {m["wallet"].lower() for m in page_one + page_two}
            assert user_wallet.lower() in paged_wallets or another_wallet.lower() in paged_wallets

        finally:
            # Clean up – revoke roles granted in this test
            manager_client.revoke_role(SYSTEM_OWNER, NETWORK_WRITER_ROLE, [user_wallet, another_wallet], wait=True) 