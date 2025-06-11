from tests.fixtures.test_trufnetwork import SYSTEM_OWNER, NETWORK_WRITER_ROLE


def ensure_network_writer(manager_client, wallet: str):
    """
    Grant `system:network_writer` to `wallet` if it doesn't already have it.
    
    Args:
        manager_client: TNClient instance with manager privileges
        wallet: Wallet address (string) to grant the role to
    """
    status = manager_client.are_members_of(
        SYSTEM_OWNER, NETWORK_WRITER_ROLE, [wallet]
    )[0]["is_member"]

    if not status:
        manager_client.grant_role(
            SYSTEM_OWNER, NETWORK_WRITER_ROLE, [wallet], wait=True
        ) 