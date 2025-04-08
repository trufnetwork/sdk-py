package exports

import (
	"context"
	"fmt"
	"log"
	"reflect"
	"strconv"
	"time"

	"github.com/cockroachdb/apd/v3"
	"github.com/golang-sql/civil"
	"github.com/kwilteam/kwil-db/core/crypto"
	"github.com/kwilteam/kwil-db/core/crypto/auth"
	kwilTypes "github.com/kwilteam/kwil-db/core/types"
	"github.com/pkg/errors"
	"github.com/trufnetwork/sdk-go/core/contractsapi"
	"github.com/trufnetwork/sdk-go/core/tnclient"
	"github.com/trufnetwork/sdk-go/core/types"
	"github.com/trufnetwork/sdk-go/core/util"
	"google.golang.org/genproto/googleapis/type/decimal"
)

// StreamType constants.
const (
	StreamTypeComposed  types.StreamType = types.StreamTypeComposed
	StreamTypePrimitive types.StreamType = types.StreamTypePrimitive
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

// using variadic to make it easier to consume from python
func ArgsFromStringsSlice(values ...[]string) ProcedureArgs {
	var anySlice []any
	for _, v := range values {
		anySlice = append(anySlice, v)
	}
	return anySlice
}

// using variadic to make it easier to consume from python
func ArgsFromFloatsSlice(values ...[]float64) ProcedureArgs {
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
	return deployTxHash.String(), nil
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
	return destroyTxHash.String(), nil
}

// InsertRecord inserts single record into the stream with the given stream ID.
func InsertRecord(client *tnclient.Client, input types.InsertRecordInput) (string, error) {
	ctx := context.Background()

	primitiveStream, err := client.LoadPrimitiveActions()
	if err != nil {
		return "", errors.Wrap(err, "error loading primitive stream")
	}

	txHash, err := primitiveStream.InsertRecord(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "error inserting record")
	}
	return txHash.String(), nil
}

// InsertRecords inserts records into the stream with the given stream ID.
func InsertRecords(client *tnclient.Client, inputs []types.InsertRecordInput) (string, error) {
	ctx := context.Background()

	primitiveStream, err := client.LoadPrimitiveActions()
	if err != nil {
		return "", errors.Wrap(err, "error loading primitive stream")
	}

	txHash, err := primitiveStream.InsertRecords(ctx, inputs)
	if err != nil {
		return "", errors.Wrap(err, "error inserting records")
	}
	return txHash.String(), nil
}

// NewInsertRecordInput creates a new InsertRecordInput struct
func NewInsertRecordInput(client *tnclient.Client, streamId string, dateVal string, val float64) types.InsertRecordInput {
	date, err := parseDate(dateVal)
	if err != nil {
		log.Printf("Warning: Failed to parse date %s: %v\n", dateVal, err)
		return types.InsertRecordInput{}
	}

	dataProvider, err := GetCurrentAccount(client)
	if err != nil {
		log.Printf("Warning: Failed to get data provider: %v\n", err)
		return types.InsertRecordInput{}
	}

	return types.InsertRecordInput{
		StreamId:     streamId,
		DataProvider: dataProvider,
		EventTime:    *date,
		Value:        val,
	}
}

// NewGetRecordInput creates a new GetRecordInput struct
func NewGetRecordInput(
	client *tnclient.Client,
	streamId string,
	dataProvider string,
	fromVal string,
	toVal string,
	frozenVal string,
	baseDateVal string,
) types.GetRecordInput {
	result := types.GetRecordInput{
		StreamId:     streamId,
		DataProvider: dataProvider,
	}

	if dataProvider == "" {
		currentAccount, err := GetCurrentAccount(client)
		if err != nil {
			return result
		}
		result.DataProvider = currentAccount
	}
	from, err := parseDate(fromVal)
	if err != nil {
		return result
	}
	to, err := parseDate(toVal)
	if err != nil {
		return result
	}
	frozenAt, err := parseDate(frozenVal)
	if err != nil {
		return result
	}
	baseDate, err := parseDate(baseDateVal)
	if err != nil {
		return result
	}

	result.From = from
	result.To = to
	result.FrozenAt = frozenAt
	result.BaseDate = baseDate

	return result
}

// GetRecords retrieves records from the stream with the given stream ID.
func GetRecords(client *tnclient.Client, input types.GetRecordInput) ([]map[string]string, error) {
	ctx := context.Background()
	stream, err := client.LoadPrimitiveActions()
	if err != nil {
		return nil, err
	}

	records, err := stream.GetRecord(ctx, input)
	if err != nil {
		return nil, err
	}

	return recordsToMapSlice(records), nil
}

func GetType(client *tnclient.Client, streamId string, dataProvider string) (types.StreamType, error) {
	streamIdTyped, err := util.NewStreamId(streamId)
	ctx := context.Background()
	if err != nil {
		return types.StreamTypePrimitive, fmt.Errorf("invalid stream id '%s': %w", streamId, err)
	}

	dataProviderTyped, err := parseDataProvider(client, dataProvider)
	if err != nil {
		return types.StreamTypePrimitive, fmt.Errorf("invalid data provider '%s': %w", dataProvider, err)
	}

	streamLocator := types.StreamLocator{
		StreamId:     *streamIdTyped,
		DataProvider: dataProviderTyped,
	}

	stream, err := client.LoadActions()
	if err != nil {
		return types.StreamTypePrimitive, err
	}

	return stream.GetType(ctx, streamLocator)
}

// NewGetFirstRecordInput creates a new GetFirstRecordInput struct
func NewGetFirstRecordInput(
	client *tnclient.Client,
	streamId string,
	dataProvider string,
	afterVal string,
	frozenVal string,
) types.GetFirstRecordInput {
	result := types.GetFirstRecordInput{
		StreamId:     streamId,
		DataProvider: dataProvider,
	}

	if dataProvider == "" {
		currentAccount, err := GetCurrentAccount(client)
		if err != nil {
			return result
		}
		result.DataProvider = currentAccount
	}
	frozenAt, err := parseDate(frozenVal)
	if err != nil {
		return result
	}
	after, err := parseDate(afterVal)
	if err != nil {
		return result
	}

	result.FrozenAt = frozenAt
	result.After = after

	return result
}

// GetFirstRecord gets the first record of a stream after a given date
func GetFirstRecord(client *tnclient.Client, input types.GetFirstRecordInput) (map[string]string, error) {
	stream, err := client.LoadPrimitiveActions()
	if err != nil {
		return nil, err
	}

	record, err := stream.GetFirstRecord(context.Background(), input)
	if record == nil {
		return nil, nil
	}
	if err != nil {
		if err == contractsapi.ErrorRecordNotFound {
			return nil, nil
		}
		return nil, err
	}

	result := make(map[string]string)
	result["date"] = parseUnixTimestamp(record.EventTime)
	value, err := record.Value.Float64()
	if err != nil {
		return nil, fmt.Errorf("error converting value to float64: %w", err)
	}
	result["value"] = strconv.FormatFloat(value, 'f', -1, 64)

	return result, nil
}

func GetIndex(client *tnclient.Client, input types.GetIndexInput) ([]map[string]string, error) {
	ctx := context.Background()

	stream, err := client.LoadPrimitiveActions()
	if err != nil {
		return nil, err
	}
	records, err := stream.GetIndex(ctx, input)
	if err != nil {
		return nil, err
	}

	return recordsToMapSlice(records), nil
}

// WaitForTx waits for the transaction with the given hash to be confirmed.
func WaitForTx(client *tnclient.Client, txHashHex string) error {
	ctx := context.Background()

	txHash, err := kwilTypes.NewHashFromString(txHashHex)
	if err != nil {
		return fmt.Errorf("invalid transaction hash '%s': %w", txHashHex, err)
	}

	tx, err := client.WaitForTx(ctx, txHash, 1*time.Second)
	if err != nil {
		return err
	}

	// Check if tx was successful
	if tx.Result.Code != uint32(kwilTypes.CodeOk) {
		return fmt.Errorf("transaction failed: %s", tx.Result.Log)
	}
	return nil
}

// /*****************************************
//  *            Helper Functions           *
//  *****************************************/

// parseDataProvider checks if dataProvider is empty; if so, returns client's own address.
func parseDataProvider(client *tnclient.Client, dataProvider string) (util.EthereumAddress, error) {
	if dataProvider == "" {
		return client.Address(), nil
	}
	return util.NewEthereumAddressFromString(dataProvider)
}

// parseDate parses a date string in YYYY-MM-DD format and returns a UNIX timestamp *int.
func parseDate(dateStr string) (*int, error) {
	if dateStr == "" {
		return nil, nil
	}
	date, err := civil.ParseDate(dateStr)
	if err != nil {
		return nil, fmt.Errorf("invalid date format '%s': %w", dateStr, err)
	}
	unixTime := int(date.In(time.UTC).Unix())
	return &unixTime, nil
}

func parseUnixTimestamp(timestamp int) string {
	unixTimestamp := int64(timestamp)
	t := time.Unix(unixTimestamp, 0).UTC()
	formattedDate := t.Format("2006-01-02")

	return formattedDate
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
