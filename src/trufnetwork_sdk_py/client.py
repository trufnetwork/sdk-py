from typing import Dict, List, Union, Optional, Any, TypedDict
import trufnetwork_sdk_c_bindings.exports as truf_sdk
import trufnetwork_sdk_c_bindings.go as go


class UnixRecord(TypedDict):
    date: int
    value: float

class UnixRecordBatch(TypedDict):
    stream_id: str
    inputs: List[UnixRecord]

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
        Helper to coalesce an optional integer into a sentinel value (default=-1).
        If val is None, return default; otherwise return val.
        """
        return val if val is not None else default

    def _go_slice_of_maps_to_list_of_dicts(
        self, go_slice: Any
    ) -> List[Dict[str, Any]]:
        """
        Helper to convert a Go slice of maps into a Python list of dicts.
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

    def init_stream(self, stream_id: str, wait: bool = True) -> str:
        """
        Initialize a stream with the given stream ID.
        If wait is True, it will wait for the transaction to be confirmed.
        Returns the transaction hash.
        """
        init_tx_hash = truf_sdk.InitStream(self.client, stream_id)
        if wait:
            truf_sdk.WaitForTx(self.client, init_tx_hash)
        return init_tx_hash

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
        """
        dates = [record["date"] for record in records]
        values = [record["value"] for record in records]

        insert_tx_hash = truf_sdk.InsertRecords(
            self.client,
            stream_id,
            go.Slice_string(dates),
            go.Slice_float64([float(v) for v in values]),
        )
        if wait:
            truf_sdk.WaitForTx(self.client, insert_tx_hash)
        return insert_tx_hash

    def insert_records_unix(
        self,
        stream_id: str,
        records: List[Dict[str, Union[str, float, int]]],
        wait: bool = True,
    ) -> str:
        """
        Insert records into a stream with the given stream ID using Unix timestamps.
        """
        dates = [record["date"] for record in records]
        values = [record["value"] for record in records]

        insert_tx_hash = truf_sdk.InsertRecordsUnix(
            self.client, stream_id, go.Slice_int(dates), go.Slice_float64([float(v) for v in values])
        )
        if wait:
            truf_sdk.WaitForTx(self.client, insert_tx_hash)
        return insert_tx_hash

    def batch_insert_records_unix(
        self,
        batches: List[UnixRecordBatch],
        wait: bool = True,
    ) -> List[str]:
        """
        Insert multiple batches of records into different streams using Unix timestamps.
        Each batch should be a dictionary containing:
            - stream_id: str
            - inputs: List[Dict[str, Union[int, float]]] where each dict has:
                - date: int (Unix timestamp)
                - value: float

        Parameters:
            - batches: List of batch dictionaries
            - wait: bool - Whether to wait for transactions to be confirmed

        Returns:
            List of transaction hashes in the same order as the input batches
        """
        # Create a Go slice of UnixBatch structs
        batches_list = []
            
        for _, batch in enumerate(batches):
            # Create a Go slice for inputs
            inputs = batch["inputs"]
            input_list = []
            
            for j, record in enumerate(inputs):
                # Create InsertRecordUnixInput struct
                go_input = truf_sdk.NewInsertRecordUnixInput(record["date"], record["value"])
                input_list.append(go_input)
            
            # Create UnixBatch struct
            go_input_list = truf_sdk.Slice_s2_types_InsertRecordUnixInput(input_list)
            go_batch = truf_sdk.NewUnixBatch(batch["stream_id"], go_input_list)
            batches_list.append(go_batch)

        # Call the Go function with the typed batches
        go_batches = truf_sdk.Slice_exports_UnixBatch(batches_list)
        tx_hashes = truf_sdk.BatchInsertRecordsUnix(self.client, go_batches)
        
        if wait:
            for tx_hash in tx_hashes:
                truf_sdk.WaitForTx(self.client, tx_hash)
        
        # Convert Go slice to Python list
        return list(tx_hashes)

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
            - data_provider: Optional[str] (hex string)
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

    def get_records_unix(
        self,
        stream_id: str,
        data_provider: Optional[str] = None,
        date_from: Optional[int] = None,
        date_to: Optional[int] = None,
        frozen_at: Optional[int] = None,
        base_date: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get records from a stream with the given stream ID using Unix timestamps.
        Returns a list of records.
        """
        data_provider = self._coalesce_str(data_provider)
        date_from = self._coalesce_int(date_from)
        date_to = self._coalesce_int(date_to)
        frozen_at = self._coalesce_int(frozen_at)
        base_date = self._coalesce_int(base_date)

        go_slice_of_maps = truf_sdk.GetRecordsUnix(
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
        args: List[List[Union[str, float, int]]],
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
            - args: List[List[Union[str, float, int]]]
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

        records = truf_sdk.CallProcedure(
            self.client,
            stream_id,
            data_provider,
            procedure,
            *args
        )
        return self._records_handle_to_list_of_dicts(records)

    def wait_for_tx(self, tx_hash: str) -> None:
        """
        Wait for a transaction to be confirmed given its hash.
        """
        truf_sdk.WaitForTx(self.client, tx_hash)

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
