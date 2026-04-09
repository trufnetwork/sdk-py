"""Unit tests for LocalClient (tn_local admin JSON-RPC wrapper).

These tests spin up a minimal HTTP server in the test process that mimics
a Kwil admin JSON-RPC server for the local.* methods. They verify that
LocalClient translates Python inputs into the correct wire shape and
decodes responses into the expected Python types.

No running node is required. Integration with a real tn_local-enabled
node is exercised separately in tests/test_local_client_integration.py
(not in this file).
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional

import pytest

from trufnetwork_sdk_py import (
    LocalClient,
    STREAM_TYPE_PRIMITIVE,
    STREAM_TYPE_COMPOSED,
)


class _FakeAdminHandler(BaseHTTPRequestHandler):
    """Minimal JSON-RPC handler used by LocalClient tests. Shared state
    lives on the HTTPServer instance via server.state.
    """

    def log_message(self, format, *args):  # silence default logging
        pass

    def do_POST(self):  # noqa: N802 (BaseHTTPRequestHandler naming)
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        try:
            req = json.loads(body)
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        state: _State = self.server.state  # type: ignore[attr-defined]
        state.last_method = req.get("method")
        state.last_params = req.get("params")

        rpc_err = state.errors.get(req["method"])
        if rpc_err is not None:
            resp = {
                "jsonrpc": "2.0",
                "id": req.get("id"),
                "error": rpc_err,
            }
        else:
            result = state.results.get(req["method"], {})
            resp = {
                "jsonrpc": "2.0",
                "id": req.get("id"),
                "result": result,
            }

        body_out = json.dumps(resp).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_out)))
        self.end_headers()
        self.wfile.write(body_out)


class _State:
    def __init__(self):
        self.last_method: Optional[str] = None
        self.last_params: Any = None
        self.results: dict[str, Any] = {}
        self.errors: dict[str, Any] = {}


@pytest.fixture
def admin_server():
    """Spin up a fake admin JSON-RPC server on an ephemeral port."""
    server = HTTPServer(("127.0.0.1", 0), _FakeAdminHandler)
    server.state = _State()  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base_url = f"http://{host}:{port}"
    yield server, base_url
    server.shutdown()
    server.server_close()


@pytest.fixture
def local_client(admin_server):
    server, base_url = admin_server
    return LocalClient(base_url), server


# ═══════════════════════════════════════════════════════════════
# CREATE STREAM
# ═══════════════════════════════════════════════════════════════


def test_create_stream_primitive(local_client):
    client, server = local_client

    client.create_stream("st00000000000000000000000000demo", STREAM_TYPE_PRIMITIVE)

    assert server.state.last_method == "local.create_stream"
    assert server.state.last_params["stream_id"] == "st00000000000000000000000000demo"
    assert server.state.last_params["stream_type"] == "primitive"
    # Critical regression: no data_provider on the wire.
    assert "data_provider" not in server.state.last_params


def test_create_stream_composed(local_client):
    client, server = local_client
    client.create_stream("st0000000000000000000000composed", STREAM_TYPE_COMPOSED)
    assert server.state.last_params["stream_type"] == "composed"


def test_create_stream_rpc_error(local_client):
    client, server = local_client
    server.state.errors["local.create_stream"] = {
        "code": -32602,
        "message": "stream already exists: st...",
    }
    with pytest.raises(Exception) as excinfo:
        client.create_stream("st00000000000000000000000000demo", STREAM_TYPE_PRIMITIVE)
    assert "stream already exists" in str(excinfo.value)


# ═══════════════════════════════════════════════════════════════
# INSERT RECORDS
# ═══════════════════════════════════════════════════════════════


def test_insert_records_single_stream(local_client):
    client, server = local_client
    client.insert_records("st00000000000000000000000000demo", [
        {"event_time": 1000, "value": "10.5"},
        {"event_time": 2000, "value": "20.5"},
    ])

    assert server.state.last_method == "local.insert_records"
    params = server.state.last_params
    assert "data_provider" not in params
    assert params["stream_id"] == [
        "st00000000000000000000000000demo",
        "st00000000000000000000000000demo",
    ]
    assert params["event_time"] == [1000, 2000]
    assert params["value"] == ["10.5", "20.5"]


def test_batch_insert_multiple_streams(local_client):
    client, server = local_client
    client.batch_insert_records([
        {
            "stream_id": "st00000000000000000000000000aaaa",
            "inputs": [{"event_time": 1, "value": "1.0"}],
        },
        {
            "stream_id": "st00000000000000000000000000bbbb",
            "inputs": [
                {"event_time": 2, "value": "2.0"},
                {"event_time": 3, "value": "3.0"},
            ],
        },
    ])
    params = server.state.last_params
    assert params["stream_id"] == [
        "st00000000000000000000000000aaaa",
        "st00000000000000000000000000bbbb",
        "st00000000000000000000000000bbbb",
    ]
    assert params["event_time"] == [1, 2, 3]
    assert params["value"] == ["1.0", "2.0", "3.0"]


def test_insert_records_numeric_value_coerced_to_string(local_client):
    client, server = local_client
    client.insert_records("st00000000000000000000000000demo", [
        {"event_time": 1000, "value": 42.5},
    ])
    assert server.state.last_params["value"] == ["42.5"]


# ═══════════════════════════════════════════════════════════════
# INSERT TAXONOMY
# ═══════════════════════════════════════════════════════════════


def test_insert_taxonomy(local_client):
    client, server = local_client
    client.insert_taxonomy(
        "st0000000000000000000000composed",
        child_stream_ids=["st000000000000000000000000child1", "st000000000000000000000000child2"],
        weights=["0.6", "0.4"],
        start_date=100,
    )
    assert server.state.last_method == "local.insert_taxonomy"
    params = server.state.last_params
    assert "data_provider" not in params
    assert "child_data_providers" not in params
    assert params["stream_id"] == "st0000000000000000000000composed"
    assert params["child_stream_ids"] == [
        "st000000000000000000000000child1",
        "st000000000000000000000000child2",
    ]
    assert params["weights"] == ["0.6", "0.4"]
    assert params["start_date"] == 100


# ═══════════════════════════════════════════════════════════════
# GET RECORD
# ═══════════════════════════════════════════════════════════════


def test_get_record_latest(local_client):
    client, server = local_client
    server.state.results["local.get_record"] = {
        "records": [
            {"event_time": 5000, "value": "99.5", "created_at": 42},
        ]
    }

    records = client.get_record("st00000000000000000000000000demo")
    assert records == [{"event_time": 5000, "value": "99.5", "created_at": 42}]

    params = server.state.last_params
    assert params["stream_id"] == "st00000000000000000000000000demo"
    # No from/to bounds → both omitted from the wire (omitempty on sentinel)
    assert "from_time" not in params
    assert "to_time" not in params


def test_get_record_with_range(local_client):
    client, server = local_client
    server.state.results["local.get_record"] = {
        "records": [
            {"event_time": 1000, "value": "10.0", "created_at": 1},
            {"event_time": 2000, "value": "20.0", "created_at": 2},
        ]
    }

    records = client.get_record(
        "st00000000000000000000000000demo", from_time=500, to_time=3000
    )
    assert len(records) == 2
    assert records[0]["event_time"] == 1000
    assert records[1]["value"] == "20.0"
    assert server.state.last_params["from_time"] == 500
    assert server.state.last_params["to_time"] == 3000


def test_get_record_empty(local_client):
    client, server = local_client
    server.state.results["local.get_record"] = {"records": []}
    records = client.get_record("st00000000000000000000000000demo")
    assert records == []


# ═══════════════════════════════════════════════════════════════
# GET INDEX
# ═══════════════════════════════════════════════════════════════


def test_get_index_with_base_time(local_client):
    client, server = local_client
    server.state.results["local.get_index"] = {
        "records": [
            {"event_time": 1000, "value": "100.000000000000000000"},
            {"event_time": 2000, "value": "200.000000000000000000"},
        ]
    }

    records = client.get_index(
        "st00000000000000000000000000demo", base_time=1000
    )
    assert len(records) == 2
    assert records[0]["value"] == "100.000000000000000000"
    assert server.state.last_params["base_time"] == 1000
    # Only base_time was set — from/to omitted
    assert "from_time" not in server.state.last_params


# ═══════════════════════════════════════════════════════════════
# LIST STREAMS
# ═══════════════════════════════════════════════════════════════


def test_list_streams(local_client):
    client, server = local_client
    server.state.results["local.list_streams"] = {
        "streams": [
            {
                "data_provider": "0xabcdef1234567890abcdef1234567890abcdef12",
                "stream_id": "st00000000000000000000000000demo",
                "stream_type": "primitive",
                "created_at": 42,
            },
        ]
    }

    streams = client.list_streams()
    assert len(streams) == 1
    s = streams[0]
    # data_provider is preserved on the response (mirrors consensus shape)
    assert s["data_provider"] == "0xabcdef1234567890abcdef1234567890abcdef12"
    assert s["stream_id"] == "st00000000000000000000000000demo"
    assert s["stream_type"] == "primitive"
    assert s["created_at"] == 42
    assert server.state.last_method == "local.list_streams"


def test_list_streams_empty(local_client):
    client, server = local_client
    server.state.results["local.list_streams"] = {"streams": []}
    streams = client.list_streams()
    assert streams == []
