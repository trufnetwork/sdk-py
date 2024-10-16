import tsn_sdk.tsn_sdk_c_bindings.exports as tsn_sdk

def generate_stream_id(name: str) -> str:
    return tsn_sdk.GenerateStreamId(name)

def wait_for_tx(client: tsn_sdk.Client, tx_hash: str) -> None:
    tsn_sdk.WaitForTx(client, tx_hash)