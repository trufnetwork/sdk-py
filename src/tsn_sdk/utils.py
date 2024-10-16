import tsn_sdk_c_bindings.exports as tsn_sdk

def generate_stream_id(name: str) -> str:
    return tsn_sdk.GenerateStreamId(name)