from dataclasses import dataclass, field
import json
import logging
import os
import shutil
import subprocess
import time
from typing import Optional

import pytest


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the network name to use
NETWORK_NAME = "tsn_network"


@dataclass
class ContainerSpec:
    """Configuration for a docker container"""

    name: str
    image: str
    tmpfs_path: Optional[str] = None
    env_vars: list[str] = field(default_factory=list)
    ports: dict[str, str] = field(default_factory=dict)
    entrypoint: Optional[str] = None
    args: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.env_vars is None:
            self.env_vars = []
        if self.ports is None:
            self.ports = {}
        if self.args is None:
            self.args = []


# Container specifications
POSTGRES_CONTAINER = ContainerSpec(
    name="test-kwil-postgres",
    image="kwildb/postgres:latest",
    tmpfs_path="/var/lib/postgresql/data",
    env_vars=["POSTGRES_HOST_AUTH_METHOD=trust"]
)

TSN_DB_CONTAINER = ContainerSpec(
    name="test-tsn-db",
    image="tsn-db:local",
    tmpfs_path="/root/.kwild",
    entrypoint="/app/kwild",
    args=[
        "start",
        "--autogen",
        "--db-owner",
        "0xecCc1ffEe06311c50Aa16e0E2acf2CD142d63905",
        "--db.host",
        "test-kwil-postgres",
    ],
    env_vars=[
        "CONFIG_PATH=/root/.kwild",
        "KWILD_APP_HOSTNAME=test-tsn-db",
        "KWILD_APP_PG_DB_HOST=test-kwil-postgres",
        "KWILD_APP_PG_DB_PORT=5432",
        "KWILD_APP_PG_DB_USER=postgres",
        "KWILD_APP_PG_DB_PASSWORD=",
        "KWILD_APP_PG_DB_NAME=postgres",
        "KWILD_CHAIN_P2P_EXTERNAL_ADDRESS=http://test-tsn-db:26656",
    ],
    ports={"50051": "50051", "50151": "50151", "8080": "8080", "8484": "8484", "26656": "26656", "26657": "26657"},
)


def run_docker_command(args: list[str], check: bool = False) -> subprocess.CompletedProcess:
    """
    Executes a docker command with the given list of arguments.

    Args:
        args: List of command arguments to pass to docker
        check: If True, raises CalledProcessError on non-zero exit status

    Returns:
        CompletedProcess instance with command output

    Raises:
        subprocess.CalledProcessError: If check=True and command returns non-zero exit status
    """
    command = ["docker", *args]
    logger.debug(f"Running docker command: {' '.join(command)}")
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=check)
        if result.stderr:
            logger.debug(f"Docker command stderr: {result.stderr}")
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Docker command failed: {e.stderr}")
        raise


def wait_for_postgres_health(max_attempts: int = 30) -> bool:
    """
    Wait for postgres container to be healthy

    Args:
        max_attempts: Maximum number of health check attempts

    Returns:
        bool: True if postgres becomes healthy, False otherwise
    """
    for i in range(max_attempts):
        try:
            result = run_docker_command(["exec", POSTGRES_CONTAINER.name, "pg_isready", "-U", "postgres"])
            if result.returncode == 0:
                logger.info(f"Postgres is healthy after {i+1} attempts")
                return True
            logger.debug(f"Postgres not ready (attempt {i+1}/{max_attempts}): {result.stderr}")
        except Exception as e:
            logger.error(f"Error checking postgres health: {e!s}")
        time.sleep(1)
    return False


def wait_for_tsn_health(max_attempts: int = 10) -> bool:
    """
    Wait for TSN-DB node to be healthy and produce first block

    Args:
        max_attempts: Maximum number of health check attempts

    Returns:
        bool: True if TSN-DB becomes healthy, False otherwise
    """
    import requests

    for i in range(max_attempts):
        try:
            logger.info(f"Checking TSN-DB health (attempt {i+1}/{max_attempts})")
            response = requests.get("http://localhost:8484/api/v1/health")
            if response.status_code == 200:
                data = response.json()
                if data.get("healthy") and data.get("services").get("user").get("block_height") >= 1:
                    logger.info(f"TSN-DB is healthy after {i+1} attempts")
                    logger.debug(f"Health check response: {json.dumps(data, indent=2)}")
                    return True
            logger.debug(f"TSN-DB not healthy yet (attempt {i+1}/{max_attempts}): {response.text}")
        except Exception as e:
            logger.debug(f"Error checking TSN-DB health (attempt {i+1}/{max_attempts}): {e!s}")
        time.sleep(1)
    return False


def start_container(spec: ContainerSpec, network: str) -> bool:
    """
    Start a docker container with the given specification

    Args:
        spec: Container specification
        network: Docker network name

    Returns:
        bool: True if container starts successfully, False otherwise
    """
    # First ensure container doesn't exist
    run_docker_command(["rm", "-f", spec.name])

    args = ["run", "--rm", "--name", spec.name, "--network", network, "-d"]

    if spec.tmpfs_path:
        args.extend(["--tmpfs", spec.tmpfs_path])

    for env in spec.env_vars:
        args.extend(["-e", env])

    for host_port, container_port in spec.ports.items():
        args.extend(["-p", f"{host_port}:{container_port}"])

    if spec.entrypoint:
        args.extend(["--entrypoint", spec.entrypoint])

    args.append(spec.image)

    if spec.args:
        args.extend(spec.args)

    try:
        run_docker_command(args, check=True)
        logger.info(f"Successfully started container {spec.name}")

        # Get container logs
        time.sleep(2)  # Wait a bit for container to initialize
        logs = run_docker_command(["logs", spec.name])
        logger.debug(f"Container logs for {spec.name}:")
        logger.debug(logs.stdout)
        if logs.stderr:
            logger.debug(f"Container stderr: {logs.stderr}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start container {spec.name}: {e.stderr}")
        return False


def stop_container(name: str) -> bool:
    """
    Stop a docker container

    Args:
        name: Name of the container to stop

    Returns:
        bool: True if container stops successfully, False otherwise
    """
    logger.info(f"Stopping container {name}...")
    try:
        run_docker_command(["stop", name], check=True)
        logger.info(f"Successfully stopped container {name}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to stop container {name}: {e.stderr}")
        return False
    finally:
        # Clean up config dir if it exists
        if name == TSN_DB_CONTAINER.name and hasattr(TSN_DB_CONTAINER, "_config_dir"):
            shutil.rmtree(getattr(TSN_DB_CONTAINER, "_config_dir"), ignore_errors=True)


@pytest.fixture(scope="session")
def docker_network():
    """
    Pytest fixture to set up and tear down a Docker network.

    Setup:
      - Attempts to remove any existing network with the same name
      - Creates a new network using: docker network create <NETWORK_NAME>

    Teardown:
      - Removes the network using: docker network rm <NETWORK_NAME>

    Returns:
        str: The name of the created network

    Raises:
        pytest.FixureError: If network creation fails
    """
    logger.info("Setting up docker network...")
    # Remove existing network (ignore errors)
    run_docker_command(["network", "rm", NETWORK_NAME])

    # Create the new network
    try:
        run_docker_command(["network", "create", NETWORK_NAME], check=True)
        logger.info(f"Docker network '{NETWORK_NAME}' created.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create docker network '{NETWORK_NAME}': {e.stderr}")
        pytest.fail(f"Failed to create docker network '{NETWORK_NAME}': {e.stderr}")

    try:
        yield NETWORK_NAME
    finally:
        logger.info("Tearing down docker network...")
        run_docker_command(["network", "rm", NETWORK_NAME])
        logger.info(f"Docker network '{NETWORK_NAME}' removed.")


@pytest.fixture(scope="session")
def tn_node(docker_network):
    """
    Pytest fixture that sets up a TSN-DB node with Postgres for testing.

    This fixture:
    1. Starts a Postgres container
    2. Waits for Postgres to be healthy
    3. Starts the TSN-DB node
    4. Waits for the node to be healthy and produce its first block
    5. Cleans up both containers after tests

    Args:
        docker_network: The docker network fixture

    Returns:
        str: The API endpoint URL for the TSN-DB node

    Raises:
        pytest.FixureError: If container setup fails
    """
    logger.info("Starting Postgres container...")
    if not start_container(POSTGRES_CONTAINER, docker_network):
        pytest.fail("Failed to start Postgres container")

    logger.info("Waiting for Postgres to be healthy...")
    if not wait_for_postgres_health():
        stop_container(POSTGRES_CONTAINER.name)
        pytest.fail("Postgres failed to become healthy")

    logger.info("Starting TSN-DB container...")
    if not start_container(TSN_DB_CONTAINER, docker_network):
        stop_container(POSTGRES_CONTAINER.name)
        pytest.fail("Failed to start TSN-DB container")

    logger.info("Waiting for TSN-DB node to be healthy...")
    if not wait_for_tsn_health():
        stop_container(TSN_DB_CONTAINER.name)
        stop_container(POSTGRES_CONTAINER.name)
        pytest.fail("TSN-DB node failed to become healthy")

    try:
        yield "http://localhost:8484"
    finally:
        logger.info("Cleaning up containers...")
        stop_container(TSN_DB_CONTAINER.name)
        stop_container(POSTGRES_CONTAINER.name)


class TrufNetworkProvider:
    """Provider class for interacting with the TrufNetwork node"""

    def __init__(self, api_endpoint: str = "http://localhost:8484"):
        """
        Initialize the provider

        Args:
            api_endpoint: The API endpoint URL for the TSN node
        """
        self.api_endpoint = api_endpoint
        self.provider = self

    def get_provider(self):
        """Get the provider instance"""
        return self.provider


@pytest.fixture(scope="session")
def tn_provider(tn_node) -> TrufNetworkProvider:
    """
    Returns a TrufNetworkProvider instance configured to use the test TSN node.

    Args:
        tn_node: The TSN node fixture providing the API endpoint

    Returns:
        TrufNetworkProvider: Configured provider instance
    """
    return TrufNetworkProvider(api_endpoint=tn_node)


# Skip these tests on CI environment
@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Local development fixture tests, skipped in CI")
class TestTrufNetworkFixtures:
    """
    Test suite for TrufNetwork fixtures.

    These tests verify the fixture setup/teardown behavior.
    Only run locally, skipped in CI.
    """

    def test_docker_network_fixture(self, docker_network):
        """Test docker network creation and cleanup"""
        # Check network exists
        result = run_docker_command(["network", "inspect", docker_network])
        assert result.returncode == 0, "Docker network should exist during test"

    def test_tsn_node_fixture(self, tn_node):
        """Test TSN node setup and health"""
        import requests

        # Verify endpoint is accessible
        response = requests.get(f"{tn_node}/api/v1/health")
        assert response.status_code == 200

        data = response.json()
        assert data.get("healthy") is True
        assert data.get("services").get("user").get("block_height") >= 1

        # Verify containers are running
        for container in [POSTGRES_CONTAINER.name, TSN_DB_CONTAINER.name]:
            result = run_docker_command(["container", "inspect", container])
            assert result.returncode == 0, f"Container {container} should be running"

    def test_tn_provider_fixture(self, tn_provider):
        """Test TrufNetworkProvider configuration"""
        assert isinstance(tn_provider, TrufNetworkProvider)
        assert tn_provider.api_endpoint.startswith("http://")
        assert tn_provider.get_provider() is tn_provider

DEFAULT_TN_PRIVATE_KEY = "0" * 63 + "1"  # 64 zeros ending with 1


