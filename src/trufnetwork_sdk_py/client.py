from typing import Dict, List, Union, Optional, Any, TypedDict
import trufnetwork_sdk_c_bindings.exports as truf_sdk
import trufnetwork_sdk_c_bindings.go as go


class UnixRecord(TypedDict):
    date: int
    value: float

class UnixRecordBatch(TypedDict):
    stream_id: str
    inputs: List[UnixRecord]

class Record(TypedDict):
    date: str  # YYYY-MM-DD format
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

    def stream_exists(
        self, stream_id: str, data_provider: Optional[str] = None
    ) -> bool:
        """
        Check if a stream with the given stream ID exists.
        Returns True if the stream exists, False otherwise.
        """
        data_provider = self._coalesce_str(data_provider)
        return truf_sdk.StreamExists(self.client, stream_id, data_provider)
    
    def insert_record(
        self,
        stream_id: str,
        record: Dict[str, Union[str, float, int]],
        wait: bool = True
    ) -> str:
        """
        Insert a single record into a stream with the given stream ID.
        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash.

        Record is expected to have:
          - "date": str (YYYY-MM-DD) 
          - "value": float or int
        """
        go_input = truf_sdk.NewInsertRecordInput(self.client, stream_id, record["date"], record["value"])
        insert_tx_hash = truf_sdk.InsertRecord(self.client, go_input)

        print(insert_tx_hash)

        if wait:
            truf_sdk.WaitForTx(self.client, insert_tx_hash)

        return insert_tx_hash

    def insert_records(
        self,
        stream_id: str,
        records: List[Dict[str, Union[str, float, int]]],
        wait: bool = True,
    ) -> str:
        """
        Insert records into a stream with the given stream ID.
        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash.

        Each record is expected to have:
          - "date": str (YYYY-MM-DD) 
          - "value": float or int

        Note: Do not use this for inserting multiple records rapidly. Use batch inserts instead.
        Or else you can have nonce errors.
        """

        input_list = []
        for i, record in enumerate(records):
            # Create InsertRecordInput struct
            go_input = truf_sdk.NewInsertRecordInput(self.client, stream_id, record["date"], record["value"])
            input_list.append(go_input)
        
        go_input_list = truf_sdk.Slice_types_InsertRecordInput(input_list)

        insert_tx_hash = truf_sdk.InsertRecords(
            self.client,
            go_input_list
        )
        if wait:
            truf_sdk.WaitForTx(self.client, insert_tx_hash)

        return insert_tx_hash

    def batch_insert_records(
        self,
        batches: List[RecordBatch],
        wait: bool = True,
    ) -> List[str]:
        """
        Insert multiple batches of records into different streams.
        Each batch should be a dictionary containing:
            - stream_id: str
            - inputs: List[Dict[str, Union[str, float]]] where each dict has:
                - date: str (YYYY-MM-DD format)
                - value: float

        Parameters:
            - batches: List of batch dictionaries
            - wait: bool - Whether to wait for transactions to be confirmed

        Returns:
            String array containing the transaction hashes
        """
        # Create a Go slice of Batch structs
        batches_list = []
            
        for _, batch in enumerate(batches):
            # Create a Go slice for inputs
            inputs = batch["inputs"]
            input_list = []
            
            for j, record in enumerate(inputs):
                # Create InsertRecordInput struct
                go_input = truf_sdk.NewInsertRecordInput(batch["stream_id"], record["date"], record["value"])
                input_list.append(go_input)
            
            # Create Batch struct
            go_input_list = truf_sdk.Slice_types_InsertRecordInput(input_list)
            go_batch = truf_sdk.NewBatch(batch["stream_id"], go_input_list)
            batches_list.append(go_batch)

        # Call the Go function with the typed batches
        go_batches = truf_sdk.Slice_exports_Batch(batches_list)

        # Put the Go batches into the args struct
        go_args = truf_sdk.BatchInsertRecordsArgs(Batches=go_batches)

        try:
            tx_hashes = truf_sdk.BatchInsertRecords(self.client, go_args)
        except Exception as e:
            error_str = str(e)
            if "failed to estimate price" in error_str:
                raise ValueError("Request too large: The batch size exceeds the maximum allowed size") from e
            raise e

        if wait:
            for tx_hash in tx_hashes:
                truf_sdk.WaitForTx(self.client, tx_hash)

        return tx_hashes

    def get_records(
        self,
        stream_id: str,
        data_provider: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        frozen_at: Optional[str] = None,
        base_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get records from a stream with the given stream ID.
        Returns a list of records.

        Parameters:
            - stream_id: str
            - data_provider: (hex string)
            - date_from: Optional[str] (YYYY-MM-DD)
            - date_to: Optional[str] (YYYY-MM-DD)
            - frozen_at: Optional[str] (YYYY-MM-DD)
            - base_date: Optional[str] (YYYY-MM-DD)
        """
        data_provider = self._coalesce_str(data_provider)
        date_from = self._coalesce_str(date_from)
        date_to = self._coalesce_str(date_to)
        frozen_at = self._coalesce_str(frozen_at)
        base_date = self._coalesce_str(base_date)

        go_slice_of_maps = truf_sdk.GetRecords(
            self.client,
            stream_id,
            data_provider,
            date_from,
            date_to,
            frozen_at,
            base_date,
        )

        return self._go_slice_of_maps_to_list_of_dicts(go_slice_of_maps)

    def execute_procedure(
        self,
        stream_id: str,
        data_provider: str,
        procedure: str,
        args: list[list[Union[str, float, int, list[str], list[float]]]],
        wait: bool = True,
    ) -> str:
        """
        Execute an arbitrary procedure with the given stream ID.
        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash.

        Parameters:
            - stream_id: str
            - data_provider: str (hex string)
            - procedure: str
            - args: List[List[Union[str, float, int, list[str], list[float]]]]
            - wait: bool
        """
        # Transpose the 2D args
        transposed_args = list(map(list, zip(*args)))

        # Convert Python lists to Go slices with the correct type
        variadic_args = []
        for arg_list in transposed_args:
            if all(isinstance(item, str) for item in arg_list):
                variadic_args.append(
                    truf_sdk.ArgsFromStrings(go.Slice_string(arg_list))
                )
            elif all(isinstance(item, (float, int)) for item in arg_list):
                # Force to float64 so that we can pass them to ArgsFromFloats
                float_list = [float(item) for item in arg_list]
                variadic_args.append(
                    truf_sdk.ArgsFromFloats(go.Slice_float64(float_list))
                )
            # now for array of arrays
            elif all_is_list_of_strings(arg_list):
                all_slices = [go.Slice_string(item) for item in arg_list]
                variadic_args.append(
                    truf_sdk.ArgsFromStringsSlice(*all_slices)
                )
            elif all_is_list_of_floats(arg_list):
                all_slices = [go.Slice_float64(item) for item in arg_list]
                variadic_args.append(
                    truf_sdk.ArgsFromFloatsSlice(*all_slices)
                )
            else:
                raise ValueError(f"Unsupported argument types in {arg_list}")

        tx_hash = truf_sdk.ExecuteProcedure(
            self.client, stream_id, data_provider, procedure, *variadic_args
        )

        if wait:
            truf_sdk.WaitForTx(self.client, tx_hash)
        return tx_hash

    def call_procedure(
        self,
        stream_id: str,
        data_provider: Optional[str] = None,
        procedure: str = "",
        args: Optional[List[Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Call a procedure on a stream with the given stream ID.
        Returns the result of the procedure call as a list of dicts.

        Parameters:
            - stream_id: str
            - data_provider: Optional[str] (hex string)
            - procedure: str
            - args: List[Any]
        """
        data_provider = self._coalesce_str(data_provider)
        if args is None:
            args = []

        call_procedure_args = truf_sdk.NewCallProcedureArgs()
        for arg in args:
            if isinstance(arg, str):
                call_procedure_args.AddString(arg)
            elif isinstance(arg, float):
                call_procedure_args.AddFloat(arg)
            elif isinstance(arg, int):
                call_procedure_args.AddInt(arg)

        records = truf_sdk.CallProcedure(
            self.client,
            stream_id,
            data_provider,
            procedure,
            call_procedure_args
        )
        return self._records_handle_to_list_of_dicts(records)

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

    def filter_initialized_streams(
        self, 
        stream_ids: List[str], 
        data_providers: Optional[List[str]] = None,
        helper_contract_stream_id: Optional[str] = None,
        helper_contract_data_provider: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Filter out non-initialized streams from a list of stream IDs and data providers.
        
        Parameters:
            - stream_ids: List[str] - List of stream IDs to filter
            - data_providers: Optional[List[str]] - List of data providers corresponding to the stream IDs
              If None, the default data provider is used for all stream IDs.
            - helper_contract_stream_id: Optional[str] - The stream ID of the helper contract
              If None, the default helper contract stream ID is used.
            - helper_contract_data_provider: Optional[str] - The data provider of the helper contract
              If None, the default helper contract data provider is used.
            
        Returns:
            List[Dict[str, str]] - A list of dictionaries containing the initialized streams,
            each with keys 'stream_id' and 'data_provider'.
        """
        # Prepare data providers list if provided
        if data_providers is None:
            data_providers = [""] * len(stream_ids)
        
        # Convert Python lists to Go slices
        go_stream_ids = go.Slice_string(stream_ids)
        go_data_providers = go.Slice_string(data_providers)
        
        # Call the FilterInitialized function
        helper_stream_id = self._coalesce_str(helper_contract_stream_id)
        helper_provider = self._coalesce_str(helper_contract_data_provider)
        
        go_slice_of_maps = truf_sdk.FilterInitialized(
            self.client,
            go_stream_ids,
            go_data_providers,
            helper_stream_id,
            helper_provider
        )
        
        return self._go_slice_of_maps_to_list_of_dicts(go_slice_of_maps)

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
        after_date: Optional[str] = None,
        frozen_at: Optional[str] = None,
    ) -> Optional[Dict[str, Union[str, float]]]:
        """
        Get the first record of a stream after a given date.
        
        Parameters:
            - stream_id: str
            - data_provider: Optional[str] (hex string)
            - after_date: Optional[str] (YYYY-MM-DD)
            - frozen_at: Optional[str] (YYYY-MM-DD)
            
        Returns:
            Optional[Dict[str, Union[str, float]]] - A dictionary containing 'date' and 'value' if found, None otherwise
        """
        data_provider = self._coalesce_str(data_provider)
        after_date = self._coalesce_str(after_date)
        frozen_at = self._coalesce_str(frozen_at)

        result = truf_sdk.GetFirstRecord(
            self.client,
            stream_id,
            data_provider,
            after_date,
            frozen_at,
        )
        
        # Convert the result to a Python dict and convert the value to float
        record = dict(result.items())
        # nil from go is an empty map, not None
        if not record:
            return None
        record["value"] = float(record["value"])
        return record

    def get_first_record_unix(
        self,
        stream_id: str,
        data_provider: Optional[str] = None,
        after_date: Optional[int] = None,
        frozen_at: Optional[int] = None,
    ) -> Optional[Dict[str, Union[int, float]]]:
        """
        Get the first record of a stream after a given Unix timestamp.
        
        Parameters:
            - stream_id: str
            - data_provider: Optional[str] (hex string)
            - after_date: Optional[int] (Unix timestamp)
            - frozen_at: Optional[int] (Unix timestamp)
            
        Returns:
            Optional[Dict[str, Union[int, float]]] - A dictionary containing 'date' (Unix timestamp) and 'value' if found, None otherwise
        """
        data_provider = self._coalesce_str(data_provider)
        after_date = self._coalesce_int(after_date)
        frozen_at = self._coalesce_int(frozen_at)

        result = truf_sdk.GetFirstRecordUnix(
            self.client,
            stream_id,
            data_provider,
            after_date,
            frozen_at,
        )
        
        # If no record found, result will be None or an empty map
        if result is None or not result:
            return None
            
        try:
            # Convert the result to a Python dict and convert the values
            record = dict(result.items())
            # Convert string values to appropriate types
            record["date"] = int(record["date"])
            record["value"] = float(record["value"])
            return record
        except (AttributeError, KeyError, ValueError) as e:
            # If any conversion fails, return None
            return None

def all_is_list_of_strings(arg_list: list[Any]) -> bool:
    return all(isinstance(arg, list) and all(isinstance(item, str) for item in arg) for arg in arg_list)

def all_is_list_of_floats(arg_list: list[Any]) -> bool:
    return all(isinstance(arg, list) and all(isinstance(item, (float, int)) for item in arg) for arg in arg_list)

