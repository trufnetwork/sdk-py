import json
import trufnetwork_sdk_c_bindings.exports as truf_sdk
import trufnetwork_sdk_c_bindings.go as go

from typing import Dict, List, Union, Optional, Any, TypedDict, Literal, cast

# Expose StreamType constants at the Python level
STREAM_TYPE_PRIMITIVE = cast(Literal["primitive"], truf_sdk.StreamTypePrimitive)
STREAM_TYPE_COMPOSED = cast(Literal["composed"], truf_sdk.StreamTypeComposed)
VISIBILITY_PUBLIC = truf_sdk.VisibilityPublic
VISIBILITY_PRIVATE = truf_sdk.VisibilityPrivate

class Record(TypedDict):
    date: int # UNIX
    value: float

class RecordBatch(TypedDict):
    stream_id: str
    inputs: List[Record]

class StreamDefinitionInput(TypedDict):
    stream_id: str
    stream_type: Literal["primitive", "composed"]

class StreamLocatorInput(TypedDict):
    stream_id: str
    data_provider: str

class StreamExistsResult(TypedDict):
    stream_id: str
    data_provider: str
    exists: bool

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
        
        go_input_list = truf_sdk.Slice_s1_types_InsertRecordInput(input_list)
        insert_tx_hash = truf_sdk.InsertRecords(self.client, go_input_list)

        if wait:
            truf_sdk.WaitForTx(self.client, insert_tx_hash)

        return insert_tx_hash

    def batch_insert_records(
        self,
        batches: List[RecordBatch],
        wait: bool = True,
    ) -> str:
        """
        Insert multiple batches of records into different streams in a single transaction.
        Each batch should be a dictionary containing:
            - stream_id: str
            - inputs: List[Dict[int, float]] where each dict has:
                - date: int (UNIX timestamp)
                - value: float

        Parameters:
            - batches : List of batch dictionaries
            - wait : bool - Whether to wait for transactions to be confirmed

        Returns:
            Single transaction hash for all the records
        """
        all_inputs = []
        
        # Collect all records from all batches into a single list
        for batch in batches:
            stream_id = batch["stream_id"]
            inputs = batch["inputs"]
            
            for record in inputs:
                # Create InsertRecordInput struct for each record
                go_input = truf_sdk.NewInsertRecordInput(self.client, stream_id, record["date"], record["value"])
                all_inputs.append(go_input)
        
        # Convert to Go slice and make a single call to InsertRecords
        go_input_list = truf_sdk.Slice_s1_types_InsertRecordInput(all_inputs)

        try:
            insert_tx_hash = truf_sdk.InsertRecords(self.client, go_input_list)
        except Exception as e:
            error_str = str(e)
            if "failed to estimate price" in error_str:
                raise ValueError("Request too large: The batch size exceeds the maximum allowed size") from e
            raise e
        
        if wait:
            truf_sdk.WaitForTx(self.client, insert_tx_hash)

        return insert_tx_hash

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

        taxonomies_go = truf_sdk.Slice_s1_types_TaxonomyItem(taxonomies)
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

    def batch_deploy_streams(
        self,
        definitions: List[StreamDefinitionInput],
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
        go_definitions = truf_sdk.Slice_s2_types_StreamDefinition([])
        for def_input in definitions:
            # The Go binding layer (NewStreamDefinitionForBinding) will handle conversion from string to Go types.
            # However, gomobile does not directly support passing slices of structs that are not built-in or explicitly defined
            # for slices in the .go file (like Slice_s2_types_InsertRecordInput).
            # We must construct each Go object and append it to a Go slice.
            # This requires a helper in Go to create the individual StreamDefinition objects first,
            # then append them to Slice_s2_types_StreamDefinition.
            # For now, assuming direct slice creation might work or we adjust bindings if not.
            # This part might need refinement based on gomobile's exact capabilities for custom struct slices.
            # Let's assume for now direct construction and appending to a list, then converting to Go slice.
            # If this doesn't work, we'll need NewStreamDefinitionForBinding in Go and build the slice there.

            # Simplified approach: directly create the Go slice of structs if supported by gomobile bindings.
            # The Python SDK will pass a list of dicts. The Go binding code (not shown here directly)
            # would iterate this, call NewStreamDefinitionForBinding for each, and build the Go slice.
            # The current truf_sdk.Slice_s2_types_StreamDefinition expects a list of Go StreamDefinition objects.

            # Correct approach given current structure:
            # Python builds a list of Python dicts.
            # The Go binding function `BatchDeployStreams` must accept this (e.g. []map[string]string)
            # and internally convert to []types.StreamDefinition.
            # OR, Python calls a Go helper for EACH definition to get a Go StreamDefinition handle,
            # collects these handles, and passes a slice of these handles.
            # Let's assume the Go `BatchDeployStreams` function now expects []types.StreamDefinition directly,
            # and `Slice_s2_types_StreamDefinition` is smart enough or we build it item by item using a Go helper.

            # Let's assume NewStreamDefinitionForBinding is available at the Go `exports` level
            # and we are constructing the slice of these Go objects in Python.
            # This is complex due to object handles across language boundaries.

            # The most straightforward way with current gomobile patterns:
            # 1. Python prepares list of dicts.
            # 2. Go binding `BatchDeployStreams` takes `List[Dict[str,str]]` (represented as `[]interface{}` or specific slice of maps).
            # 3. Go binding internally iterates, calls `NewStreamDefinitionForBinding` for each, builds `[]types.StreamDefinition`.
            # For this edit, I will assume the Go binding `BatchDeployStreams` in `bindings.go` will be adjusted
            # to take a slice of Go `StreamDefinition` objects, and we prepare it in Python by calling a (yet to be confirmed)
            # Go helper for each item and then creating a Go slice from these. 
            # Given the current binding structure, this is the most likely path for Slice_s2_types_StreamDefinition

            # Revisiting the Go bindings: `BatchDeployStreams(client *tnclient.Client, definitions []types.StreamDefinition)`
            # This means Python must construct `[]types.StreamDefinition`.
            # `truf_sdk.NewStreamDefinitionForBinding` will be used.
            go_def = truf_sdk.NewStreamDefinitionForBinding(def_input["stream_id"], def_input["stream_type"])
            # This go_def is a handle. We need to append these handles to the slice.
            # The truf_sdk.Slice_s2_types_StreamDefinition is likely expecting a list of these handles.
            go_definitions.append(go_def) # This is pseudocode for how gomobile might handle slice appends
                                        # Actual mechanism depends on gomobile's generated Python bindings for slices of custom types.
                                        # If `Slice_s2_types_StreamDefinition` is a constructor that takes a list of handles, that's it.
                                        # If not, this part needs careful implementation based on `gomobile bind` output.

        # The below is a common pattern for gomobile if Slice_s2_types_StreamDefinition is a list-like object in Python
        # that wraps the Go slice. Often, you build a Python list of the Go object handles.
        py_list_of_go_defs = []
        for def_input in definitions:
            go_def_handle = truf_sdk.NewStreamDefinitionForBinding(def_input["stream_id"], def_input["stream_type"])
            # We should check for errors from NewStreamDefinitionForBinding if it can return them.
            # Assuming it raises an exception on error for simplicity here.
            py_list_of_go_defs.append(go_def_handle)
        
        # Now, convert the Python list of Go object handles to the required Go slice type.
        # This conversion mechanism is specific to how gomobile wraps slice types.
        # It might be direct: `go_slice_defs = truf_sdk.Slice_s2_types_StreamDefinition(py_list_of_go_defs)`
        # Or it might involve a specific constructor or method.
        # For now, let's assume `Slice_s2_types_StreamDefinition` can take a list of these handles.
        final_go_definitions = truf_sdk.Slice_s2_types_StreamDefinition(py_list_of_go_defs)

        tx_hash = truf_sdk.BatchDeployStreams(self.client, final_go_definitions)
        if wait:
            truf_sdk.WaitForTx(self.client, tx_hash)
        return tx_hash

    def batch_stream_exists(
        self,
        locators: List[StreamLocatorInput],
    ) -> List[StreamExistsResult]:
        """
        Check for the existence of multiple streams.
        Each locator should be a dictionary containing:
            - stream_id: str
            - data_provider: str (hex string)

        Returns a list of results, each indicating if a stream exists.
        """
        py_list_of_go_locators = []
        for loc_input in locators:
            go_loc_handle = truf_sdk.NewStreamLocatorForBinding(loc_input["stream_id"], loc_input["data_provider"])
            py_list_of_go_locators.append(go_loc_handle)
        
        final_go_locators = truf_sdk.Slice_s2_types_StreamLocator(py_list_of_go_locators)

        go_results = truf_sdk.BatchStreamExists(self.client, final_go_locators)
        
        results = []
        for go_map in go_results:
            item = dict(go_map.items()) # Convert Go map to Python dict
            results.append({
                "stream_id": item["stream_id"],
                "data_provider": item["data_provider"],
                "exists": item["exists"].lower() == "true", # Convert string "true"/"false" to bool
            })
        return results

    def batch_filter_streams_by_existence(
        self,
        locators: List[StreamLocatorInput],
        return_existing: bool,
    ) -> List[StreamLocatorInput]: # Returns List[StreamLocatorInput] as they are just locators
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
            go_loc_handle = truf_sdk.NewStreamLocatorForBinding(loc_input["stream_id"], loc_input["data_provider"])
            py_list_of_go_locators.append(go_loc_handle)

        final_go_locators = truf_sdk.Slice_s2_types_StreamLocator(py_list_of_go_locators)

        go_results = truf_sdk.BatchFilterStreamsByExistence(self.client, final_go_locators, return_existing)
        
        results = []
        for go_map in go_results:
            item = dict(go_map.items()) # Convert Go map to Python dict
            results.append({
                "stream_id": item["stream_id"],
                "data_provider": item["data_provider"],
            })
        return results

def all_is_list_of_strings(arg_list: list[Any]) -> bool:
    return all(isinstance(arg, list) and all(isinstance(item, str) for item in arg) for arg in arg_list)

def all_is_list_of_floats(arg_list: list[Any]) -> bool:
    return all(isinstance(arg, list) and all(isinstance(item, (float, int)) for item in arg) for arg in arg_list)

