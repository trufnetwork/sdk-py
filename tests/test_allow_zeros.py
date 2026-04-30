"""Tests for the per-stream allow_zeros configuration.

Mirrors the behaviors covered upstream in
node/tests/streams/allow_zeros_test.go from the SDK consumer perspective:
the deploy-time opt-in, the post-deploy toggle, and the owner gate on
set_allow_zeros.
"""

from datetime import datetime, timezone

import pytest

from trufnetwork_sdk_py.client import TNClient
from trufnetwork_sdk_py.utils import generate_stream_id
from tests.fixtures.test_trufnetwork import tn_node, DB_PRIVATE_KEY


OWNER_PRIVATE_KEY = "0121234567890123456789012345678901234567890123456789012345178901"


@pytest.fixture(scope="module")
def owner_client(tn_node, grant_network_writer):
    client = TNClient(tn_node, OWNER_PRIVATE_KEY)
    grant_network_writer(client)
    return client


@pytest.fixture(scope="module")
def non_owner_client(tn_node):
    # DB_PRIVATE_KEY is a separate signer; no network_writer grant required
    # because set_allow_zeros only needs a transaction (and the owner check
    # runs inside the action itself, which is exactly what we want to assert).
    return TNClient(tn_node, DB_PRIVATE_KEY)


def _ts(date_str: str) -> int:
    return int(
        datetime.strptime(date_str, "%Y-%m-%d")
        .replace(tzinfo=timezone.utc)
        .timestamp()
    )


def _safe_destroy(client: TNClient, stream_id: str) -> None:
    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass


def test_default_drops_zero_inserts(owner_client: TNClient):
    """Without allow_zeros, value=0 is silently dropped on insert."""
    stream_id = generate_stream_id("allow_zeros_default_drop")
    _safe_destroy(owner_client, stream_id)

    owner_client.deploy_stream(stream_id)
    try:
        assert owner_client.get_allow_zeros(stream_id) is False

        owner_client.insert_record(
            stream_id, {"date": _ts("2024-01-01"), "value": 0}
        )
        owner_client.insert_record(
            stream_id, {"date": _ts("2024-01-02"), "value": 5}
        )

        records = owner_client.get_records(
            stream_id,
            date_from=_ts("2024-01-01"),
            date_to=_ts("2024-01-02"),
            use_cache=False,
        ).data

        event_times = {r["EventTime"] for r in records}
        assert str(_ts("2024-01-01")) not in event_times, (
            "zero value must be dropped under default allow_zeros=False"
        )
        assert str(_ts("2024-01-02")) in event_times
    finally:
        _safe_destroy(owner_client, stream_id)


def test_allow_zeros_true_at_deploy_persists_zero(owner_client: TNClient):
    """deploy_stream(allow_zeros=True) opts the stream out of the zero filter."""
    stream_id = generate_stream_id("allow_zeros_deploy_true")
    _safe_destroy(owner_client, stream_id)

    owner_client.deploy_stream(stream_id, allow_zeros=True)
    try:
        assert owner_client.get_allow_zeros(stream_id) is True

        owner_client.insert_record(
            stream_id, {"date": _ts("2024-02-01"), "value": 0}
        )

        records = owner_client.get_records(
            stream_id,
            date_from=_ts("2024-02-01"),
            date_to=_ts("2024-02-01"),
            use_cache=False,
        ).data

        assert len(records) == 1, "zero record must persist when allow_zeros=True"
        assert float(records[0]["Value"]) == 0.0
    finally:
        _safe_destroy(owner_client, stream_id)


def test_set_allow_zeros_toggle_is_forward_only(owner_client: TNClient):
    """Flipping allow_zeros affects future inserts only; pre-flip drops stay dropped."""
    stream_id = generate_stream_id("allow_zeros_toggle")
    _safe_destroy(owner_client, stream_id)

    owner_client.deploy_stream(stream_id)
    try:
        # Pre-flip: zero is dropped
        owner_client.insert_record(
            stream_id, {"date": _ts("2024-03-01"), "value": 0}
        )

        # Flip on
        owner_client.set_allow_zeros(stream_id, True)
        assert owner_client.get_allow_zeros(stream_id) is True

        # Post-flip: zero persists
        owner_client.insert_record(
            stream_id, {"date": _ts("2024-03-02"), "value": 0}
        )

        records = owner_client.get_records(
            stream_id,
            date_from=_ts("2024-03-01"),
            date_to=_ts("2024-03-02"),
            use_cache=False,
        ).data
        event_times = {r["EventTime"] for r in records}

        assert str(_ts("2024-03-01")) not in event_times, (
            "pre-flip zero must remain dropped (forward-only semantics)"
        )
        assert str(_ts("2024-03-02")) in event_times, (
            "post-flip zero must persist"
        )

        # Flip back off and confirm the read reflects it
        owner_client.set_allow_zeros(stream_id, False)
        assert owner_client.get_allow_zeros(stream_id) is False
    finally:
        _safe_destroy(owner_client, stream_id)


def test_non_owner_cannot_toggle_allow_zeros(
    owner_client: TNClient, non_owner_client: TNClient
):
    """The owner gate on set_allow_zeros rejects non-owners."""
    stream_id = generate_stream_id("allow_zeros_owner_gate")
    _safe_destroy(owner_client, stream_id)

    owner_client.deploy_stream(stream_id)
    try:
        with pytest.raises(Exception):
            non_owner_client.set_allow_zeros(stream_id, True)

        # Owner-side state unchanged.
        assert owner_client.get_allow_zeros(stream_id) is False
    finally:
        _safe_destroy(owner_client, stream_id)
