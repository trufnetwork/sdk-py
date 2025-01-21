package exports

import (
	"context"
	"encoding/hex"
	"fmt"
	"log"
	"reflect"
	"strconv"
	"strings"
	"time"

	"github.com/cockroachdb/apd/v3"
	"github.com/golang-sql/civil"
	"github.com/kwilteam/kwil-db/core/crypto"
	"github.com/kwilteam/kwil-db/core/crypto/auth"
	kwilTypes "github.com/kwilteam/kwil-db/core/types"
	"github.com/kwilteam/kwil-db/core/types/client"
	kwilClientType "github.com/kwilteam/kwil-db/core/types/client"
	"github.com/kwilteam/kwil-db/core/types/decimal"
	"github.com/kwilteam/kwil-db/core/types/transactions"
	"github.com/pkg/errors"
	"github.com/trufnetwork/sdk-go/core/tnclient"
	"github.com/trufnetwork/sdk-go/core/types"
	"github.com/trufnetwork/sdk-go/core/util"
)

// StreamType constants.
const (
	StreamTypeComposed      types.StreamType = types.StreamTypeComposed
	StreamTypePrimitive     types.StreamType = types.StreamTypePrimitive
	StreamTypePrimitiveUnix types.StreamType = types.StreamTypePrimitiveUnix
)

// ProcedureArgs represents a slice of arguments for a procedure.
type ProcedureArgs []any

// ArgsFromStrings converts a slice of strings to ProcedureArgs.
func ArgsFromStrings(values []string) ProcedureArgs {
	var anySlice []any
	for _, v := range values {
		anySlice = append(anySlice, v)
	}
	return anySlice
}

// ArgsFromFloats converts a slice of floats to ProcedureArgs.
func ArgsFromFloats(values []float64) ProcedureArgs {
	var anySlice []any
	for _, v := range values {
		anySlice = append(anySlice, v)
	}
	return anySlice
}

// NewClient creates a new TN client with the given provider and private key.
func NewClient(provider string, privateKey string) (*tnclient.Client, error) {
	ctx := context.Background()

	signer, err := createSigner(privateKey)
	if err != nil {
		return nil, errors.Wrap(err, "error creating signer")
	}

	client, err := tnclient.NewClient(ctx, provider, tnclient.WithSigner(signer))
	if err != nil {
		return nil, errors.Wrap(err, "error creating client")
	}
	return client, nil
}

func GetCurrentAccount(client *tnclient.Client) (string, error) {
	address := client.Address()
	return address.Address(), nil
}

func GetNextNonce(client *tnclient.Client) (int64, error) {
	kwilClient := client.GetKwilClient()
	acct, err := kwilClient.GetAccount(context.Background(), client.Signer.Identity(), kwilTypes.AccountStatusPending)
	if err != nil {
		return 0, err
	}
	return acct.Nonce + 1, nil
}

// createSigner creates an EthPersonalSigner from a private key.
func createSigner(privateKey string) (*auth.EthPersonalSigner, error) {
	pk, err := crypto.Secp256k1PrivateKeyFromHex(privateKey)
	if err != nil {
		return nil, errors.Wrap(err, "failed to create signer")
	}
	signer := &auth.EthPersonalSigner{Key: *pk}
	return signer, nil
}

// GenerateStreamId generates a stream ID from the given name.
func GenerateStreamId(name string) string {
	streamId := util.GenerateStreamId(name)
	return streamId.String()
}

// DeployStream deploys a stream with the given stream ID and stream type.
func DeployStream(client *tnclient.Client, streamId string, streamType types.StreamType) (string, error) {
	ctx := context.Background()

	streamIdTyped, err := util.NewStreamId(streamId)
	if err != nil {
		return "", errors.Wrap(err, "error creating stream id")
	}

	deployTxHash, err := client.DeployStream(ctx, *streamIdTyped, streamType)
	if err != nil {
		return "", errors.Wrap(err, "error deploying stream")
	}
	return deployTxHash.Hex(), nil
}

// DestroyStream destroys the stream with the given stream ID.
func DestroyStream(client *tnclient.Client, streamId string) (string, error) {
	ctx := context.Background()

	streamIdTyped, err := util.NewStreamId(streamId)
	if err != nil {
		return "", errors.Wrap(err, "error creating stream id")
	}

	destroyTxHash, err := client.DestroyStream(ctx, *streamIdTyped)
	if err != nil {
		return "", errors.Wrap(err, "error destroying stream")
	}
	return destroyTxHash.Hex(), nil
}

// InitStream initializes the stream with the given stream ID.
func InitStream(client *tnclient.Client, streamId string) (string, error) {
	ctx := context.Background()

	streamIdTyped, err := util.NewStreamId(streamId)
	if err != nil {
		return "", errors.Wrap(err, "error creating stream id")
	}

	streamLocator := client.OwnStreamLocator(*streamIdTyped)
	stream, err := client.LoadStream(streamLocator)
	if err != nil {
		return "", errors.Wrap(err, "error loading stream")
	}

	txHash, err := stream.InitializeStream(ctx)
	if err != nil {
		return "", errors.Wrap(err, "error initializing stream")
	}
	return txHash.Hex(), nil
}

// InsertRecords inserts records into the stream with the given stream ID.
func InsertRecords(client *tnclient.Client, streamId string, inputDates []string, inputValues []float64) (string, error) {
	ctx := context.Background()

	processedInputs, err := processInsertInputs(inputDates, inputValues)
	if err != nil {
		return "", errors.Wrap(err, "error processing insert inputs")
	}

	streamIdTyped, err := util.NewStreamId(streamId)
	if err != nil {
		return "", errors.Wrap(err, "error creating stream id")
	}

	streamLocator := client.OwnStreamLocator(*streamIdTyped)
	primitiveStream, err := client.LoadPrimitiveStream(streamLocator)
	if err != nil {
		return "", errors.Wrap(err, "error loading primitive stream")
	}

	txHash, err := primitiveStream.InsertRecords(ctx, processedInputs)
	if err != nil {
		return "", errors.Wrap(err, "error inserting records")
	}
	return txHash.Hex(), nil
}

// InsertRecordsUnix inserts records into the stream with the given stream ID using Unix timestamps.
func InsertRecordsUnix(client *tnclient.Client, streamId string, inputDates []int, inputValues []float64) (string, error) {
	ctx := context.Background()

	processedInputs, err := processInsertInputsUnix(inputDates, inputValues)
	if err != nil {
		return "", errors.Wrap(err, "error processing insert inputs")
	}

	streamIdTyped, err := util.NewStreamId(streamId)
	if err != nil {
		return "", errors.Wrap(err, "error creating stream id")
	}

	streamLocator := client.OwnStreamLocator(*streamIdTyped)
	primitiveStream, err := client.LoadPrimitiveStream(streamLocator)
	if err != nil {
		return "", errors.Wrap(err, "error loading primitive stream")
	}

	txHash, err := primitiveStream.InsertRecordsUnix(ctx, processedInputs)
	if err != nil {
		return "", errors.Wrap(err, "error inserting records")
	}
	return txHash.Hex(), nil
}

type UnixBatch struct {
	StreamId string                        `json:"stream_id"`
	Inputs   []types.InsertRecordUnixInput `json:"inputs"`
}

// NewUnixBatch creates a new UnixBatch struct
func NewUnixBatch(streamId string, inputs []types.InsertRecordUnixInput) UnixBatch {
	return UnixBatch{
		StreamId: streamId,
		Inputs:   inputs,
	}
}

// NewInsertRecordUnixInput creates a new InsertRecordUnixInput struct
func NewInsertRecordUnixInput(dateVal int, val float64) types.InsertRecordUnixInput {
	return types.InsertRecordUnixInput{
		DateValue: dateVal,
		Value:     val,
	}
}

func BatchInsertRecordsUnix(client *tnclient.Client, batches []UnixBatch) ([]string, error) {
	ctx := context.Background()
	txHashes := make([]string, len(batches))

	nextNonce, err := GetNextNonce(client)
	if err != nil {
		return nil, errors.Wrap(err, "error getting next nonce")
	}

	for i, batch := range batches {
		streamIdTyped, err := util.NewStreamId(batch.StreamId)
		if err != nil {
			return nil, errors.Wrap(err, "error creating stream id")
		}

		streamLocator := client.OwnStreamLocator(*streamIdTyped)
		primitiveStream, err := client.LoadPrimitiveStream(streamLocator)
		if err != nil {
			return nil, errors.Wrap(err, "error loading primitive stream")
		}

		txHash, err := primitiveStream.InsertRecordsUnix(ctx, batch.Inputs, kwilClientType.WithNonce(int64(nextNonce)))
		if err != nil {
			return nil, errors.Wrap(err, "error inserting records")
		}
		txHashes[i] = txHash.Hex()
		nextNonce++
	}

	return txHashes, nil
}

// processInsertInputs processes the input dates and values and returns a slice of InsertRecordInput.
func processInsertInputs(inputDates []string, inputValues []float64) ([]types.InsertRecordInput, error) {
	if len(inputDates) != len(inputValues) {
		return nil, errors.New("input dates and values must have the same length")
	}

	var processedInputs []types.InsertRecordInput
	for i, inputDate := range inputDates {
		dateTime, err := time.Parse("2006-01-02", inputDate)
		if err != nil {
			return nil, errors.Wrap(err, fmt.Sprintf("invalid date format '%s'", inputDate))
		}

		processedInputs = append(processedInputs, types.InsertRecordInput{
			DateValue: civil.DateOf(dateTime),
			Value:     inputValues[i],
		})
	}
	return processedInputs, nil
}

// processInsertInputsUnix processes the input dates and values and returns a slice of InsertRecordUnixInput.
func processInsertInputsUnix(inputDates []int, inputValues []float64) ([]types.InsertRecordUnixInput, error) {
	if len(inputDates) != len(inputValues) {
		return nil, errors.New("input dates and values must have the same length")
	}

	var processedInputs []types.InsertRecordUnixInput
	for i, inputDate := range inputDates {
		dateTime := time.Unix(int64(inputDate), 0)

		processedInputs = append(processedInputs, types.InsertRecordUnixInput{
			DateValue: int(dateTime.Unix()),
			Value:     inputValues[i],
		})
	}
	return processedInputs, nil
}

// ExecuteProcedure executes a procedure on the stream with the given stream ID, data provider, and procedure.
func ExecuteProcedure(client *tnclient.Client, streamId string, dataProvider string, procedure string, args ...ProcedureArgs) (string, error) {
	ctx := context.Background()

	streamIdTyped, err := util.NewStreamId(streamId)
	if err != nil {
		return "", errors.Wrap(err, "error creating stream id")
	}

	dataProviderTyped, err := parseDataProvider(client, dataProvider)
	if err != nil {
		return "", errors.Wrap(err, "error creating data provider")
	}

	streamLocator := types.StreamLocator{
		StreamId:     *streamIdTyped,
		DataProvider: dataProviderTyped,
	}

	stream, err := client.LoadStream(streamLocator)
	if err != nil {
		return "", errors.Wrap(err, "error loading stream")
	}

	// Transpose arguments so the procedure sees them in the expected format.
	if len(args) == 0 {
		return "", errors.New("no procedure arguments provided")
	}
	expectedBatchLength := len(args[0])
	transposedArgs := make([][]any, expectedBatchLength)

	for _, arg := range args {
		if len(arg) != expectedBatchLength {
			return "", errors.New("all slices must have the same length")
		}
		for i, item := range arg {
			transposedArgs[i] = append(transposedArgs[i], item)
		}
	}

	txHash, err := stream.ExecuteProcedure(ctx, procedure, transposedArgs)
	if err != nil {
		return "", errors.Wrap(err, "error executing procedure")
	}
	return txHash.Hex(), nil
}

// CallProcedure calls a procedure on the stream with the given stream ID, data provider, and procedure.
func CallProcedure(client *tnclient.Client, streamId string, dataProvider string, procedure string, args ...any) (*client.Records, error) {
	ctx := context.Background()

	streamIdTyped, err := util.NewStreamId(streamId)
	if err != nil {
		return nil, errors.Wrap(err, "error creating stream id")
	}

	dataProviderTyped, err := parseDataProvider(client, dataProvider)
	if err != nil {
		return nil, errors.Wrap(err, "error creating data provider")
	}

	streamLocator := types.StreamLocator{
		StreamId:     *streamIdTyped,
		DataProvider: dataProviderTyped,
	}

	stream, err := client.LoadStream(streamLocator)
	if err != nil {
		return nil, errors.Wrap(err, "error loading stream")
	}

	return stream.CallProcedure(ctx, procedure, args)
}

// StreamExists checks if the stream with the given ID (and optional data provider) exists.
func StreamExists(client *tnclient.Client, streamId string, dataProvider string) (bool, error) {
	streamIdTyped, err := util.NewStreamId(streamId)
	if err != nil {
		return false, errors.Wrap(err, "error creating stream id")
	}

	dataProviderTyped, err := parseDataProvider(client, dataProvider)
	if err != nil {
		return false, errors.Wrap(err, "error creating data provider")
	}

	streamLocator := types.StreamLocator{
		StreamId:     *streamIdTyped,
		DataProvider: dataProviderTyped,
	}

	_, err = client.LoadStream(streamLocator)
	return err == nil, nil
}

// GetRecords retrieves records from the stream with the given stream ID.
func GetRecords(
	client *tnclient.Client,
	streamId string,
	dataProvider string,
	dateFrom string,
	dateTo string,
	frozenAt string,
	baseDate string,
) ([]map[string]string, error) {

	dateFromTyped, err := parseDate(dateFrom)
	if err != nil {
		return nil, err
	}
	dateToTyped, err := parseDate(dateTo)
	if err != nil {
		return nil, err
	}

	ctx := context.Background()

	// For retrieving, we generate a StreamId from the string.
	// If your usage requires an existing ID, use `util.NewStreamId` instead.
	streamIdTyped := util.GenerateStreamId(streamId)

	dataProviderTyped, err := parseDataProvider(client, dataProvider)
	if err != nil {
		return nil, fmt.Errorf("invalid data provider '%s': %w", dataProvider, err)
	}

	streamLocator := types.StreamLocator{
		StreamId:     streamIdTyped,
		DataProvider: dataProviderTyped,
	}

	stream, err := client.LoadPrimitiveStream(streamLocator)
	if err != nil {
		return nil, err
	}

	records, err := stream.GetRecord(ctx, types.GetRecordInput{
		DateFrom: dateFromTyped,
		DateTo:   dateToTyped,
		// frozenAt and baseDate are not used here.
		// If needed, add them to GetRecordInput in the SDK & pass them here.
	})
	if err != nil {
		return nil, err
	}

	return recordsToMapSlice(records), nil
}

// GetRecordsUnix retrieves records from the stream with the given stream ID using Unix timestamps.
func GetRecordsUnix(
	client *tnclient.Client,
	streamId string,
	dataProvider string,
	dateFrom int,
	dateTo int,
	frozenAt int,
	baseDate int,
) ([]map[string]string, error) {

	ctx := context.Background()

	streamIdTyped := util.GenerateStreamId(streamId)
	dataProviderTyped, err := parseDataProvider(client, dataProvider)
	if err != nil {
		return nil, fmt.Errorf("invalid data provider '%s': %w", dataProvider, err)
	}

	streamLocator := types.StreamLocator{
		StreamId:     streamIdTyped,
		DataProvider: dataProviderTyped,
	}

	stream, err := client.LoadPrimitiveStream(streamLocator)
	if err != nil {
		return nil, err
	}

	frozenAtTime, err := parseUnixTime(frozenAt)
	if err != nil {
		return nil, err
	}

	records, err := stream.GetRecordUnix(ctx, types.GetRecordUnixInput{
		DateFrom: intOrNil(dateFrom),
		DateTo:   intOrNil(dateTo),
		FrozenAt: frozenAtTime, // pointer or nil
		BaseDate: intOrNil(baseDate),
	})
	if err != nil {
		return nil, err
	}

	return recordsToMapSlice(records), nil
}

// GetIndexUnix retrieves an index from the stream with the given stream ID using Unix timestamps.
func GetIndexUnix(
	client *tnclient.Client,
	streamId string,
	dataProvider string,
	dateFrom int,
	dateTo int,
	frozenAt int,
	baseDate int,
) ([]map[string]string, error) {

	ctx := context.Background()

	streamIdTyped := util.GenerateStreamId(streamId)
	dataProviderTyped, err := parseDataProvider(client, dataProvider)
	if err != nil {
		return nil, fmt.Errorf("invalid data provider '%s': %w", dataProvider, err)
	}

	streamLocator := types.StreamLocator{
		StreamId:     streamIdTyped,
		DataProvider: dataProviderTyped,
	}

	stream, err := client.LoadPrimitiveStream(streamLocator)
	if err != nil {
		return nil, err
	}

	frozenAtTime, err := parseUnixTime(frozenAt)
	if err != nil {
		return nil, err
	}

	index, err := stream.GetIndexUnix(ctx, types.GetIndexUnixInput{
		DateFrom: intOrNil(dateFrom),
		DateTo:   intOrNil(dateTo),
		FrozenAt: frozenAtTime,
		BaseDate: intOrNil(baseDate),
	})
	if err != nil {
		return nil, err
	}

	return recordsToMapSlice(index), nil
}

// WaitForTx waits for the transaction with the given hash to be confirmed.
func WaitForTx(client *tnclient.Client, txHashHex string) error {
	ctx := context.Background()

	txHash, err := hex.DecodeString(strings.TrimPrefix(txHashHex, "0x"))
	if err != nil {
		return fmt.Errorf("invalid transaction hash '%s': %w", txHashHex, err)
	}

	tx, err := client.WaitForTx(ctx, txHash, 1*time.Second)
	if err != nil {
		return err
	}

	// Check if tx was successful
	if tx.TxResult.Code != uint32(transactions.CodeOk) {
		return fmt.Errorf("transaction failed: %s", tx.TxResult.Log)
	}
	return nil
}

/*****************************************
 *            Helper Functions           *
 *****************************************/

// parseDataProvider checks if dataProvider is empty; if so, returns client's own address.
func parseDataProvider(client *tnclient.Client, dataProvider string) (util.EthereumAddress, error) {
	if dataProvider == "" {
		return client.Address(), nil
	}
	return util.NewEthereumAddressFromString(dataProvider)
}

// parseDate parses a date string in YYYY-MM-DD format and returns a *civil.Date.
func parseDate(dateStr string) (*civil.Date, error) {
	if dateStr == "" {
		return nil, nil
	}
	date, err := civil.ParseDate(dateStr)
	if err != nil {
		return nil, fmt.Errorf("invalid date format '%s': %w", dateStr, err)
	}
	return &date, nil
}

// parseUnixTime parses a Unix timestamp (int). If value is -1, it returns nil.
func parseUnixTime(value int) (*time.Time, error) {
	if value == -1 {
		return nil, nil
	}
	t := time.Unix(int64(value), 0)
	return &t, nil
}

// intOrNil returns a pointer to value unless it's -1, in which case it returns nil.
func intOrNil(value int) *int {
	if value == -1 {
		return nil
	}
	return &value
}

// recordsToMapSlice converts a slice of records (structs) to a slice of map[string]string.
func recordsToMapSlice(records interface{}) []map[string]string {
	v := reflect.ValueOf(records)
	if v.Kind() != reflect.Slice {
		return nil
	}

	length := v.Len()
	out := make([]map[string]string, length)

	for i := 0; i < length; i++ {
		recordVal := v.Index(i)
		out[i] = structToMapString(recordVal.Interface())
	}

	return out
}

// structToMapString converts a struct to a map[string]string by reflecting over its fields.
func structToMapString(record any) map[string]string {
	result := make(map[string]string)
	val := reflect.ValueOf(record)
	typ := val.Type()

	for i := 0; i < val.NumField(); i++ {
		field := typ.Field(i)
		valAsStr := convertToString(val.Field(i).Interface())
		result[field.Name] = valAsStr
	}
	return result
}

// convertToString converts various data types to a string representation.
func convertToString(val any) string {
	switch v := val.(type) {
	case string:
		return v
	case int:
		return strconv.Itoa(v)
	case float64:
		return strconv.FormatFloat(v, 'f', -1, 64)
	case decimal.Decimal:
		return v.String()
	case apd.Decimal:
		return v.String()
	case civil.Date:
		return v.String()
	case fmt.Stringer:
		return v.String()
	default:
		log.Printf("Warning: Failed to convert argument to string from type %T: %v\n", val, val)
		return fmt.Sprintf("%v", val)
	}
}
