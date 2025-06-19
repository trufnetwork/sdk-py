from datetime import datetime, timezone, timedelta

# Import the high-level Python SDK
from trufnetwork_sdk_py.client import TNClient

# ---------------------------------------------------------------------------
# Configuration – replace the values below with your own setup
# ---------------------------------------------------------------------------
ENDPOINT = "https://gateway.mainnet.truf.network"  # Or your local node, e.g. http://localhost:8484
PRIVATE_KEY = "0000000000000000000000000000000000000000000000000000000000000001"  # Replace with your private key


def main() -> None:
    """Minimal example showing how to invoke a read-only custom procedure."""

    # 1. Initialise the client (signer is only needed for write procedures)
    client = TNClient(ENDPOINT, PRIVATE_KEY)

    # 2. Build the positional argument list required by the stored procedure
    one_week_ago = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp())
    now = int(datetime.now(timezone.utc).timestamp())
    time_interval = 31_536_000  # one year in seconds

    # The get_divergence_index_change procedure expects 5 positional arguments
    args = [one_week_ago, now, None, None, time_interval]

    # 3. Invoke the procedure (read-only ➜ no transaction fee)
    # NOTE: The Python SDK exposes a generic `call_procedure` helper for this
    result = client.call_procedure("get_divergence_index_change", args)

    # 4. Display the returned records in a simple CSV-like format
    print("Columns:", result["column_names"])
    for row in result["values"]:
        print(row)


if __name__ == "__main__":
    main() 