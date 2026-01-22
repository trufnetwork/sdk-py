"""
TRUF NETWORK Python SDK – Client

Migration notice (Cache API)
----------------------------
•   Version ≤ cache update: The methods get_records, get_first_record, and get_index returned
    bare lists / StreamRecord objects.
•   Version cache update+1 introduced cache-aware responses.  For backward compatibility we
    keep a *bridge* behavior: if `use_cache` is **omitted**, the old format is
    returned **with a DeprecationWarning**.
•   The bridge will be removed in **version cache update+1.0.0** (next major).  After that,
    ommitting `use_cache` will just return the new CacheAwareResponse structure, but without a warning, defaulting to False.
Action (current version):
    –   **Always pass** the `use_cache` keyword when you migrate:
         • `use_cache=False`  → bypass cache **and** return the **new** `CacheAwareResponse` structure (no warning).
         • `use_cache=True`   → consult cache and return `CacheAwareResponse`.
    –   Omitting `use_cache` continues to yield the **legacy** list/record structure but emits a `DeprecationWarning`.

After bridge removal (next major):
    • Omitting `use_cache` will behave exactly the same as `use_cache=False` – it will return a `CacheAwareResponse` **without** any warning.
    • The legacy structure will no longer be available.

See tests in `tests/test_cache_support.py` for working examples.
"""

import json
import warnings

import trufnetwork_sdk_c_bindings.exports as truf_sdk
import trufnetwork_sdk_c_bindings.go as go

from typing import Any, TypedDict, Literal, cast, overload, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")

# Sentinel meaning "keyword not supplied"
_UNSET: Literal[None] = None

# Expose StreamType constants at the Python level
STREAM_TYPE_PRIMITIVE = cast(Literal["primitive"], truf_sdk.StreamTypePrimitive)
STREAM_TYPE_COMPOSED = cast(Literal["composed"], truf_sdk.StreamTypeComposed)
VISIBILITY_PUBLIC = truf_sdk.VisibilityPublic
VISIBILITY_PRIVATE = truf_sdk.VisibilityPrivate


class Record(TypedDict):
    date: int  # UNIX
    value: float


class RecordBatch(TypedDict):
    stream_id: str
    inputs: list[Record]


class StreamDefinitionInput(TypedDict):
    stream_id: str
    stream_type: Literal["primitive", "composed"]


class StreamLocatorInput(TypedDict):
    stream_id: str
    data_provider: str | None


class StreamExistsResult(TypedDict):
    stream_id: str
    data_provider: str
    exists: bool


class RoleMembershipStatus(TypedDict):
    wallet: str
    is_member: bool


class RoleMember(TypedDict):
    wallet: str
    granted_at: int
    granted_by: str


class AttestationMetadata(TypedDict):
    request_tx_id: str
    attestation_hash: bytes
    requester: bytes
    created_height: int
    signed_height: int | None
    encrypt_sig: bool


class AttestationSignatureVerification(TypedDict):
    """Result of attestation signature verification"""

    validator_address: str  # Ethereum address of validator who signed (0x...)
    canonical_payload: bytes  # The payload that was signed (excludes signature)
    signature: bytes  # The 65-byte signature (R || S || V)


class ParsedAttestationPayload(BaseModel):
    """Parsed attestation payload structure

    Attributes:
        version: Payload format version (currently 1)
        algorithm: Signature algorithm (0 = secp256k1)
        block_height: Block height when attestation was created
        data_provider: Data provider address (0x...)
        stream_id: Stream identifier
        action_id: Numeric action identifier
        arguments: List of decoded arguments passed to the action
        result: List of decoded rows from the query result
    """

    version: int
    algorithm: int
    block_height: int
    data_provider: str
    stream_id: str
    action_id: int
    arguments: list[Any] = []
    result: list[dict[str, Any]] = []


class FeeDistribution(TypedDict):
    recipient: str
    amount: str


class TransactionEvent(TypedDict):
    tx_id: str
    block_height: int
    method: str
    caller: str
    fee_amount: str
    fee_recipient: str | None
    metadata: str | None
    fee_distributions: list[FeeDistribution]


class TransactionFeeEntry(TypedDict):
    tx_id: str
    block_height: int
    method: str
    caller: str
    total_fee: str
    fee_recipient: str | None
    metadata: str | None
    distribution_sequence: int
    distribution_recipient: str | None
    distribution_amount: str | None


class TaxonomyDetails(TypedDict):
    stream_id: str
    child_streams: list["TaxonomyDefinition"]
    # start_date: int
    created_at: int
    # group_sequence: int


class TaxonomyDefinition(BaseModel):
    stream: StreamLocatorInput
    weight: int | float


# Order Book type definitions


class MarketInfo(TypedDict):
    """Market information"""
    hash: bytes
    settle_time: int
    settled: bool
    winning_outcome: bool | None
    settled_at: int | None
    max_spread: int
    min_order_size: int
    created_at: int
    creator: bytes


class MarketSummary(TypedDict):
    """Market summary for list results"""
    id: int
    hash: bytes
    settle_time: int
    settled: bool
    winning_outcome: bool | None
    max_spread: int
    min_order_size: int
    created_at: int


class MarketValidation(TypedDict):
    """Market collateral validation result"""
    valid_token_binaries: bool
    valid_collateral: bool
    total_true: int
    total_false: int
    vault_balance: str
    expected_collateral: str
    open_buys_value: int


class OrderBookEntry(TypedDict):
    """Single order book entry"""
    wallet_address: bytes
    price: int
    amount: int
    last_updated: int


class UserPosition(TypedDict):
    """User position in a market"""
    query_id: int
    outcome: bool
    price: int
    amount: int
    last_updated: int


class DepthLevel(TypedDict):
    """Market depth at price level"""
    price: int
    total_amount: int


class BestPrices(TypedDict):
    """Best bid/ask spread"""
    best_bid: int | None
    best_ask: int | None
    spread: int | None


class UserCollateral(TypedDict):
    """User's total collateral locked"""
    total_locked: str
    buy_orders_locked: str
    shares_value: str


class DistributionSummary(TypedDict):
    """Fee distribution summary"""
    distribution_id: int
    total_fees_distributed: str
    total_lp_count: int
    block_count: int
    distributed_at: int


class LPRewardDetail(TypedDict):
    """LP reward detail"""
    wallet_address: bytes
    reward_amount: str
    total_reward_percent: str


class RewardHistory(TypedDict):
    """Reward history entry"""
    distribution_id: int
    query_id: int
    reward_amount: str
    total_reward_percent: str
    distributed_at: int


# Cache-related type definitions


class StreamRecord(BaseModel):
    """Represents a single stream record matching client.py response format"""

    # best would make it a int, but now we're not breaking it
    # TODO: make it a int on a major version bump
    EventTime: str  # Unix timestamp (matches Go capitalization)
    Value: float

    def __getitem__(self, item):
        return getattr(self, item)


class CacheMetadata(BaseModel):
    """Cache metadata information"""

    hit: bool  # Whether cache was hit
    cache_height: int | None  # Block height when data was cached


class CacheAwareResponse(BaseModel, Generic[T]):
    """Wrapper for cache-aware responses"""

    data: T  # Original response data (List[StreamRecord], Dict, etc.)
    cache: CacheMetadata | None  # Cache metadata (if available)


class TNClient:
    def __init__(self, url: str, token: str):
        """
        Initialize a new client.

        Args:
            url (str): The RPC endpoint URL of the TRUF.NETWORK node.
            token (str): The user's private key for signing transactions.

        Note:
            This client supports cache-aware operations for query methods
            (get_records, get_index, get_first_record) when use_cache=True
            is provided. Cache functionality improves performance by
            leveraging cached data when available.
        """
        self.client = truf_sdk.NewClient(url, token)

    # --------------------------------------------------
    #               Private Helper Methods
    # --------------------------------------------------

    def _coalesce_str(self, val: str | None, default: str = "") -> str:
        """
        Helper to coalesce an optional string into a non-empty string.
        If val is None, return default; otherwise return val.
        """
        return val if val is not None else default

    def _coalesce_int(self, val: int | None, default: int = -1) -> int:
        """
        Helper to coalesce an optional integer into a sentinel value.

        Args:
            val: The optional integer value
            default: The default value to use if val is None (-1 by default)

        Returns:
            The non-None integer value
        """
        return val if val is not None else default

    def _go_slice_of_maps_to_list_of_dicts(self, go_slice: Any) -> list[dict[str, Any]]:
        """
        Helper to convert a Go slice of maps into a Python list of dicts.

        Args:
            go_slice: The Go slice object returned from the bindings

        Returns:
            A list of Python dictionaries
        """
        result = []
        for record in go_slice:
            result.append(dict(record.items()))
        return result

    def _records_handle_to_list_of_dicts(self, records: Any) -> list[dict[str, Any]]:
        """
        Specialized helper for `call_procedure` that converts the returned records
        object into a list of dicts by reflecting over its fields.
        """
        if records is None:
            return []

        result = []
        record_dict = {}
        for field in dir(records):
            # Skip private/dunder attributes
            if not field.startswith("_") and field not in (
                    "handle",
                    "incref",
                    "decref",
            ):
                try:
                    value = getattr(records, field)
                    record_dict[field] = value
                except AttributeError:
                    continue

        if record_dict:
            result.append(record_dict)
        return result

    def _map_cache_metadata(self, response) -> CacheMetadata:
        """
        Map cache metadata from Go binding response to Python CacheMetadata structure.
        Handles any mapping errors gracefully.
        """
        try:
            # Handle both object attribute access and dict-like access patterns
            if hasattr(response, "CacheHit"):
                cache_hit = response.CacheHit
            else:
                cache_hit = response.get("CacheHit", False)

            if cache_hit:
                # Try to get height from Height field
                height = None
                if hasattr(response, "Height") and hasattr(response.Height, "IsSet") and response.Height.IsSet:
                    height = response.Height.Value
                elif "Height" in response and response["Height"].get("IsSet", False):
                    height = response["Height"]["Value"]

                return CacheMetadata(
                    hit=cache_hit,
                    cache_height=height,
                )
            else:
                return CacheMetadata(hit=False, cache_height=None)
        except (KeyError, TypeError, AttributeError) as e:
            warnings.warn(f"Failed to map cache metadata from Go: {e}", UserWarning)
            return CacheMetadata(hit=False, cache_height=None)

    def _extract_records_data(
            self, response: truf_sdk.DataResponse
    ) -> list[StreamRecord]:
        """Extract and format records data from DataResponse."""
        data = []
        for record in response.Data:
            data.append(
                StreamRecord(EventTime=str(record.Date), Value=float(record.Value))
            )
        return data

    def _extract_single_record_data(
            self, response: truf_sdk.DataResponse
    ) -> StreamRecord | None:
        """Extract and format single record data from SingleRecordResponse."""
        records = list(response.Data)
        if len(records) > 0:
            # warn if it's returning more than one record
            if len(records) > 1:
                warnings.warn(
                    "Returning more than one record, returning the first one. This is a bug, please report it.",
                    UserWarning,
                )
            # return the first record
            record = records[0]
            return StreamRecord(EventTime=str(record.Date), Value=float(record.Value))
        return None

    def _format_records_response(
            self, response: truf_sdk.DataResponse
    ) -> CacheAwareResponse[list[StreamRecord]]:
        """
        Format DataResponse into cache-aware response for list-based methods (get_records, get_index).
        """
        cache_metadata = self._map_cache_metadata(response)
        data = self._extract_records_data(response)

        return CacheAwareResponse(data=data, cache=cache_metadata)

    def _format_single_record_response(
            self, response: truf_sdk.DataResponse
    ) -> CacheAwareResponse[StreamRecord | None]:
        """
        Format SingleRecordResponse into cache-aware response for single record methods (get_first_record).
        """
        cache_metadata = self._map_cache_metadata(response)
        data = self._extract_single_record_data(response)

        return CacheAwareResponse(data=data, cache=cache_metadata)

    def _format_legacy_response[T](self, response: CacheAwareResponse[T]) -> T:
        """
        Format legacy response to match the new cache-aware response format.
        """
        return response.data

    # --------------------------------------------------
    #               Public API Methods
    # --------------------------------------------------

    def deploy_stream(
            self,
            stream_id: str,
            stream_type: str = truf_sdk.StreamTypePrimitive,
            wait: bool = True,
    ) -> str:
        """
        Deploy a stream with the given stream ID and stream type.
        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash.
        """
        deploy_tx_hash = truf_sdk.DeployStream(self.client, stream_id, stream_type)
        if wait:
            self.wait_for_tx(deploy_tx_hash)
        return deploy_tx_hash

    def insert_record(
            self, stream_id: str, record: dict[str, float | int], wait: bool = True
    ) -> str:
        """
        Insert a single record into a stream with the given stream ID.
        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash.

        Record is expected to have:
          - "date": int (UNIX timestamp)
          - "value": float or int

        Note:
            For inserting multiple records rapidly, use `batch_insert_records`
            instead to avoid potential nonce errors.
        """
        go_input = truf_sdk.NewInsertRecordInput(
            self.client, stream_id, record["date"], record["value"]
        )
        insert_tx_hash = truf_sdk.InsertRecord(self.client, go_input)

        if wait:
            truf_sdk.WaitForTx(self.client, insert_tx_hash)

        return insert_tx_hash

    def insert_records(
            self,
            stream_id: str,
            records: list[dict[str, float | int]],
            wait: bool = True,
    ) -> str:
        """
        Insert records into a stream with the given stream ID.
        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash.

        Each record is expected to have:
          - "date": int (UNIX timestamp)
          - "value": float or int

        Note:
            For inserting multiple records rapidly, use `batch_insert_records`
            instead to avoid potential nonce errors.
        """

        input_list = []
        for _, record in enumerate(records):
            # Create InsertRecordInput struct
            go_input = truf_sdk.NewInsertRecordInput(
                self.client, stream_id, record["date"], record["value"]
            )
            input_list.append(go_input)

        go_input_list = truf_sdk.Slice_s1_types_InsertRecordInput(input_list)
        insert_tx_hash = truf_sdk.InsertRecords(self.client, go_input_list)

        if wait:
            truf_sdk.WaitForTx(self.client, insert_tx_hash)

        return insert_tx_hash

    def batch_insert_records(
            self, batches: list[RecordBatch], wait: bool = True
    ) -> str:
        """
        Insert multiple batches of records into different streams in a single transaction.
        This is the most efficient way to insert large amounts of data.

        Each batch should be a dictionary conforming to the RecordBatch TypedDict:
            - stream_id: str
            - inputs: List[Record] where each record has:
                - date: int (UNIX timestamp)
                - value: float or int

        Parameters:
            - batches : A list of batch objects.
            - wait : Whether to wait for the transaction to be confirmed.

        Returns:
            A single transaction hash for all inserted records.

        Raises:
            ValueError: If the total batch size is too large for the network to process.
        """
        all_inputs = []

        # Collect all records from all batches into a single list
        for batch in batches:
            stream_id = batch["stream_id"]
            inputs = batch["inputs"]

            for record in inputs:
                # Create InsertRecordInput struct for each record
                go_input = truf_sdk.NewInsertRecordInput(
                    self.client, stream_id, record["date"], record["value"]
                )
                all_inputs.append(go_input)

        # Convert to Go slice and make a single call to InsertRecords
        go_input_list = truf_sdk.Slice_s1_types_InsertRecordInput(all_inputs)

        try:
            insert_tx_hash = truf_sdk.InsertRecords(self.client, go_input_list)
        except Exception as e:
            error_str = str(e)
            if "failed to estimate price" in error_str:
                raise ValueError(
                    "Request too large: The batch size exceeds the maximum allowed size"
                ) from e
            raise e

        if wait:
            truf_sdk.WaitForTx(self.client, insert_tx_hash)

        return insert_tx_hash

    @overload
    def get_records(
            self,
            stream_id: str,
            data_provider: str | None = None,
            date_from: int | None = None,
            date_to: int | None = None,
            frozen_at: int | None = None,
            base_date: int | None = None,
            prefix: str | None = None,
            *,
            use_cache: bool,
    ) -> CacheAwareResponse[list[StreamRecord]]: ...

    @overload
    def get_records(
            self,
            stream_id: str,
            data_provider: str | None = None,
            date_from: int | None = None,
            date_to: int | None = None,
            frozen_at: int | None = None,
            base_date: int | None = None,
            prefix: str | None = None,
    ) -> list[StreamRecord]: ...

    def get_records(
            self,
            stream_id: str,
            data_provider: str | None = None,
            date_from: int | None = None,
            date_to: int | None = None,
            frozen_at: int | None = None,
            base_date: int | None = None,
            prefix: str | None = None,
            *,
            use_cache: bool | None = _UNSET,
    ) -> list[StreamRecord] | CacheAwareResponse[list[StreamRecord]]:
        """
        Get records from a stream with the given stream ID (cache-aware signature).
        Returns a list of records or CacheAwareResponse based on use_cache flag.

        Parameters:
            - stream_id : str
            - use_cache : bool
            - data_provider : (hex string)
            - date_from : Optional[int] (UNIX)
            - date_to : Optional[int] (UNIX)
            - frozen_at : Optional[int] (UNIX)
            - base_date : Optional[int] (UNIX)
            - prefix : Optional[str]

        Returns:
            A list of dictionaries or CacheAwareResponse, depending on use_cache flag.
            Note: Keys from the Go layer are capitalized (e.g., `EventTime`, `Value`).
        """
        data_provider = self._coalesce_str(data_provider)
        date_from = self._coalesce_int(date_from)
        date_to = self._coalesce_int(date_to)
        frozen_at = self._coalesce_int(frozen_at)
        base_date = self._coalesce_int(base_date)
        prefix = self._coalesce_str(prefix)

        input = truf_sdk.NewGetRecordInput(
            self.client,
            stream_id,
            data_provider,
            date_from,
            date_to,
            frozen_at,
            base_date,
            prefix,
            use_cache,
        )
        go_response = truf_sdk.GetRecords(self.client, input)
        response = self._format_records_response(go_response)

        if use_cache is _UNSET:
            warnings.warn(
                "get_records: Omitting 'use_cache' is deprecated (legacy response) and will be removed in the next major version. "
                "Pass use_cache=False or use_cache=True to receive the new response formats.",
                DeprecationWarning,
                stacklevel=2,
            )
            return response.data
        else:
            return response

    def get_type(self, stream_id: str, data_provider: str | None = None) -> str:
        """
        Get the type of a stream with the given stream ID.
        Returns the type of the stream.
        """
        data_provider = self._coalesce_str(data_provider)
        return truf_sdk.GetType(self.client, stream_id, data_provider)

    def wait_for_tx(self, tx_hash: str) -> None:
        """
        Wait for a transaction to be confirmed given its hash.

        Raises:
            Exception: If the transaction fails to execute on-chain (e.g., due to
                       a permission error, invalid input, or other logic error).
        """
        truf_sdk.WaitForTx(self.client, tx_hash)

    def get_current_account(self) -> str:
        """
        Get the current account address associated with this client.

        Returns:
            str: The hex-encoded address of the current account
        """
        return truf_sdk.GetCurrentAccount(self.client)

    def destroy_stream(self, stream_id: str, wait: bool = True) -> str:
        """
        Destroy a stream with the given stream ID.
        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash.
        """
        destroy_tx_hash = truf_sdk.DestroyStream(self.client, stream_id)
        if wait:
            truf_sdk.WaitForTx(self.client, destroy_tx_hash)
        return destroy_tx_hash

    @overload
    def get_first_record(
            self,
            stream_id: str,
            data_provider: str | None = None,
            after_date: int | None = None,
            frozen_at: int | None = None,
            *,
            use_cache: bool,
    ) -> CacheAwareResponse[StreamRecord | None]: ...

    @overload
    def get_first_record(
            self,
            stream_id: str,
            data_provider: str | None = None,
            after_date: int | None = None,
            frozen_at: int | None = None,
    ) -> StreamRecord | None: ...

    def get_first_record(
            self,
            stream_id: str,
            data_provider: str | None = None,
            after_date: int | None = None,
            frozen_at: int | None = None,
            *,
            use_cache: bool | None = _UNSET,
    ) -> StreamRecord | None | CacheAwareResponse[StreamRecord | None]:
        """Get the first record of a stream after a given date."""
        data_provider = self._coalesce_str(data_provider)
        after_date = self._coalesce_int(after_date)
        frozen_at = self._coalesce_int(frozen_at)

        input = truf_sdk.NewGetFirstRecordInput(
            self.client, stream_id, data_provider, after_date, frozen_at, use_cache
        )
        go_response = truf_sdk.GetFirstRecord(self.client, input)
        response = self._format_single_record_response(go_response)

        if use_cache is _UNSET:
            warnings.warn(
                "get_first_record: Omitting 'use_cache' is deprecated (legacy response) and will be removed in the next major version. "
                "Pass use_cache=False or use_cache=True to receive the new response formats.",
                DeprecationWarning,
                stacklevel=2,
            )
            return response.data
        else:
            return response

    @overload
    def get_index(
            self,
            stream_id: str,
            data_provider: str | None = None,
            date_from: int | None = None,
            date_to: int | None = None,
            frozen_at: int | None = None,
            base_date: int | None = None,
            prefix: str | None = None,
            *,
            use_cache: bool,
    ) -> CacheAwareResponse[list[StreamRecord]]: ...

    @overload
    def get_index(
            self,
            stream_id: str,
            data_provider: str | None = None,
            date_from: int | None = None,
            date_to: int | None = None,
            frozen_at: int | None = None,
            base_date: int | None = None,
            prefix: str | None = None,
    ) -> list[StreamRecord]: ...

    def get_index(
            self,
            stream_id: str,
            data_provider: str | None = None,
            date_from: int | None = None,
            date_to: int | None = None,
            frozen_at: int | None = None,
            base_date: int | None = None,
            prefix: str | None = None,
            *,
            use_cache: bool | None = _UNSET,
    ) -> list[StreamRecord] | CacheAwareResponse[list[StreamRecord]]:
        """Get index from a stream with the given stream ID."""
        data_provider = self._coalesce_str(data_provider)
        date_from = self._coalesce_int(date_from)
        date_to = self._coalesce_int(date_to)
        frozen_at = self._coalesce_int(frozen_at)
        base_date = self._coalesce_int(base_date)
        prefix = self._coalesce_str(prefix)

        input = truf_sdk.NewGetRecordInput(
            self.client,
            stream_id,
            data_provider,
            date_from,
            date_to,
            frozen_at,
            base_date,
            prefix,
            use_cache,
        )
        go_response = truf_sdk.GetIndex(self.client, input)
        response = self._format_records_response(go_response)

        if use_cache is _UNSET:
            warnings.warn(
                "get_index: Omitting 'use_cache' is deprecated (legacy response) and will be removed in the next major version. "
                "Pass use_cache=False or use_cache=True to receive the new response formats.",
                DeprecationWarning,
                stacklevel=2,
            )
            return response.data
        else:
            return response

    def list_streams(
            self,
            limit: int | None = None,
            offset: int | None = None,
            data_provider: str | None = None,
            order_by: str | None = None,
            block_height: int | None = 0,
    ) -> list[dict[str, Any]]:
        """
        List all streams associated with client account
        """
        limit = self._coalesce_int(limit)
        offset = self._coalesce_int(offset)
        data_provider = self._coalesce_str(data_provider)
        order_by = self._coalesce_str(order_by)

        input = truf_sdk.NewListStreamsInput(
            limit, offset, data_provider, order_by, block_height
        )
        go_slice_of_maps = truf_sdk.ListStreams(self.client, input)

        return self._go_slice_of_maps_to_list_of_dicts(go_slice_of_maps)

    def set_taxonomy(
            self,
            stream_id: str,
            taxonomies: list[TaxonomyDefinition],
            start_date: int | None = None,
            wait: bool = True,
    ) -> str:
        """
        Set Taxonomy will define taxonomy of a composed stream.
        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash.

        Parameters:
            - stream_id: The composed stream to define.
            - taxonomies: A list of TaxonomyDefinition objects.
            - start_date: Optional UNIX timestamp for when the taxonomy becomes effective.
            - group_sequence: Optional integer for ordering taxonomies.
            - wait: If True, waits for the transaction to be confirmed.
        """
        start_date = self._coalesce_int(start_date)

        taxonomy_items = []
        for taxonomy in taxonomies:
            data_provider = self._coalesce_str(taxonomy.stream.get("data_provider"))
            taxonomy_item = truf_sdk.NewTaxonomyItemInput(
                self.client,
                data_provider,
                taxonomy.stream["stream_id"],
                taxonomy.weight,
            )
            taxonomy_items.append(taxonomy_item)

        taxonomy_items_go = truf_sdk.Slice_s1_types_TaxonomyItem(taxonomy_items)
        input = truf_sdk.NewTaxonomyInput(
            self.client, stream_id, taxonomy_items_go, start_date, 0
        )
        tx_hash = truf_sdk.SetTaxonomy(self.client, input)

        if wait:
            truf_sdk.WaitForTx(self.client, tx_hash)

        return tx_hash

    def describe_taxonomy(
            self, stream_id: str, latest_version: bool = True
    ) -> TaxonomyDetails | None:
        """
        Get taxonomy structure of a composed stream

        If latest_version is true, then it will return only the latest version of the taxonomy

        Parameters:
            - stream_id : str
            - latest_version : bool
        """
        result = truf_sdk.DescribeTaxonomy(self.client, stream_id, latest_version)
        taxonomy_data = dict(result.items())

        if not taxonomy_data:
            return None

        child_streams_json = taxonomy_data.get("child_streams")
        raw_taxonomy_list = json.loads(child_streams_json) if child_streams_json else []

        processed_taxonomies = []
        for item in raw_taxonomy_list:
            processed_taxonomies.append(
                TaxonomyDefinition(
                    stream={
                        "stream_id": item.get("stream_id"),
                        "data_provider": item.get("data_provider"),
                    },
                    weight=float(item["weight"]),
                )
            )

        return TaxonomyDetails(
            stream_id=taxonomy_data.get("stream_id") or "",
            child_streams=processed_taxonomies,
            created_at=int(taxonomy_data.get("created_at", 0)),
        )

    def allow_compose_stream(self, stream_id: str, wait: bool = True) -> str:
        """
        Allows streams to use this stream as child, if composing is private.

        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash.
        """
        tx_hash = truf_sdk.AllowComposeStream(self.client, stream_id)

        if wait:
            truf_sdk.WaitForTx(self.client, tx_hash)

        return tx_hash

    def disable_compose_stream(self, stream_id: str, wait: bool = True) -> str:
        """
        Disable streams from using this stream as child.

        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash.
        """
        tx_hash = truf_sdk.DisableComposeStream(self.client, stream_id)

        if wait:
            truf_sdk.WaitForTx(self.client, tx_hash)

        return tx_hash

    def allow_read_wallet(self, stream_id: str, wallet: str, wait: bool = True) -> str:
        """
        Allows a wallet to read the stream, if reading is private

        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash.

        Parameters:
            - stream_id : str
            - wallet : str (Ethereum Address)
        """

        input = truf_sdk.NewReadWalletInput(self.client, stream_id, wallet)
        tx_hash = truf_sdk.AllowReadWallet(self.client, input)

        if wait:
            truf_sdk.WaitForTx(self.client, tx_hash)

        return tx_hash

    def disable_read_wallet(
            self, stream_id: str, wallet: str, wait: bool = True
    ) -> str:
        """
        Disables a wallet from reading the stream

        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash.

        Parameters:
            - stream_id : str
            - wallet : str (Ethereum Address)
        """

        input = truf_sdk.NewReadWalletInput(self.client, stream_id, wallet)
        tx_hash = truf_sdk.DisableReadWallet(self.client, input)

        if wait:
            truf_sdk.WaitForTx(self.client, tx_hash)

        return tx_hash

    def set_read_visibility(
            self, stream_id: str, visibilityVal: str, wait: bool = True
    ) -> str:
        """
        Sets the read visibility of the stream -- Private or Public

        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash.

        Parameters:
            - stream_id : str
            - visibility : str ("public" or "private")
        """
        visibility = 0
        if visibilityVal == "private":
            visibility = 1

        input = truf_sdk.NewVisibilityInput(self.client, stream_id, visibility)
        tx_hash = truf_sdk.SetReadVisibility(self.client, input)

        if wait:
            truf_sdk.WaitForTx(self.client, tx_hash)

        return tx_hash

    def get_read_visibility(self, stream_id: str) -> str:
        """
        Gets the read visibility of the stream -- Private or Public
        """

        visibility = truf_sdk.GetReadVisibility(self.client, stream_id)

        return "public" if visibility == truf_sdk.VisibilityPublic else "private"

    def set_compose_visibility(
            self, stream_id: str, visibilityVal: int | str, wait: bool = True
    ) -> str:
        """
        Sets the compose visibility of the stream -- Private or Public

        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash.

        Parameters:
            - stream_id : str
            - visibility : str ("public" or "private")
        """

        visibility = 0
        if visibilityVal == "private":
            visibility = 1

        input = truf_sdk.NewVisibilityInput(self.client, stream_id, visibility)
        tx_hash = truf_sdk.SetComposeVisibility(self.client, input)

        if wait:
            truf_sdk.WaitForTx(self.client, tx_hash)

        return tx_hash

    def get_compose_visibility(self, stream_id: str) -> str:
        """
        Gets the compose visibility of the stream -- Private or Public
        """

        visibility = truf_sdk.GetComposeVisibility(self.client, stream_id)

        return "public" if visibility == truf_sdk.VisibilityPublic else "private"

    def get_allowed_read_wallets(self, stream_id: str) -> list[str]:
        """
        Gets the wallets allowed to read the stream, if read stream is private
        """

        wallets = truf_sdk.GetAllowedReadWallets(self.client, stream_id)
        return list(wallets)

    def get_allowed_compose_streams(self, stream_id: str) -> list[str]:
        """
        Gets the streams allowed to compose this stream, if compose stream is private
        """

        streams = truf_sdk.GetAllowedComposeStreams(self.client, stream_id)
        return list(streams)

    def batch_deploy_streams(
            self,
            definitions: list[StreamDefinitionInput],
            wait: bool = True,
    ) -> str:
        """
        Deploy multiple streams (primitive and composed).
        Each definition should be a dictionary containing:
            - stream_id: str
            - stream_type: str ("primitive" or "composed")

        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash of the batch operation.
        """
        # Build a list of Go StreamDefinition objects
        go_definitions = []
        for def_input in definitions:
            go_def = truf_sdk.NewStreamDefinitionForBinding(
                def_input["stream_id"], def_input["stream_type"]
            )
            go_definitions.append(go_def)

        # Convert to Go slice type
        final_go_definitions = truf_sdk.Slice_s1_types_StreamDefinition(go_definitions)

        tx_hash = truf_sdk.BatchDeployStreams(self.client, final_go_definitions)
        if wait:
            truf_sdk.WaitForTx(self.client, tx_hash)
        return tx_hash

    def batch_stream_exists(
            self,
            locators: list[StreamLocatorInput],
    ) -> list[StreamExistsResult]:
        """
        Check for the existence of multiple streams.
        Each locator should be a dictionary containing:
            - stream_id: str
            - data_provider: str (hex string)

        Returns a list of results, each indicating if a stream exists.
        """
        py_list_of_go_locators = []
        for loc_input in locators:
            go_loc_handle = truf_sdk.NewStreamLocatorForBinding(
                loc_input["stream_id"], loc_input["data_provider"]
            )
            py_list_of_go_locators.append(go_loc_handle)

        final_go_locators = truf_sdk.Slice_s1_types_StreamLocator(
            py_list_of_go_locators
        )

        go_results = truf_sdk.BatchStreamExists(self.client, final_go_locators)

        results = []
        for go_map in go_results:
            item = dict(go_map.items())  # Convert Go map to Python dict
            results.append(
                {
                    "stream_id": item["stream_id"],
                    "data_provider": item["data_provider"],
                    "exists": item["exists"].lower()
                              == "true",  # Convert string "true"/"false" to bool
                }
            )
        return results

    def batch_filter_streams_by_existence(
            self,
            locators: list[StreamLocatorInput],
            return_existing: bool,
    ) -> list[
        StreamLocatorInput
    ]:  # Returns List[StreamLocatorInput] as they are just locators
        """
        Filters a list of streams based on their existence in the database.
        Each locator should be a dictionary containing:
            - stream_id: str
            - data_provider: str (hex string)

        Parameters:
            - locators: List of stream locators to filter.
            - return_existing: bool - If True, returns streams that exist. If False, returns streams that do not exist.

        Returns a list of stream locators that match the filter criteria.
        """
        py_list_of_go_locators = []
        for loc_input in locators:
            go_loc_handle = truf_sdk.NewStreamLocatorForBinding(
                loc_input["stream_id"], loc_input["data_provider"]
            )
            py_list_of_go_locators.append(go_loc_handle)

        final_go_locators = truf_sdk.Slice_s1_types_StreamLocator(
            py_list_of_go_locators
        )

        go_results = truf_sdk.BatchFilterStreamsByExistence(
            self.client, final_go_locators, return_existing
        )

        results = []
        for go_map in go_results:
            item = dict(go_map.items())  # Convert Go map to Python dict
            results.append(
                {
                    "stream_id": item["stream_id"],
                    "data_provider": item["data_provider"],
                }
            )
        return results

    def call_procedure(self, procedure: str, args: list[str | None]) -> dict[str, Any]:
        """Call a **read-only** stored procedure on the gateway.

        Parameters
        ----------
        procedure : str
            Name of the stored procedure to invoke.
        args : List[Any]
            Positional arguments expected by the procedure. Use ``None`` for SQL
            NULL / optional parameters you want to skip.

        Returns
        -------
        Dict[str, Any]
            A mapping with two keys:
                • ``column_names`` – list of column names returned
                • ``values`` – 2-D list with the result rows
        """
        # Convert Python list to Go slice wrapper
        str_args = ["" if a is None else str(a) for a in args]
        go_slice = go.Slice_string(str_args)
        result_json = truf_sdk.CallProcedureStrings(self.client, procedure, go_slice)
        return json.loads(result_json)

    # --------------------------------------------------
    #               Role Management Methods
    # --------------------------------------------------

    def grant_role(
            self,
            owner: str,
            role_name: str,
            wallets: list[str],
            wait: bool = True,
    ) -> str:
        """
        Grants a role to a list of wallets.

        Permissions:
        - Only the role owner or members of the designated manager role can execute this.

        Parameters:
            - owner: The owner of the role (e.g., 'system' or an Ethereum address).
            - role_name: The name of the role.
            - wallets: A list of wallet addresses to grant the role to.
            - wait: If True, waits for the transaction to be confirmed.

        Returns:
            The transaction hash.
        """
        go_wallets = go.Slice_string(wallets)
        tx_hash = truf_sdk.GrantRole(self.client, owner, role_name, go_wallets)

        if wait:
            self.wait_for_tx(tx_hash)

        return tx_hash

    def revoke_role(
            self,
            owner: str,
            role_name: str,
            wallets: list[str],
            wait: bool = True,
    ) -> str:
        """
        Revokes a role from a list of wallets.

        Permissions:
        - Only the role owner or members of the designated manager role can execute this.

        Parameters:
            - owner: The owner of the role.
            - role_name: The name of the role.
            - wallets: A list of wallet addresses to revoke the role from.
            - wait: If True, waits for the transaction to be confirmed.

        Returns:
            The transaction hash.
        """
        go_wallets = go.Slice_string(wallets)
        tx_hash = truf_sdk.RevokeRole(self.client, owner, role_name, go_wallets)

        if wait:
            self.wait_for_tx(tx_hash)

        return tx_hash

    def are_members_of(
            self,
            owner: str,
            role_name: str,
            wallets: list[str],
    ) -> list[RoleMembershipStatus]:
        """
        Checks if a list of wallets are members of a specific role.

        This is a public view action and requires no special permissions.

        Parameters:
            - owner: The owner of the role.
            - role_name: The name of the role.
            - wallets: A list of wallet addresses to check.

        Returns:
            A list of objects, each representing the membership status of a wallet.
        """
        go_wallets = go.Slice_string(wallets)
        go_results = truf_sdk.AreMembersOf(self.client, owner, role_name, go_wallets)

        results: list[RoleMembershipStatus] = []
        for go_map in go_results:
            item = dict(go_map.items())
            # The keys from Go are capitalized struct fields: `Wallet`, `IsMember`.
            # We map them to snake_case Python dict keys and correct types.
            wallet_address = item.get("Wallet", "")
            is_member_str = str(item.get("IsMember", "false")).lower()

            results.append(
                {
                    "wallet": wallet_address,
                    "is_member": is_member_str == "true",
                }
            )
        return results

    def list_role_members(
            self,
            owner: str,
            role_name: str,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[RoleMember]:
        """
        Lists the members of a role with optional pagination.

        Parameters:
            - owner: The owner namespace of the role (e.g., 'system').
            - role_name: The role to list members for.
            - limit: Maximum number of results to return. Defaults to SDK / DB default if None.
            - offset: Number of records to skip. Defaults to 0 if None.

        Returns:
            A list of RoleMember dictionaries.
        """
        # Coalesce optional ints into sentinel values expected by the Go layer.
        limit_val = self._coalesce_int(limit, 0) if limit is not None else 0
        offset_val = self._coalesce_int(offset, 0)

        go_results = truf_sdk.ListRoleMembers(
            self.client,
            owner,
            role_name,
            limit_val,
            offset_val,
        )

        members: list[RoleMember] = []
        for go_map in go_results:
            item = dict(go_map.items())
            wallet = item.get("Wallet", "")
            granted_at_str = item.get("GrantedAt", "0")
            granted_by = item.get("GrantedBy", "")

            try:
                granted_at = int(granted_at_str)
            except ValueError:
                granted_at = 0

            members.append(
                {
                    "wallet": wallet,
                    "granted_at": granted_at,
                    "granted_by": granted_by,
                }
            )

        return members

    # ==========================================
    #          ATTESTATION METHODS
    # ==========================================

    def request_attestation(
            self,
            data_provider: str,
            stream_id: str,
            action_name: str,
            args: list[Any],
            encrypt_sig: bool = False,
            max_fee: str = "100000000000000000000",
            wait: bool = True,
    ) -> str:
        """
        Request a signed attestation for query results.

        Args:
            data_provider: 0x-prefixed hex address (42 characters)
            stream_id: Stream ID (32 characters)
            action_name: Action to attest (e.g., "get_record")
            args: Action arguments
            encrypt_sig: Whether to encrypt signature (must be False in MVP)
            max_fee: Maximum fee willing to pay as string (NUMERIC(78,0), e.g., "100000000000000000000" for 100 TRUF)
            wait: If True, wait for transaction confirmation

        Returns:
            Transaction ID (request_tx_id)

        Example:
            >>> tx_id = client.request_attestation(
            ...     data_provider="0x4710a8d8f0d845da110086812a32de6d90d7ff5c",
            ...     stream_id="stai0000000000000000000000000000",
            ...     action_name="get_record",
            ...     args=[data_provider, stream_id, from_time, to_time, None, False],
            ...     max_fee="100000000000000000000",
            ... )
        """
        # Validate inputs
        if len(data_provider) != 42:
            raise ValueError(
                f"data_provider must be 42 characters (0x + 40 hex), got {len(data_provider)}"
            )

        if not data_provider.startswith("0x"):
            raise ValueError("data_provider must start with '0x'")

        if len(stream_id) != 32:
            raise ValueError(f"stream_id must be 32 characters, got {len(stream_id)}")

        if not action_name:
            raise ValueError("action_name cannot be empty")

        if encrypt_sig:
            raise ValueError(
                "Signature encryption is not supported in MVP (encrypt_sig must be False)"
            )

        # Validate max_fee is a valid non-negative numeric string
        if max_fee:
            if not max_fee.isdigit():
                raise ValueError(f"max_fee must be a numeric string, got: {max_fee}")
            if int(max_fee) < 0:
                raise ValueError(f"max_fee must be non-negative, got {max_fee}")

        # Convert args to JSON string for passing to Go layer
        args_json = json.dumps(args)

        # Request attestation
        request_tx_id = truf_sdk.RequestAttestation(
            self.client,
            data_provider,
            stream_id,
            action_name,
            args_json,
            encrypt_sig,
            max_fee,
        )

        if wait:
            truf_sdk.WaitForTx(self.client, request_tx_id)

        return request_tx_id

    def get_signed_attestation(self, request_tx_id: str) -> bytes:
        """
        Retrieve the signed attestation payload.

        Args:
            request_tx_id: Transaction ID from request_attestation

        Returns:
            Signed attestation payload (bytes)

        Note:
            This may return an empty or incomplete payload if the attestation
            has not been signed by the validator yet. Poll this endpoint
            until you receive a non-empty payload.

        Example:
            >>> payload = client.get_signed_attestation(request_tx_id)
            >>> print(f"Payload size: {len(payload)} bytes")
        """
        if not request_tx_id:
            raise ValueError("request_tx_id cannot be empty")

        go_payload = truf_sdk.GetSignedAttestation(self.client, request_tx_id)

        # Convert Go bytes to Python bytes
        if hasattr(go_payload, "__iter__"):
            return bytes(go_payload)

        return go_payload

    def list_attestations(
            self,
            requester: bytes | None = None,
            limit: int | None = None,
            offset: int | None = None,
            order_by: str | None = None,
    ) -> list[AttestationMetadata]:
        """
        List attestation metadata with optional filtering.

        Args:
            requester: Optional filter by requester address (20 bytes)
            limit: Maximum results to return (default/max: 5000)
            offset: Pagination offset (default: 0)
            order_by: Sort order, one of:
                - "created_height asc" (default)
                - "created_height desc"
                - "signed_height asc"
                - "signed_height desc"

        Returns:
            List of attestation metadata

        Example:
            >>> # Get my recent attestations
            >>> my_address = bytes.fromhex(client.get_current_account()[2:])
            >>> attestations = client.list_attestations(
            ...     requester=my_address,
            ...     limit=10,
            ...     order_by="created_height desc",
            ... )
            >>> for att in attestations:
            ...     print(f"TX: {att['request_tx_id']}, Height: {att['created_height']}")
        """
        # Validate inputs
        if requester is not None and len(requester) > 20:
            raise ValueError(f"requester must be at most 20 bytes, got {len(requester)}")

        if limit is not None and (limit <= 0 or limit > 5000):
            raise ValueError(f"limit must be between 1 and 5000, got {limit}")

        if offset is not None and offset < 0:
            raise ValueError(f"offset must be non-negative, got {offset}")

        # Validate order_by
        valid_order_by = [
            "created_height asc",
            "created_height desc",
            "signed_height asc",
            "signed_height desc",
        ]
        if order_by is not None and order_by.lower() not in valid_order_by:
            raise ValueError(f"order_by must be one of: {', '.join(valid_order_by)}")

        # Normalize order_by to lowercase for consistent Go API calls
        if order_by is not None:
            order_by = order_by.lower()

        # Convert None to sentinel values
        requester_bytes = go.Slice_byte(list(requester)) if requester else go.Slice_byte([])
        limit_val = self._coalesce_int(limit, -1)
        offset_val = self._coalesce_int(offset, -1)
        order_by_val = self._coalesce_str(order_by)

        # Call Go function
        go_results = truf_sdk.ListAttestations(
            self.client,
            requester_bytes,
            limit_val,
            offset_val,
            order_by_val,
        )

        # Convert to Python dicts
        results: list[AttestationMetadata] = []
        for go_map in go_results:
            item = dict(go_map.items())

            # Parse signed_height (handle null)
            signed_height_str = item.get("SignedHeight", "")
            signed_height: int | None = None
            if signed_height_str and signed_height_str != "null" and signed_height_str != "":
                try:
                    signed_height = int(signed_height_str)
                except ValueError:
                    pass

            # Parse with error handling for malformed data
            try:
                attestation_hash = (
                    bytes.fromhex(item.get("AttestationHash", ""))
                    if item.get("AttestationHash")
                    else b""
                )
                requester = (
                    bytes.fromhex(item.get("Requester", ""))
                    if item.get("Requester")
                    else b""
                )
                created_height = int(item.get("CreatedHeight") or "0")
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Failed to parse attestation metadata: {e}. "
                    f"AttestationHash: {item.get('AttestationHash')}, "
                    f"Requester: {item.get('Requester')}, "
                    f"CreatedHeight: {item.get('CreatedHeight')}"
                ) from e

            results.append(
                {
                    "request_tx_id": item.get("RequestTxID", ""),
                    "attestation_hash": attestation_hash,
                    "requester": requester,
                    "created_height": created_height,
                    "signed_height": signed_height,
                    "encrypt_sig": item.get("EncryptSig", "false").lower() == "true",
                }
            )

        return results

    def parse_attestation_payload(self, payload: bytes) -> ParsedAttestationPayload:
        """
        Parse a canonical attestation payload (without signature).

        Args:
            payload: The canonical attestation payload bytes (signature already removed)

        Returns:
            ParsedAttestationPayload: Parsed payload with all fields decoded

        Raises:
            ValueError: If payload is malformed or cannot be parsed
            Exception: If Go binding call fails

        Example:
            ```python
            # Get signed attestation
            signed = client.get_signed_attestation(tx_id)

            # Option 1 (Recommended): Verify signature first
            verification = client.verify_attestation_signature(signed)
            parsed = client.parse_attestation_payload(verification['canonical_payload'])

            # Option 2: If signature already verified elsewhere, extract manually
            # canonical_payload = signed[:-65]
            # parsed = client.parse_attestation_payload(canonical_payload)

            print(f"Data Provider: {parsed.data_provider}")
            print(f"Stream ID: {parsed.stream_id}")
            print(f"Block Height: {parsed.block_height}")
            print(f"Results: {len(parsed.result)} rows")

            for i, row in enumerate(parsed.result):
                print(f"  Row {i+1}: {row['values']}")
            ```
        """
        if not isinstance(payload, bytes):
            raise ValueError(f"Payload must be bytes, got {type(payload).__name__}")

        if len(payload) == 0:
            raise ValueError("Payload cannot be empty")

        # Convert Python bytes to Go byte slice
        payload_go = go.Slice_byte(list(payload))

        # Call Go binding
        try:
            json_str = truf_sdk.ParseAttestationPayload(payload_go)
        except Exception as e:
            raise Exception(f"Failed to parse attestation payload: {e}") from e

        # Parse JSON response
        parsed_dict = json.loads(json_str)

        # Convert field names from Go (camelCase) to Python (snake_case)
        python_dict = {
            "version": parsed_dict.get("version", 0),
            "algorithm": parsed_dict.get("algorithm", 0),
            "block_height": parsed_dict.get("blockHeight", 0),
            "data_provider": parsed_dict.get("dataProvider", ""),
            "stream_id": parsed_dict.get("streamId", ""),
            "action_id": parsed_dict.get("actionId", 0),
            "arguments": parsed_dict.get("arguments", []),
            "result": parsed_dict.get("result", []),
        }

        # Convert to Pydantic model
        return ParsedAttestationPayload(**python_dict)

    def verify_attestation_signature(
            self, full_payload: bytes
    ) -> AttestationSignatureVerification:
        """
        Verify an attestation signature and extract validator address.

        This method:
        1. Validates the payload has minimum length (66 bytes)
        2. Extracts the canonical payload and signature (last 65 bytes)
        3. Recovers the validator's public key from the signature
        4. Derives the Ethereum address from the public key

        Args:
            full_payload: The complete attestation payload including signature

        Returns:
            AttestationSignatureVerification: Contains validator address, canonical payload, and signature

        Raises:
            ValueError: If payload is too short or malformed
            Exception: If signature verification fails

        Example:
            ```python
            # Get signed attestation
            signed = client.get_signed_attestation(tx_id)

            # Verify signature and get validator address
            verification = client.verify_attestation_signature(signed)

            print(f"Validator Address: {verification['validator_address']}")
            print("This address should be used in your smart contract's verify() function")

            # Now parse the canonical payload
            parsed = client.parse_attestation_payload(verification['canonical_payload'])
            ```
        """
        if not isinstance(full_payload, bytes):
            raise ValueError(
                f"Payload must be bytes, got {type(full_payload).__name__}"
            )

        if len(full_payload) < 66:
            raise ValueError(
                f"Payload too short: {len(full_payload)} bytes, expected at least 66 "
                "(minimum 1 byte data + 65 bytes signature)"
            )

        # Convert Python bytes to Go byte slice
        payload_go = go.Slice_byte(list(full_payload))

        # Call Go binding to verify and extract validator address
        try:
            validator_address = truf_sdk.VerifyAttestationSignature(payload_go)
        except Exception as e:
            raise Exception(f"Failed to verify attestation signature: {e}") from e

        # Extract canonical payload and signature for return
        canonical_payload = full_payload[:-65]
        signature = full_payload[-65:]

        return {
            "validator_address": validator_address,
            "canonical_payload": canonical_payload,
            "signature": signature,
        }

    # ==========================================
    #     TRANSACTION LEDGER METHODS
    # ==========================================

    def get_transaction_event(self, tx_id: str) -> TransactionEvent:
        """
        Retrieve detailed transaction information by transaction hash.

        Args:
            tx_id: Transaction hash (with or without 0x prefix)

        Returns:
            TransactionEvent with transaction details and fee distributions

        Raises:
            ValueError: If tx_id is empty
            Exception: If transaction not found or query fails

        Example:
            >>> tx_event = client.get_transaction_event("0xabcdef...")
            >>> print(f"Method: {tx_event['method']}")
            >>> print(f"Fee: {tx_event['fee_amount']} wei")
            >>> for dist in tx_event['fee_distributions']:
            ...     print(f"  → {dist['recipient']}: {dist['amount']}")
        """
        # Validate input
        if not tx_id or tx_id.strip() == "":
            raise ValueError("tx_id is required and cannot be empty")

        # Call Go binding
        go_result = truf_sdk.GetTransactionEvent(self.client, tx_id)

        # Convert to Python dict
        result_dict = dict(go_result.items())

        # Parse block height
        try:
            block_height = int(result_dict.get("BlockHeight", "0"))
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Failed to parse transaction event: Invalid BlockHeight. "
                f"BlockHeight: {result_dict.get('BlockHeight')}"
            ) from e

        # Parse fee distributions from JSON
        fee_distributions_json = result_dict.get("FeeDistributions", "[]")
        fee_distributions: list[FeeDistribution] = []

        if fee_distributions_json and fee_distributions_json != "[]":
            try:
                fee_distributions_data = json.loads(fee_distributions_json)
                for dist in fee_distributions_data:
                    fee_distributions.append({
                        "recipient": dist.get("recipient", ""),
                        "amount": dist.get("amount", "")
                    })
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                raise ValueError(
                    f"Failed to parse fee distributions: {e}. "
                    f"FeeDistributions: {fee_distributions_json}"
                ) from e

        # Convert nullable fields (empty string → None)
        fee_recipient = result_dict.get("FeeRecipient")
        if fee_recipient == "":
            fee_recipient = None

        metadata = result_dict.get("Metadata")
        if metadata == "":
            metadata = None

        # Build result
        return {
            "tx_id": result_dict.get("TxID", ""),
            "block_height": block_height,
            "method": result_dict.get("Method", ""),
            "caller": result_dict.get("Caller", ""),
            "fee_amount": result_dict.get("FeeAmount", "0"),
            "fee_recipient": fee_recipient,
            "metadata": metadata,
            "fee_distributions": fee_distributions,
        }

    def list_transaction_fees(
            self,
            wallet: str,
            mode: str = "paid",
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[TransactionFeeEntry]:
        """
        List transactions filtered by wallet address and mode.

        Args:
            wallet: Ethereum address to query (required)
            mode: Filter mode - one of: "paid", "received", "both" (default: "paid")
            limit: Maximum results to return (default: 20, max: 1000)
            offset: Pagination offset (default: 0)

        Returns:
            List of TransactionFeeEntry dictionaries.
            Note: Returns one row per fee distribution, so a transaction with
            multiple distributions will appear multiple times.

        Raises:
            ValueError: If wallet is empty or mode is invalid

        Example:
            >>> # List fees paid by wallet
            >>> entries = client.list_transaction_fees(
            ...     wallet="0x1234...",
            ...     mode="paid",
            ...     limit=10
            ... )
            >>> for entry in entries:
            ...     print(f"{entry['method']}: {entry['total_fee']} wei")
        """
        # Validate inputs
        if not wallet or wallet.strip() == "":
            raise ValueError("wallet is required and cannot be empty")

        valid_modes = ["paid", "received", "both"]
        if mode not in valid_modes:
            raise ValueError(f"mode must be one of: {', '.join(valid_modes)}")

        if limit is not None and (limit <= 0 or limit > 1000):
            raise ValueError("limit must be between 1 and 1000")

        if offset is not None and offset < 0:
            raise ValueError("offset cannot be negative")

        # Set defaults
        limit_val = limit if limit is not None else 20
        offset_val = offset if offset is not None else 0

        # Call Go binding
        go_results = truf_sdk.ListTransactionFees(
            self.client,
            wallet,
            mode,
            limit_val,
            offset_val,
        )

        # Convert to Python list of dicts
        results: list[TransactionFeeEntry] = []
        for go_map in go_results:
            item = dict(go_map.items())

            # Parse block height
            try:
                block_height = int(item.get("BlockHeight", "0"))
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Failed to parse transaction fee entry: Invalid BlockHeight. "
                    f"BlockHeight: {item.get('BlockHeight')}, item: {item}"
                ) from e

            # Parse distribution sequence
            try:
                distribution_sequence = int(item.get("DistributionSequence", "0"))
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Failed to parse transaction fee entry: Invalid DistributionSequence. "
                    f"DistributionSequence: {item.get('DistributionSequence')}, item: {item}"
                ) from e

            # Convert nullable fields (empty string → None)
            fee_recipient = item.get("FeeRecipient")
            if fee_recipient == "":
                fee_recipient = None

            metadata = item.get("Metadata")
            if metadata == "":
                metadata = None

            distribution_recipient = item.get("DistributionRecipient")
            if distribution_recipient == "":
                distribution_recipient = None

            distribution_amount = item.get("DistributionAmount")
            if distribution_amount == "":
                distribution_amount = None

            results.append({
                "tx_id": item.get("TxID", ""),
                "block_height": block_height,
                "method": item.get("Method", ""),
                "caller": item.get("Caller", ""),
                "total_fee": item.get("TotalFee", "0"),
                "fee_recipient": fee_recipient,
                "metadata": metadata,
                "distribution_sequence": distribution_sequence,
                "distribution_recipient": distribution_recipient,
                "distribution_amount": distribution_amount,
            })

        return results

    # ═══════════════════════════════════════════════════════════════
    # ORDER BOOK - MARKET OPERATIONS
    # ═══════════════════════════════════════════════════════════════

    def create_market(
        self,
        query_hash: bytes,
        settle_time: int,
        max_spread: int,
        min_order_size: int,
    ) -> str:
        """
        Create a new prediction market.

        Args:
            query_hash: 32-byte SHA256 hash of the query
            settle_time: Unix timestamp when market can be settled
            max_spread: Maximum spread for LP rewards (1-50 cents)
            min_order_size: Minimum order size for LP rewards

        Returns:
            Transaction hash

        Raises:
            RuntimeError: If market creation fails

        Example:
            >>> import hashlib
            >>> query_hash = hashlib.sha256(b"btc_price_gt_50000").digest()
            >>> settle_time = int(time.time()) + 3600
            >>> tx_hash = client.create_market(query_hash, settle_time, 5, 100)
        """
        if len(query_hash) != 32:
            raise ValueError("query_hash must be exactly 32 bytes")
        if max_spread < 1 or max_spread > 50:
            raise ValueError("max_spread must be between 1 and 50")
        if min_order_size <= 0:
            raise ValueError("min_order_size must be positive")

        tx_hash = truf_sdk.CreateMarket(
            self._client,
            query_hash,
            settle_time,
            max_spread,
            min_order_size,
        )

        if not tx_hash:
            raise RuntimeError("Failed to create market")

        return tx_hash

    def get_market_info(self, query_id: int) -> MarketInfo:
        """Get market details by ID."""
        json_str = truf_sdk.GetMarketInfo(self._client, query_id)

        if not json_str:
            raise RuntimeError(f"Market {query_id} not found")

        data = json.loads(json_str)
        data["hash"] = bytes.fromhex(data["hash"].replace("0x", ""))
        data["creator"] = bytes.fromhex(data["creator"].replace("0x", ""))

        return cast(MarketInfo, data)

    def get_market_by_hash(self, query_hash: bytes) -> MarketInfo:
        """Get market details by query hash."""
        if len(query_hash) != 32:
            raise ValueError("query_hash must be exactly 32 bytes")

        json_str = truf_sdk.GetMarketByHash(self._client, query_hash)

        if not json_str:
            raise RuntimeError("Market not found for given hash")

        data = json.loads(json_str)
        data["hash"] = bytes.fromhex(data["hash"].replace("0x", ""))
        data["creator"] = bytes.fromhex(data["creator"].replace("0x", ""))

        return cast(MarketInfo, data)

    def list_markets(
        self,
        settled_filter: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MarketSummary]:
        """List markets with optional filtering."""
        settled_int = -1 if settled_filter is None else (1 if settled_filter else 0)

        json_str = truf_sdk.ListMarkets(self._client, settled_int, limit, offset)

        if not json_str:
            return []

        markets = json.loads(json_str)

        for market in markets:
            market["hash"] = bytes.fromhex(market["hash"].replace("0x", ""))

        return cast(list[MarketSummary], markets)

    def market_exists(self, query_hash: bytes) -> bool:
        """Check if market exists by hash."""
        if len(query_hash) != 32:
            raise ValueError("query_hash must be exactly 32 bytes")

        return truf_sdk.MarketExists(self._client, query_hash)

    def validate_market_collateral(self, query_id: int) -> MarketValidation:
        """Validate market collateral integrity."""
        json_str = truf_sdk.ValidateMarketCollateral(self._client, query_id)

        if not json_str:
            raise RuntimeError(f"Failed to validate market {query_id}")

        return cast(MarketValidation, json.loads(json_str))

    # ═══════════════════════════════════════════════════════════════
    # ORDER BOOK - ORDER OPERATIONS
    # ═══════════════════════════════════════════════════════════════

    def place_buy_order(
        self,
        query_id: int,
        outcome: bool,
        price: int,
        amount: int,
    ) -> str:
        """
        Place a buy order for YES or NO shares.

        Args:
            query_id: Market ID
            outcome: True for YES shares, False for NO shares
            price: Price per share in cents (1-99)
            amount: Number of shares to buy

        Returns:
            Transaction hash

        Example:
            >>> tx_hash = client.place_buy_order(
            ...     query_id=1,
            ...     outcome=True,
            ...     price=56,
            ...     amount=100
            ... )
        """
        if price < 1 or price > 99:
            raise ValueError("price must be between 1 and 99 cents")
        if amount <= 0:
            raise ValueError("amount must be positive")

        tx_hash = truf_sdk.PlaceBuyOrder(self._client, query_id, outcome, price, amount)

        if not tx_hash:
            raise RuntimeError("Failed to place buy order")

        return tx_hash

    def place_sell_order(
        self,
        query_id: int,
        outcome: bool,
        price: int,
        amount: int,
    ) -> str:
        """Place a sell order for shares you own."""
        if price < 1 or price > 99:
            raise ValueError("price must be between 1 and 99 cents")
        if amount <= 0:
            raise ValueError("amount must be positive")

        tx_hash = truf_sdk.PlaceSellOrder(self._client, query_id, outcome, price, amount)

        if not tx_hash:
            raise RuntimeError("Failed to place sell order")

        return tx_hash

    def place_split_limit_order(
        self,
        query_id: int,
        true_price: int,
        amount: int,
    ) -> str:
        """
        Mint binary share pairs and list unwanted side for sale.

        Args:
            query_id: Market ID
            true_price: YES price in cents (1-99)
            amount: Number of share PAIRS to mint

        Example:
            >>> tx_hash = client.place_split_limit_order(
            ...     query_id=1,
            ...     true_price=56,
            ...     amount=100
            ... )
        """
        if true_price < 1 or true_price > 99:
            raise ValueError("true_price must be between 1 and 99 cents")
        if amount <= 0:
            raise ValueError("amount must be positive")

        tx_hash = truf_sdk.PlaceSplitLimitOrder(self._client, query_id, true_price, amount)

        if not tx_hash:
            raise RuntimeError("Failed to place split limit order")

        return tx_hash

    def cancel_order(
        self,
        query_id: int,
        outcome: bool,
        price: int,
    ) -> str:
        """Cancel an open buy or sell order."""
        if price == 0:
            raise ValueError("Cannot cancel holdings (price=0), use place_sell_order instead")
        if price < -99 or price > 99:
            raise ValueError("price must be between -99 and 99 (excluding 0)")

        tx_hash = truf_sdk.CancelOrder(self._client, query_id, outcome, price)

        if not tx_hash:
            raise RuntimeError("Failed to cancel order")

        return tx_hash

    def change_bid(
        self,
        query_id: int,
        outcome: bool,
        old_price: int,
        new_price: int,
        new_amount: int,
    ) -> str:
        """Atomically modify buy order price and amount."""
        if old_price >= 0 or new_price >= 0:
            raise ValueError("bid prices must be negative (buy orders)")
        if new_amount <= 0:
            raise ValueError("new_amount must be positive")

        tx_hash = truf_sdk.ChangeBid(
            self._client, query_id, outcome, old_price, new_price, new_amount
        )

        if not tx_hash:
            raise RuntimeError("Failed to change bid")

        return tx_hash

    def change_ask(
        self,
        query_id: int,
        outcome: bool,
        old_price: int,
        new_price: int,
        new_amount: int,
    ) -> str:
        """Atomically modify sell order price and amount."""
        if old_price <= 0 or new_price <= 0:
            raise ValueError("ask prices must be positive (sell orders)")
        if new_amount <= 0:
            raise ValueError("new_amount must be positive")

        tx_hash = truf_sdk.ChangeAsk(
            self._client, query_id, outcome, old_price, new_price, new_amount
        )

        if not tx_hash:
            raise RuntimeError("Failed to change ask")

        return tx_hash

    # ═══════════════════════════════════════════════════════════════
    # ORDER BOOK - QUERY OPERATIONS
    # ═══════════════════════════════════════════════════════════════

    def get_order_book(self, query_id: int, outcome: bool) -> list[OrderBookEntry]:
        """Get all buy/sell orders for a market outcome."""
        json_str = truf_sdk.GetOrderBook(self._client, query_id, outcome)

        if not json_str:
            return []

        orders = json.loads(json_str)

        for order in orders:
            order["wallet_address"] = bytes.fromhex(order["wallet_address"].replace("0x", ""))

        return cast(list[OrderBookEntry], orders)

    def get_user_positions(self) -> list[UserPosition]:
        """Get caller's portfolio across all markets."""
        json_str = truf_sdk.GetUserPositions(self._client)

        if not json_str:
            return []

        return cast(list[UserPosition], json.loads(json_str))

    def get_market_depth(self, query_id: int, outcome: bool) -> list[DepthLevel]:
        """Get aggregated volume per price level."""
        json_str = truf_sdk.GetMarketDepth(self._client, query_id, outcome)

        if not json_str:
            return []

        return cast(list[DepthLevel], json.loads(json_str))

    def get_best_prices(self, query_id: int, outcome: bool) -> BestPrices:
        """Get current bid/ask spread."""
        json_str = truf_sdk.GetBestPrices(self._client, query_id, outcome)

        if not json_str:
            raise RuntimeError("Failed to get best prices")

        return cast(BestPrices, json.loads(json_str))

    def get_user_collateral(self) -> UserCollateral:
        """Get caller's total locked collateral value."""
        json_str = truf_sdk.GetUserCollateral(self._client)

        if not json_str:
            return {
                "total_locked": "0",
                "buy_orders_locked": "0",
                "shares_value": "0",
            }

        return cast(UserCollateral, json.loads(json_str))

    # ═══════════════════════════════════════════════════════════════
    # ORDER BOOK - SETTLEMENT & REWARDS
    # ═══════════════════════════════════════════════════════════════

    def settle_market(self, query_id: int) -> str:
        """Settle a market using attestation results."""
        tx_hash = truf_sdk.SettleMarket(self._client, query_id)

        if not tx_hash:
            raise RuntimeError(f"Failed to settle market {query_id}")

        return tx_hash

    def sample_lp_rewards(self, query_id: int, block: int) -> str:
        """Sample liquidity provider rewards for a block."""
        tx_hash = truf_sdk.SampleLPRewards(self._client, query_id, block)

        if not tx_hash:
            raise RuntimeError(f"Failed to sample LP rewards for market {query_id}")

        return tx_hash

    def get_distribution_summary(self, query_id: int) -> DistributionSummary:
        """Get fee distribution summary for a market."""
        json_str = truf_sdk.GetDistributionSummary(self._client, query_id)

        if not json_str:
            raise RuntimeError(f"No distribution found for market {query_id}")

        return cast(DistributionSummary, json.loads(json_str))

    def get_distribution_details(self, distribution_id: int) -> list[LPRewardDetail]:
        """Get per-LP reward breakdown."""
        json_str = truf_sdk.GetDistributionDetails(self._client, distribution_id)

        if not json_str:
            return []

        details = json.loads(json_str)

        for detail in details:
            detail["wallet_address"] = bytes.fromhex(detail["wallet_address"].replace("0x", ""))

        return cast(list[LPRewardDetail], details)

    def get_participant_reward_history(self, wallet_hex: str) -> list[RewardHistory]:
        """Get reward history for a wallet."""
        json_str = truf_sdk.GetParticipantRewardHistory(self._client, wallet_hex)

        if not json_str:
            return []

        return cast(list[RewardHistory], json.loads(json_str))


def all_is_list_of_strings[T](arg_list: list[T]) -> bool:
    return all(
        isinstance(arg, list) and all(isinstance(item, str) for item in arg)
        for arg in arg_list
    )


def all_is_list_of_floats[T](arg_list: list[T]) -> bool:
    return all(
        isinstance(arg, list) and all(isinstance(item, (float, int)) for item in arg)
        for arg in arg_list
    )
