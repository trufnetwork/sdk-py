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
	"github.com/kwilteam/kwil-db/core/types/decimal"
	"github.com/kwilteam/kwil-db/core/types/transactions"
	"github.com/pkg/errors"
	"github.com/trufnetwork/sdk-go/core/tnclient"
	"github.com/trufnetwork/sdk-go/core/types"
	"github.com/trufnetwork/sdk-go/core/util"
)

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

	// Process the inputs
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

// processInsertInputs processes the input dates and values and returns a slice of InsertRecordInput.
func processInsertInputs(inputDates []string, inputValues []float64) ([]types.InsertRecordInput, error) {
	// Check that the lengths of the input dates and values are the same
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

// ExecuteProcedure executes a procedure on the stream with the given stream ID, data provider, and procedure.
func ExecuteProcedure(client *tnclient.Client, streamId string, dataProvider string, procedure string, args ...ProcedureArgs) (string, error) {
	ctx := context.Background()
	streamIdTyped, err := util.NewStreamId(streamId)
	if err != nil {
		return "", errors.Wrap(err, "error creating stream id")
	}

	var dataProviderTyped util.EthereumAddress
	if dataProvider == "" {
		dataProviderTyped = client.Address()
	} else {
		dataProviderTyped, err = util.NewEthereumAddressFromString(dataProvider)
		if err != nil {
			return "", errors.Wrap(err, "error creating data provider")
		}
	}
	streamLocator := types.StreamLocator{
		StreamId:     *streamIdTyped,
		DataProvider: dataProviderTyped,
	}
	stream, err := client.LoadStream(streamLocator)
	if err != nil {
		return "", errors.Wrap(err, "error loading stream")
	}

	// Transpose the args to match expected format
	expectedBatchLength := len(args[0])
	transposedArgs := make([][]any, expectedBatchLength)
	for _, arg := range args {
		if len(arg) != expectedBatchLength {
			return "", errors.New("all slices must have the same length")
		}
		for i, argSlice := range arg {
			transposedArgs[i] = append(transposedArgs[i], argSlice)
		}
	}

	txHash, err := stream.ExecuteProcedure(ctx, procedure, transposedArgs)
	if err != nil {
		return "", errors.Wrap(err, "error executing procedure")
	}
	return txHash.Hex(), nil
}

func StreamExists(client *tnclient.Client, streamId string, dataProvider string) (bool, error) {
	streamIdTyped, err := util.NewStreamId(streamId)
	if err != nil {
		return false, errors.Wrap(err, "error creating stream id")
	}

	// if there's no data provider, use the client's own data provider
	var dataProviderTyped util.EthereumAddress
	if dataProvider == "" {
		dataProviderTyped = client.Address()
	} else {
		dataProviderTyped, err = util.NewEthereumAddressFromString(dataProvider)
		if err != nil {
			return false, errors.Wrap(err, "error creating data provider")
		}
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
	// Parse dates
	dateFromTyped, err := parseDate(dateFrom)
	if err != nil {
		return nil, err
	}
	dateToTyped, err := parseDate(dateTo)
	if err != nil {
		return nil, err
	}

	ctx := context.Background()
	streamIdTyped := util.GenerateStreamId(streamId)

	// If dataProvider is empty, use the client's own data provider
	var dataProviderTyped util.EthereumAddress
	if dataProvider == "" {
		dataProviderTyped = client.Address()
	} else {
		dataProviderTyped, err = util.NewEthereumAddressFromString(dataProvider)
		if err != nil {
			return nil, fmt.Errorf("invalid data provider '%s': %w", dataProvider, err)
		}
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
	})
	if err != nil {
		return nil, err
	}

	// Convert records to map[string]string
	// independently of the type of the record and the fields
	result := make([]map[string]string, len(records))
	for i, record := range records {
		m := make(map[string]string)
		val := reflect.ValueOf(record)
		typ := val.Type()
		for j := 0; j < val.NumField(); j++ {
			field := typ.Field(j)
			valAsStr := convertToString(val.Field(j).Interface())
			m[field.Name] = valAsStr
		}
		result[i] = m
	}

	return result, nil
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
		// Log a warning and return the default string representation
		log.Printf("Warning: Failed to convert argument to string from type %T: %v\n", val, val)
		return fmt.Sprintf("%v", val)
	}
}

// StreamType constants.
const (
	StreamTypeComposed  types.StreamType = types.StreamTypeComposed
	StreamTypePrimitive types.StreamType = types.StreamTypePrimitive
)

// WaitForTx waits for the transaction with the given hash to be confirmed.
func WaitForTx(client *tnclient.Client, txHashHex string) error {
	ctx := context.Background()

	// Normalize txHash as bytes
	txHash, err := hex.DecodeString(strings.TrimPrefix(txHashHex, "0x"))
	if err != nil {
		return fmt.Errorf("invalid transaction hash '%s': %w", txHashHex, err)
	}

	tx, err := client.WaitForTx(ctx, txHash, 1*time.Second)
	if err != nil {
		return err
	}

	// Check if tx has success code
	if tx.TxResult.Code != uint32(transactions.CodeOk) {
		return fmt.Errorf("transaction failed: %s", tx.TxResult.Log)
	}
	return nil
}

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
