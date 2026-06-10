"""Shared skip markers for tests blocked on node-side provisioning."""

import pytest

# Node #1384 ("charge 100 TRUF per stream on stream creation") made the common
# create_stream/insert/taxonomy actions charge a fee via hoodi_tt.balance/transfer.
# That bridge is provisioned only by the node's in-process Go test harness, never
# over RPC, so this black-box suite can't register or fund it — every stream
# deploy fails with `namespace not found: "hoodi_tt"`. The fee behavior itself is
# covered in the trufnetwork/node repository (tests/streams), where the harness
# funds the bridge. Remove this marker and its uses once the dev bridge faucet
# lands and the fixture funds the test wallets.
skip_until_stream_creation_fee_funded = pytest.mark.skip(
    reason="blocked on node stream-creation fee (#1384): hoodi_tt bridge not "
    "provisioned for black-box RPC CI — covered by trufnetwork/node tests"
)
