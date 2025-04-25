import json
import trufnetwork_sdk_c_bindings.exports as truf_sdk
import trufnetwork_sdk_c_bindings.go as go

from typing import Dict, List, Union, Optional, Any, TypedDict

class Record(TypedDict):
    date: int # UNIX
    value: float

class RecordBatch(TypedDict):
    stream_id: str
    inputs: List[Record]

class TNClient:
    def __init__(self, url: str, token: str):
        """
        Initialize a new client by calling the Go-layer's NewClient.
        """
        self.client = truf_sdk.NewClient(url, token)

    # --------------------------------------------------
    #               Private Helper Methods
    # --------------------------------------------------

    def _coalesce_str(self, val: Optional[str], default: str = "") -> str:
        """
        Helper to coalesce an optional string into a non-empty string.
        If val is None, return default; otherwise return val.
        """
        return val if val is not None else default

    def _coalesce_int(self, val: Optional[int], default: int = -1) -> int:
        """
        Helper to coalesce an optional integer into a sentinel value.
        
        Args:
            val: The optional integer value
            default: The default value to use if val is None (-1 by default)
            
        Returns:
            The non-None integer value
        """
        return val if val is not None else default

    def _go_slice_of_maps_to_list_of_dicts(
        self, go_slice: Any
    ) -> List[Dict[str, Any]]:
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

    def _records_handle_to_list_of_dicts(self, records: Any) -> List[Dict[str, Any]]:
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
            if not field.startswith("_") and field not in ("handle", "incref", "decref"):
                try:
                    value = getattr(records, field)
                    record_dict[field] = value
                except AttributeError:
                    continue

        if record_dict:
            result.append(record_dict)
        return result

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
            truf_sdk.WaitForTx(self.client, deploy_tx_hash)
        return deploy_tx_hash
    
    def insert_record(
        self,
        stream_id: str,
        record: Dict[str, Union[float, int]],
        wait: bool = True
    ) -> str:
        """
        Insert a single record into a stream with the given stream ID.
        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash.

        Record is expected to have:
          - "date": int (UNIX timestamp)
          - "value": float or int
        """
        go_input = truf_sdk.NewInsertRecordInput(self.client, stream_id, record["date"], record["value"])
        insert_tx_hash = truf_sdk.InsertRecord(self.client, go_input)

        if wait:
            truf_sdk.WaitForTx(self.client, insert_tx_hash)

        return insert_tx_hash

    def insert_records(
        self,
        stream_id: str,
        records: List[Dict[str, Union[float, int]]],
        wait: bool = True,
    ) -> str:
        """
        Insert records into a stream with the given stream ID.
        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash.

        Each record is expected to have:
          - "date": int (UNIX timestamp) 
          - "value": float or int

        Note: Do not use this for inserting multiple records rapidly. Use batch inserts instead.
        Or else you can have nonce errors.
        """

        input_list = []
        for _, record in enumerate(records):
            # Create InsertRecordInput struct
            go_input = truf_sdk.NewInsertRecordInput(self.client, stream_id, record["date"], record["value"])
            input_list.append(go_input)
        
        go_input_list = truf_sdk.Slice_s2_types_InsertRecordInput(input_list)
        insert_tx_hash = truf_sdk.InsertRecords(self.client, go_input_list)

        if wait:
            truf_sdk.WaitForTx(self.client, insert_tx_hash)

        return insert_tx_hash

    def batch_insert_records(
        self,
        batches: List[RecordBatch],
        wait: bool = True,
    ) -> List[str]:
        tx_hashes = []
        for batch_idx, batch in enumerate(batches, start=1):
            inputs = batch["inputs"]

            # 1) Log the batch metadata
            print(f"Batch #{batch_idx}: stream={batch['stream_id']} count={len(inputs)}")

            # 2) Dump each Python record dict
            for rec_idx, record in enumerate(inputs, start=1):
                print(f"  Rec {rec_idx}: date={record['date']}  value={record['value']}")

            # 3) Build your Go‐struct list
            input_list = []
            for record in inputs:
                go_input = truf_sdk.NewInsertRecordInput(
                    self.client,
                    batch["stream_id"],
                    record["date"],
                    record["value"],
                )
                input_list.append(go_input)

            # 4) Now you know exactly what you’re passing in
            print(f"Built {len(input_list)} Go InsertRecordInput structs for stream {batch['stream_id']}")

            go_input_list = truf_sdk.Slice_s2_types_InsertRecordInput(input_list)

            # (Optional) if the binding exposes getters, you can peek at the first one:
            first = input_list[0]
            print(f" First struct → stream={first.StreamId()} date={first.EventTime()} value={first.Value()}")
            print(first)

            print(go_input_list[0])

            try:
                insert_tx_hash = truf_sdk.InsertRecords(self.client, go_input_list)
                tx_hashes.append(insert_tx_hash)
            except Exception as e:
                error_str = str(e)
                if "failed to estimate price" in error_str:
                    raise ValueError("Request too large: batch size too big") from e
                raise

        if wait:
            for tx in tx_hashes:
                truf_sdk.WaitForTx(self.client, tx)

        return tx_hashes


    def get_records(
        self,
        stream_id: str,
        data_provider: Optional[str] = None,
        date_from: Optional[int] = None,
        date_to: Optional[int] = None,
        frozen_at: Optional[int] = None,
        base_date: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get records from a stream with the given stream ID.
        Returns a list of records.

        Parameters:
            - stream_id : str
            - data_provider : (hex string)
            - date_from : Optional[int] (UNIX)
            - date_to : Optional[int] (UNIX)
            - frozen_at : Optional[int] (UNIX)
            - base_date : Optional[int] (UNIX)
        """
        data_provider = self._coalesce_str(data_provider)
        date_from = self._coalesce_int(date_from)
        date_to = self._coalesce_int(date_to)
        frozen_at = self._coalesce_int(frozen_at)
        base_date = self._coalesce_int(base_date)

        input = truf_sdk.NewGetRecordInput(
            self.client, 
            stream_id,
            data_provider,
            date_from,
            date_to,
            frozen_at,
            base_date
        )
        go_slice_of_maps = truf_sdk.GetRecords(self.client, input)

        return self._go_slice_of_maps_to_list_of_dicts(go_slice_of_maps)

    def get_type(self, stream_id: str, data_provider: Optional[str] = None) -> str:
        """
        Get the type of a stream with the given stream ID.
        Returns the type of the stream.
        """
        data_provider = self._coalesce_str(data_provider)
        return truf_sdk.GetType(self.client, stream_id, data_provider)

    def wait_for_tx(self, tx_hash: str) -> None:
        """
        Wait for a transaction to be confirmed given its hash.
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

    def get_first_record(
        self,
        stream_id: str,
        data_provider: Optional[str] = None,
        after_date: Optional[int] = None,
        frozen_at: Optional[int] = None,
    ) -> Optional[Dict[str, Union[str, float]]]:
        """
        Get the first record of a stream after a given date.
        
        Parameters:
            - stream_id : str
            - data_provider : Optional[str] (hex string)
            - after_date : Optional[int] (UNIX)
            - frozen_at : Optional[int] (UNIX)
            
        Returns:
            Optional[Dict[str, Union[str, float]]] - A dictionary containing 'date' and 'value' if found, None otherwise
        """
        data_provider = self._coalesce_str(data_provider)
        after_date = self._coalesce_int(after_date)
        frozen_at = self._coalesce_int(frozen_at)

        input = truf_sdk.NewGetFirstRecordInput(self.client, stream_id, data_provider, after_date, frozen_at)
        result = truf_sdk.GetFirstRecord(self.client, input)
        
        # Convert the result to a Python dict and convert the value to float
        record = dict(result.items())

        # nil from go is an empty map, not None
        if not record:
            return None

        record["value"] = float(record["value"])
        return record
    
    def get_index(
        self,
        stream_id: str,
        data_provider: Optional[str] = None,
        date_from: Optional[int] = None,
        date_to: Optional[int] = None,
        frozen_at: Optional[int] = None,
        base_date: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get index from a stream with the given stream ID.
        Returns a list of indexes.

        Index: Calculated values derived from stream data, representing a value's growth compared to the stream's first record.

        Parameters:
            - stream_id : str
            - data_provider : (hex string)
            - date_from : Optional[int] (UNIX)
            - date_to : Optional[int] (UNIX)
            - frozen_at : Optional[int] (UNIX)
            - base_date : Optional[int] (UNIX)
        """
        data_provider = self._coalesce_str(data_provider)
        date_from = self._coalesce_int(date_from)
        date_to = self._coalesce_int(date_to)
        frozen_at = self._coalesce_int(frozen_at)
        base_date = self._coalesce_int(base_date)

        input = truf_sdk.NewGetRecordInput(
            self.client, 
            stream_id,
            data_provider,
            date_from,
            date_to,
            frozen_at,
            base_date
        )
        go_slice_of_maps = truf_sdk.GetIndex(self.client, input)

        return self._go_slice_of_maps_to_list_of_dicts(go_slice_of_maps)

    def list_streams(
        self, 
        limit: Optional[int] = None, 
        offset: Optional[int] = None, 
        data_provider: Optional[str] = None, 
        order_by: Optional[str] = None
    ):
        """
            List all streams associated with client account
        """
        limit = self._coalesce_int(limit)
        offset = self._coalesce_int(offset)
        data_provider = self._coalesce_str(data_provider)
        order_by = self._coalesce_str(order_by)

        input = truf_sdk.NewListStreamsInput(limit, offset, data_provider, order_by)
        go_slice_of_maps = truf_sdk.ListStreams(self.client, input)

        return self._go_slice_of_maps_to_list_of_dicts(go_slice_of_maps)
        
    def set_taxonomy(
        self, 
        stream_id: str,
        child_streams: Dict[str, int],
        start_date: Optional[int] = None,
        group_sequence: Optional[int] = None,
        wait: bool = True
    ):
        """
        Set Taxonomy will define taxonomy of a composed stream.
        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash.

        Each child stream is expected to have dictionary of:
          - "stream id" as the key
          - "weight" as the value

        Start date defines the starting point of value from the composed stream.
        """
        group_sequence = self._coalesce_int(group_sequence)
        start_date = self._coalesce_int(start_date)

        taxonomies = []
        for id, weight in child_streams.items():
            taxonomy_item = truf_sdk.NewTaxonomyItemInput(self.client, id, weight)
            taxonomies.append(taxonomy_item)

        taxonomies_go = truf_sdk.Slice_s2_types_TaxonomyItem(taxonomies)
        input = truf_sdk.NewTaxonomyInput(
            self.client, 
            stream_id, 
            taxonomies_go,
            start_date,
            group_sequence
        )
        tx_hash = truf_sdk.SetTaxonomy(self.client, input)

        if wait:
            truf_sdk.WaitForTx(self.client, tx_hash)

        return tx_hash
    
    def describe_taxonomy(self, stream_id: str, latest_version: bool = True):
        """
        Get taxonomy structure of a composed stream

        If latest_version is true, then it will return only the latest version of the taxonomy

        Parameters:
            - stream_id : str
            - latest_version : bool
        """
         
        result = truf_sdk.DescribeTaxonomy(self.client, stream_id, latest_version)
        taxonomy = dict(result.items())
        taxonomy["child_streams"] = json.loads(taxonomy["child_streams"])

        for child_stream in taxonomy["child_streams"]:
            child_stream["weight"] = round(float(child_stream["weight"]), 2)

        return taxonomy

    def allow_compose_stream(self, stream_id: str, wait: bool = True):
        """
        Allows streams to use this stream as child, if composing is private.

        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash.
        """
        tx_hash = truf_sdk.AllowComposeStream(self.client, stream_id)

        if wait:
            truf_sdk.WaitForTx(self.client, tx_hash)

        return tx_hash
    
    def disable_compose_stream(self, stream_id: str, wait: bool = True):
        """
        Disable streams from using this stream as child.

        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash.
        """
        tx_hash = truf_sdk.DisableComposeStream(self.client, stream_id)

        if wait:
            truf_sdk.WaitForTx(self.client, tx_hash)

        return tx_hash

    def allow_read_wallet(self, stream_id: str, wallet: str, wait: bool = True):
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

    def disable_read_wallet(self, stream_id: str, wallet: str, wait: bool = True):
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

    def set_read_visibility(self, stream_id: str, visibilityVal: str, wait: bool = True):
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
    
    def get_read_visibility(self, stream_id: str):
        """
        Gets the read visibility of the stream -- Private or Public
        """

        visibility = truf_sdk.GetReadVisibility(self.client, stream_id)

        return "public" if visibility == truf_sdk.VisibilityPublic else "private"
    
    def set_compose_visibility(self, stream_id: str, visibilityVal: int, wait: bool = True):
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

    def get_compose_visibility(self, stream_id: str):
        """
        Gets the compose visibility of the stream -- Private or Public
        """

        visibility = truf_sdk.GetComposeVisibility(self.client, stream_id)

        return "public" if visibility == truf_sdk.VisibilityPublic else "private"
    
    def get_allowed_read_wallets(self, stream_id: str):
        """
        Gets the wallets allowed to read the stream, if read stream is private
        """

        wallets = truf_sdk.GetAllowedReadWallets(self.client, stream_id)
        return wallets
    
    def get_allowed_compose_streams(self, stream_id: str):
        """
        Gets the streams allowed to compose this stream, if compose stream is private
        """
         
        streams = truf_sdk.GetAllowedComposeStreams(self.client, stream_id)
        return streams

def all_is_list_of_strings(arg_list: list[Any]) -> bool:
    return all(isinstance(arg, list) and all(isinstance(item, str) for item in arg) for arg in arg_list)

def all_is_list_of_floats(arg_list: list[Any]) -> bool:
    return all(isinstance(arg, list) and all(isinstance(item, (float, int)) for item in arg) for arg in arg_list)

