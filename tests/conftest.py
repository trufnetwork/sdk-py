# conftest.py

from glob import glob
import pytest
from tests.helpers.permissions import ensure_network_writer


def refactor(string: str) -> str:
    return string.replace("/", ".").replace("\\", ".").replace(".py", "")


pytest_plugins = [refactor(fixture) for fixture in glob("tests/fixtures/*.py") if "__" not in fixture]


@pytest.fixture(scope="session")
def grant_network_writer(manager_client):
    """
    Fixture that provides a function to grant network_writer role to a client's wallet.
    
    Usage:
        grant_network_writer(client)   # client is TNClient
    """
    def _grant(client):
        ensure_network_writer(manager_client, client.get_current_account())
    return _grant
