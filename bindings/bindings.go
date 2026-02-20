package exports

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"log"
	"reflect"
	"strconv"
	"strings"
	"time"

	"github.com/cockroachdb/apd/v3"
	"github.com/golang-sql/civil"
	"github.com/pkg/errors"
	"github.com/trufnetwork/kwil-db/core/crypto"
	"github.com/trufnetwork/kwil-db/core/crypto/auth"
	kwilTypes "github.com/trufnetwork/kwil-db/core/types"
	"github.com/trufnetwork/sdk-go/core/contractsapi"
	"github.com/trufnetwork/sdk-go/core/tnclient"
	"github.com/trufnetwork/sdk-go/core/types"
	"github.com/trufnetwork/sdk-go/core/util"
	"google.golang.org/genproto/googleapis/type/decimal"
)

// StreamType constants.
const (
	StreamTypeComposed  types.StreamType    = types.StreamTypeComposed
	StreamTypePrimitive types.StreamType    = types.StreamTypePrimitive
	VisibilityPublic    util.VisibilityEnum = util.PublicVisibility
	VisibilityPrivate   util.VisibilityEnum = util.PrivateVisibility
)

type OptionalInt64 struct {
	Value int64
	IsSet bool
}

func toOptionalInt64(value *int64) OptionalInt64 {
	if value == nil {
		return OptionalInt64{
			Value: 0,
			IsSet: false,
		}
	}
	return OptionalInt64{
		Value: *value,
		IsSet: value != nil,
	}
}

// ProcedureArgs represents a slice of arguments for a procedure.
type ProcedureArgs []any

type Record struct {
	Date  int    `json:"date"`
	Value string `json:"value"`
}

type DataResponse struct {
	Data     []Record      `json:"data"`
	CacheHit bool          `json:"cache_hit"`
	Height   OptionalInt64 `json:"height"`
}

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

// ArgsFromJSON converts a JSON string to ProcedureArgs.
// This allows passing mixed-type arguments from Python.
func ArgsFromJSON(jsonStr string) (ProcedureArgs, error) {
	var anySlice []any
	err := json.Unmarshal([]byte(jsonStr), &anySlice)
	if err != nil {
		return nil, errors.Wrap(err, "failed to unmarshal JSON args")
	}
	return anySlice, nil
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
func NewInsertRecordInput(client *tnclient.Client, streamId string, date int, val float64) types.InsertRecordInput {
	dataProvider, err := GetCurrentAccount(client)
	if err != nil {
		log.Printf("Warning: Failed to get data provider: %v\n", err)
		return types.InsertRecordInput{}
	}

	return types.InsertRecordInput{
		StreamId:     streamId,
		DataProvider: dataProvider,
		EventTime:    date,
		Value:        val,
	}
}

// NewGetRecordInput creates a new GetRecordInput struct
func NewGetRecordInput(
	client *tnclient.Client,
	streamId string,
	dataProvider string,
	from int,
	to int,
	frozenAt int,
	baseDate int,
	prefix string,
	useCache bool,
) types.GetRecordInput {
	result := types.GetRecordInput{
		StreamId:     streamId,
		DataProvider: dataProvider,
		Prefix:       &prefix,
		UseCache:     &useCache,
	}

	if dataProvider == "" {
		currentAccount, err := GetCurrentAccount(client)
		if err != nil {
			return result
		}
		result.DataProvider = currentAccount
	}

	if from != -1 {
		result.From = &from
	}

	if to != -1 {
		result.To = &to
	}

	if frozenAt != -1 {
		result.FrozenAt = &frozenAt
	}

	if baseDate != -1 {
		result.BaseDate = &baseDate
	}

	return result
}

// GetRecords retrieves records from the stream with the given stream ID.
func GetRecords(client *tnclient.Client, input types.GetRecordInput) (DataResponse, error) {
	ctx := context.Background()
	stream, err := client.LoadPrimitiveActions()
	if err != nil {
		return DataResponse{}, err
	}

	// Call WithMetadata variant for cache support
	response, err := stream.GetRecord(ctx, input)
	if err != nil {
		return DataResponse{}, err
	}

	// Convert records to map slice
	records := make([]Record, len(response.Results))
	for i, record := range response.Results {
		records[i] = Record{
			Date:  record.EventTime,
			Value: record.Value.String(),
		}
	}

	// Build cache-aware response with metadata from sdk-go
	result := DataResponse{
		Data:     records,
		CacheHit: response.Metadata.CacheHit,
		Height:   toOptionalInt64(response.Metadata.CacheHeight),
	}

	return result, nil
}

// GetType retrieves type of a stream (primitive or composed)
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
	after int,
	frozenAt int,
	useCache bool,
) types.GetFirstRecordInput {
	result := types.GetFirstRecordInput{
		StreamId:     streamId,
		DataProvider: dataProvider,
		UseCache:     &useCache,
	}

	if dataProvider == "" {
		currentAccount, err := GetCurrentAccount(client)
		if err != nil {
			return result
		}
		result.DataProvider = currentAccount
	}

	if frozenAt != -1 {
		result.FrozenAt = &frozenAt
	}

	if after != -1 {
		result.After = &after
	}

	return result
}

// GetFirstRecord retrieves the first record of a stream after a given date
// we return a slice even if we expect only one record because we can't return nil in this interface
func GetFirstRecord(client *tnclient.Client, input types.GetFirstRecordInput) (DataResponse, error) {
	ctx := context.Background()
	stream, err := client.LoadPrimitiveActions()
	if err != nil {
		return DataResponse{}, err
	}

	// Call WithMetadata variant for cache support
	record, err := stream.GetFirstRecord(ctx, input)

	// Guard against empty results
	if len(record.Results) == 0 {
		return DataResponse{
			Data:     []Record{},
			CacheHit: record.Metadata.CacheHit,
			Height:   toOptionalInt64(record.Metadata.CacheHeight),
		}, nil
	}

	// Convert to Record struct
	recordData := Record{
		Date:  record.Results[0].EventTime,
		Value: record.Results[0].Value.String(),
	}

	// Build cache-aware response with metadata
	result := DataResponse{
		Data:     []Record{recordData},
		CacheHit: record.Metadata.CacheHit,
		Height:   toOptionalInt64(record.Metadata.CacheHeight),
	}

	return result, nil
}

// GetIndex retrieves index values from a stream
func GetIndex(client *tnclient.Client, input types.GetIndexInput) (DataResponse, error) {
	ctx := context.Background()
	stream, err := client.LoadPrimitiveActions()
	if err != nil {
		return DataResponse{}, err
	}

	// Call WithMetadata variant for cache support
	response, err := stream.GetIndex(ctx, input)
	if err != nil {
		return DataResponse{}, err
	}

	// Convert indices to Record slice
	records := make([]Record, len(response.Results))
	for i, index := range response.Results {
		records[i] = Record{
			Date:  index.EventTime,
			Value: index.Value.String(),
		}
	}

	// Build cache-aware response with metadata from sdk-go
	result := DataResponse{
		Data:     records,
		CacheHit: response.Metadata.CacheHit,
		Height:   toOptionalInt64(response.Metadata.CacheHeight),
	}

	return result, nil
}

// NewListStreamsInput creates a new ListStreamsInput struct
func NewListStreamsInput(limit int, offset int, dataProvider string, orderBy string, blockHeight int) types.ListStreamsInput {
	result := types.ListStreamsInput{
		BlockHeight: blockHeight,
	}

	if limit != -1 {
		result.Limit = limit
	}
	if offset != -1 {
		result.Offset = offset
	}
	if dataProvider != "" {
		result.DataProvider = dataProvider
	}
	if orderBy != "" {
		result.OrderBy = orderBy
	}

	return result
}

// ListStreams retrieves all streams associated with client
func ListStreams(client *tnclient.Client, input types.ListStreamsInput) ([]map[string]string, error) {
	ctx := context.Background()

	streams, err := client.ListStreams(ctx, input)
	if err != nil {
		return nil, err
	}

	return recordsToMapSlice(streams), nil
}

// NewTaxonomyItemInput creates a new TaxonomyItemInput struct
func NewTaxonomyItemInput(client *tnclient.Client, dataProvider string, stream_id string, weight float64) types.TaxonomyItem {
	streamIdObj, err := util.NewStreamId(stream_id)
	if err != nil {
		return types.TaxonomyItem{}
	}

	if dataProvider == "" {
		currentAccount, err := GetCurrentAccount(client)
		if err != nil {
			return types.TaxonomyItem{}
		}
		dataProvider = currentAccount
	}
	dataProviderTyped, err := parseDataProvider(client, dataProvider)
	if err != nil {
		return types.TaxonomyItem{}
	}

	return types.TaxonomyItem{
		ChildStream: types.StreamLocator{
			StreamId:     *streamIdObj,
			DataProvider: dataProviderTyped,
		},
		Weight: weight,
	}
}

// NewTaxonomyInput creates a new TaxonomyInput struct
func NewTaxonomyInput(client *tnclient.Client, streamId string, childStreams []types.TaxonomyItem, startDate int, groupSequence int) types.Taxonomy {
	result := types.Taxonomy{
		TaxonomyItems: childStreams,
	}

	// Assign parent stream
	streamIdObj, err := util.NewStreamId(streamId)
	if err != nil {
		return types.Taxonomy{}
	}
	result.ParentStream = client.OwnStreamLocator(*streamIdObj)

	createdAt, err := parseDate(time.Now().Format("2006-01-02"))
	if err != nil {
		return types.Taxonomy{}
	}

	result.CreatedAt = *createdAt

	if startDate != -1 {
		result.StartDate = &startDate
	}
	if groupSequence != -1 {
		result.GroupSequence = groupSequence
	}

	return result
}

// SetTaxonomy define the taxonomy structure of a composed stream
func SetTaxonomy(client *tnclient.Client, input types.Taxonomy) (string, error) {
	ctx := context.Background()

	stream, err := client.LoadComposedActions()
	if err != nil {
		return "", err
	}

	txHash, err := stream.InsertTaxonomy(ctx, input)
	if err != nil {
		return "", err
	}

	return txHash.String(), nil
}

// DescribeTaxonomy retrieves the taxonomy structure of a composed stream
func DescribeTaxonomy(client *tnclient.Client, streamId string, latestVersion bool) (map[string]string, error) {
	ctx := context.Background()

	stream, err := client.LoadComposedActions()
	if err != nil {
		return map[string]string{}, err
	}

	streamIdObj, err := util.NewStreamId(streamId)
	if err != nil {
		return map[string]string{}, nil
	}

	result, err := stream.DescribeTaxonomies(ctx, types.DescribeTaxonomiesParams{
		Stream:        client.OwnStreamLocator(*streamIdObj),
		LatestVersion: latestVersion,
	})
	if err != nil {
		return map[string]string{}, err
	}

	childStreams := make([]map[string]string, 0, len(result.TaxonomyItems))
	for _, childStream := range result.TaxonomyItems {
		childStreams = append(childStreams, map[string]string{
			"stream_id":     childStream.ChildStream.StreamId.String(),
			"data_provider": childStream.ChildStream.DataProvider.Address(),
			"weight":        convertToString(childStream.Weight),
		})
	}
	childStreamsJSON, err := json.Marshal(childStreams)
	if err != nil {
		return map[string]string{}, err
	}

	res := map[string]string{
		"stream_id":      streamId,
		"child_streams":  string(childStreamsJSON),
		"start_date":     convertToString(result.StartDate),
		"created_at":     convertToString(result.CreatedAt),
		"group_sequence": convertToString(result.GroupSequence),
	}

	return res, nil
}

// AllowComposeStream allows stream to use this stream as child, if composing is private
func AllowComposeStream(client *tnclient.Client, streamId string) (string, error) {
	ctx := context.Background()

	stream, err := client.LoadPrimitiveActions()
	if err != nil {
		return "", err
	}

	streamIdObj, err := util.NewStreamId(streamId)
	if err != nil {
		return "", err
	}

	txHash, err := stream.AllowComposeStream(ctx, client.OwnStreamLocator(*streamIdObj))
	if err != nil {
		return "", err
	}

	return txHash.String(), nil
}

// DisableComposeStream disables streams from using this stream as child
func DisableComposeStream(client *tnclient.Client, streamId string) (string, error) {
	ctx := context.Background()
	stream, err := client.LoadPrimitiveActions()
	if err != nil {
		return "", err
	}

	streamIdObj, err := util.NewStreamId(streamId)
	if err != nil {
		return "", err
	}

	txHash, err := stream.DisableComposeStream(ctx, client.OwnStreamLocator(*streamIdObj))
	if err != nil {
		return "", err
	}

	return txHash.String(), nil
}

// NewReadWalletInput creates a new ReadWalletInput struct
func NewReadWalletInput(client *tnclient.Client, streamId string, wallet string) types.ReadWalletInput {
	result := types.ReadWalletInput{}

	streamIdObj, err := util.NewStreamId(streamId)
	if err != nil {
		return types.ReadWalletInput{}
	}
	result.Stream = client.OwnStreamLocator(*streamIdObj)
	result.Wallet, err = util.NewEthereumAddressFromString(wallet)
	if err != nil {
		return types.ReadWalletInput{}
	}

	return result
}

// AllowReadWallet allows a wallet to read the stream, if reading is private
func AllowReadWallet(client *tnclient.Client, input types.ReadWalletInput) (string, error) {
	ctx := context.Background()
	stream, err := client.LoadActions()
	if err != nil {
		return "", err
	}

	txHash, err := stream.AllowReadWallet(ctx, input)
	if err != nil {
		return "", err
	}

	return txHash.String(), nil
}

// DisableReadWallet disables a wallet from reading the stream
func DisableReadWallet(client *tnclient.Client, input types.ReadWalletInput) (string, error) {
	ctx := context.Background()
	stream, err := client.LoadActions()
	if err != nil {
		return "", err
	}

	txHash, err := stream.DisableReadWallet(ctx, input)
	if err != nil {
		return "", err
	}

	return txHash.String(), nil
}

// NewVisibilityInput creates a new VisibilityInput struct
func NewVisibilityInput(client *tnclient.Client, streamId string, visibility int) types.VisibilityInput {
	result := types.VisibilityInput{}

	streamIdObj, err := util.NewStreamId(streamId)
	if err != nil {
		return types.VisibilityInput{}
	}

	result.Stream = client.OwnStreamLocator(*streamIdObj)

	result.Visibility, err = util.NewVisibilityEnum(visibility)
	if err != nil {
		return types.VisibilityInput{}
	}

	return result
}

// SetReadVisibility sets the read visibility of the stream -- Private or Public
func SetReadVisibility(client *tnclient.Client, input types.VisibilityInput) (string, error) {
	ctx := context.Background()
	stream, err := client.LoadActions()
	if err != nil {
		return "", err
	}

	txHash, err := stream.SetReadVisibility(ctx, input)
	if err != nil {
		return "", err
	}

	return txHash.String(), nil
}

// GetReadVisibility gets the read visibility of the stream -- Private or Public
func GetReadVisibility(client *tnclient.Client, streamId string) (util.VisibilityEnum, error) {
	ctx := context.Background()
	stream, err := client.LoadActions()
	if err != nil {
		return 0, err
	}

	streamIdObj, err := util.NewStreamId(streamId)
	if err != nil {
		return 0, err
	}

	visibility, err := stream.GetReadVisibility(ctx, client.OwnStreamLocator(*streamIdObj))
	if err != nil {
		return 0, err
	}

	return *visibility, nil
}

// SetComposeVisibility sets the compose visibility of the stream -- Private or Public
func SetComposeVisibility(client *tnclient.Client, input types.VisibilityInput) (string, error) {
	ctx := context.Background()
	stream, err := client.LoadActions()
	if err != nil {
		return "", err
	}

	txHash, err := stream.SetComposeVisibility(ctx, input)
	if err != nil {
		return "", err
	}

	return txHash.String(), nil
}

// GetComposeVisibility gets the compose visibility of the stream -- Private or Public
func GetComposeVisibility(client *tnclient.Client, streamId string) (util.VisibilityEnum, error) {
	ctx := context.Background()
	stream, err := client.LoadActions()
	if err != nil {
		return 0, err
	}

	streamIdObj, err := util.NewStreamId(streamId)
	if err != nil {
		return 0, err
	}

	visibility, err := stream.GetComposeVisibility(ctx, client.OwnStreamLocator(*streamIdObj))
	if err != nil {
		return 0, err
	}

	return *visibility, nil
}

// GetAllowedReadWallets gets the wallets allowed to read the stream
func GetAllowedReadWallets(client *tnclient.Client, streamId string) ([]string, error) {
	ctx := context.Background()
	stream, err := client.LoadActions()
	if err != nil {
		return []string{}, err
	}

	streamIdObj, err := util.NewStreamId(streamId)
	if err != nil {
		return []string{}, err
	}

	result, err := stream.GetAllowedReadWallets(ctx, client.OwnStreamLocator(*streamIdObj))
	if err != nil {
		return []string{}, err
	}

	addresses := make([]string, 0, len(result))
	for _, address := range result {
		addresses = append(addresses, address.Address())
	}

	return addresses, nil
}

// GetAllowedComposeStreams gets the streams allowed to compose this stream
func GetAllowedComposeStreams(client *tnclient.Client, streamId string) ([]string, error) {
	ctx := context.Background()
	stream, err := client.LoadActions()
	if err != nil {
		return []string{}, err
	}

	streamIdObj, err := util.NewStreamId(streamId)
	if err != nil {
		return []string{}, err
	}

	result, err := stream.GetAllowedComposeStreams(ctx, client.OwnStreamLocator(*streamIdObj))
	if err != nil {
		return []string{}, err
	}

	streams := make([]string, 0, len(result))
	for _, stream := range result {
		streams = append(streams, stream.StreamId.String())
	}

	return streams, nil
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
	case nil:
		return ""
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
	case util.EthereumAddress:
		return v.Address()
	case *util.EthereumAddress:
		return v.Address()
	case bool:
		return strconv.FormatBool(v)
	case fmt.Stringer:
		return v.String()
	default:
		log.Printf("Warning: Failed to convert argument to string from type %T: %v\n", val, val)
		return fmt.Sprintf("%v", val)
	}
}

// convertBytesToHex converts byte slice to hex string for Python compatibility
func convertBytesToHex(data []byte) string {
	if data == nil {
		return ""
	}
	return fmt.Sprintf("%x", data) // Use hex encoding for simplicity and readability
}

// NewStreamDefinitionForBinding creates a new types.StreamDefinition for binding purposes.
// It takes string representations of streamId and streamType and converts them.
func NewStreamDefinitionForBinding(streamIdStr string, streamTypeStr string) (*types.StreamDefinition, error) {
	sid, err := util.NewStreamId(streamIdStr)
	if err != nil {
		return nil, errors.Wrapf(err, "error creating stream id from string: %s", streamIdStr)
	}

	var st types.StreamType
	if streamTypeStr == string(types.StreamTypeComposed) {
		st = types.StreamTypeComposed
	} else if streamTypeStr == string(types.StreamTypePrimitive) {
		st = types.StreamTypePrimitive
	} else {
		return nil, fmt.Errorf("unsupported stream type string: %s, expected 'primitive' or 'composed'", streamTypeStr)
	}

	return &types.StreamDefinition{
		StreamId:   *sid,
		StreamType: st,
	}, nil
}

// NewStreamLocatorForBinding creates a new types.StreamLocator for binding purposes.
func NewStreamLocatorForBinding(streamIdStr string, dataProviderAddressStr string) (*types.StreamLocator, error) {
	sid, err := util.NewStreamId(streamIdStr)
	if err != nil {
		return nil, errors.Wrapf(err, "error creating stream id from string: %s", streamIdStr)
	}
	dp, err := util.NewEthereumAddressFromString(dataProviderAddressStr)
	if err != nil {
		return nil, errors.Wrapf(err, "error creating ethereum address from string: %s", dataProviderAddressStr)
	}
	return &types.StreamLocator{
		StreamId:     *sid,
		DataProvider: dp,
	}, nil
}

// BatchDeployStreams deploys multiple streams.
// It expects a slice of types.StreamDefinition, which Python side should construct.
func BatchDeployStreams(client *tnclient.Client, definitions []types.StreamDefinition) (string, error) {
	ctx := context.Background()
	txHash, err := client.BatchDeployStreams(ctx, definitions)
	if err != nil {
		return "", errors.Wrap(err, "error batch deploying streams")
	}
	return txHash.String(), nil
}

// BatchStreamExists checks for the existence of multiple streams.
// It expects a slice of types.StreamLocator and returns a slice of maps.
func BatchStreamExists(client *tnclient.Client, locators []types.StreamLocator) ([]map[string]string, error) {
	ctx := context.Background()
	results, err := client.BatchStreamExists(ctx, locators)
	if err != nil {
		return nil, errors.Wrap(err, "error checking batch stream existence")
	}

	output := make([]map[string]string, len(results))
	for i, res := range results {
		output[i] = map[string]string{
			"stream_id":     res.StreamLocator.StreamId.String(),
			"data_provider": res.StreamLocator.DataProvider.Address(),
			"exists":        strconv.FormatBool(res.Exists),
		}
	}
	return output, nil
}

// BatchFilterStreamsByExistence filters a list of streams based on their existence.
// It expects a slice of types.StreamLocator and a boolean, returns a slice of maps (locators).
func BatchFilterStreamsByExistence(client *tnclient.Client, locators []types.StreamLocator, returnExisting bool) ([]map[string]string, error) {
	ctx := context.Background()
	results, err := client.BatchFilterStreamsByExistence(ctx, locators, returnExisting)
	if err != nil {
		return nil, errors.Wrap(err, "error filtering batch streams by existence")
	}

	output := make([]map[string]string, len(results))
	for i, res := range results {
		output[i] = map[string]string{
			"stream_id":     res.StreamId.String(),
			"data_provider": res.DataProvider.Address(),
		}
	}
	return output, nil
}

// helper to convert slice of hex wallet strings to []util.EthereumAddress
func strSliceToEthAddrs(wallets []string) ([]util.EthereumAddress, error) {
	out := make([]util.EthereumAddress, len(wallets))
	for i, w := range wallets {
		addr, err := util.NewEthereumAddressFromString(w)
		if err != nil {
			return nil, err
		}
		out[i] = addr
	}
	return out, nil
}

// GrantRole grants a role to multiple wallets.
func GrantRole(client *tnclient.Client, owner string, roleName string, wallets []string) (string, error) {
	ctx := context.Background()

	roleMgmt, err := client.LoadRoleManagementActions()
	if err != nil {
		return "", errors.Wrap(err, "error loading role management actions")
	}

	addrs, err := strSliceToEthAddrs(wallets)
	if err != nil {
		return "", errors.Wrap(err, "invalid wallet address")
	}

	input := types.GrantRoleInput{
		Owner:    owner,
		RoleName: roleName,
		Wallets:  addrs,
	}

	txHash, err := roleMgmt.GrantRole(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "error granting role")
	}
	return txHash.String(), nil
}

// RevokeRole revokes a role from multiple wallets.
func RevokeRole(client *tnclient.Client, owner string, roleName string, wallets []string) (string, error) {
	ctx := context.Background()

	roleMgmt, err := client.LoadRoleManagementActions()
	if err != nil {
		return "", errors.Wrap(err, "error loading role management actions")
	}

	addrs, err := strSliceToEthAddrs(wallets)
	if err != nil {
		return "", errors.Wrap(err, "invalid wallet address")
	}

	input := types.RevokeRoleInput{
		Owner:    owner,
		RoleName: roleName,
		Wallets:  addrs,
	}

	txHash, err := roleMgmt.RevokeRole(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "error revoking role")
	}
	return txHash.String(), nil
}

// AreMembersOf checks if a list of wallets are members of a specific role.
func AreMembersOf(client *tnclient.Client, owner string, roleName string, wallets []string) ([]map[string]string, error) {
	ctx := context.Background()

	roleMgmt, err := client.LoadRoleManagementActions()
	if err != nil {
		return nil, errors.Wrap(err, "error loading role management actions")
	}

	addrs, err := strSliceToEthAddrs(wallets)
	if err != nil {
		return nil, errors.Wrap(err, "invalid wallet address")
	}

	input := types.AreMembersOfInput{
		Owner:    owner,
		RoleName: roleName,
		Wallets:  addrs,
	}

	results, err := roleMgmt.AreMembersOf(ctx, input)
	if err != nil {
		return nil, errors.Wrap(err, "error checking role members")
	}

	return recordsToMapSlice(results), nil
}

// ListRoleMembers lists the current members of a role with optional pagination.
// It returns a slice of map[string]string where each map contains `Wallet`, `GrantedAt`, and `GrantedBy`.
func ListRoleMembers(client *tnclient.Client, owner string, roleName string, limit int, offset int) ([]map[string]string, error) {
	ctx := context.Background()

	roleMgmt, err := client.LoadRoleManagementActions()
	if err != nil {
		return nil, errors.Wrap(err, "error loading role management actions")
	}

	input := types.ListRoleMembersInput{
		Owner:    owner,
		RoleName: roleName,
		Limit:    limit,
		Offset:   offset,
	}

	results, err := roleMgmt.ListRoleMembers(ctx, input)
	if err != nil {
		return nil, errors.Wrap(err, "error listing role members")
	}

	return recordsToMapSlice(results), nil
}

// CallProcedure executes a read-only stored procedure and returns its query result in a JSON-like map.
// The returned map has two keys:
//   - "column_names": []string – names of the columns returned by the procedure
//   - "values": [][]string – row-major 2-D slice with stringified cell values
//
// All procedure arguments are forwarded as-is. Use nil for SQL NULLs / optional params.
func CallProcedure(client *tnclient.Client, procedure string, args []any) (map[string]any, error) {
	ctx := context.Background()

	// Load the generic Action API which exposes arbitrary procedures.
	actions, err := client.LoadActions()
	if err != nil {
		return nil, errors.Wrap(err, "failed to load Action API")
	}

	qr, err := actions.CallProcedure(ctx, procedure, args)
	if err != nil {
		return nil, errors.WithStack(err)
	}

	// Convert result values to string to make them JSON / Python friendly.
	strVals := make([][]string, len(qr.Values))
	for i, row := range qr.Values {
		rowOut := make([]string, len(row))
		for j, cell := range row {
			rowOut[j] = convertToString(cell)
		}
		strVals[i] = rowOut
	}

	out := map[string]any{
		"column_names": qr.ColumnNames,
		"values":       strVals,
	}
	return out, nil
}

// CallProcedureStrings is a convenience wrapper that accepts the procedure arguments
// as a slice of strings, which Python can pass directly (gopy happily converts
// a Python list[str] to []string).  Each element is heuristically converted to
// an appropriate Go type (int, float64, or left as string).  An empty string
// is treated as SQL NULL (nil).
func CallProcedureStrings(client *tnclient.Client, procedure string, args []string) (string, error) {
	// Convert []string into []any with basic type inference
	parsed := make([]any, len(args))
	for i, s := range args {
		if s == "" {
			parsed[i] = nil
			continue
		}
		// Try int
		if iv, err := strconv.Atoi(s); err == nil {
			parsed[i] = iv
			continue
		}
		// Try float
		if fv, err := strconv.ParseFloat(s, 64); err == nil {
			parsed[i] = fv
			continue
		}
		// Fallback to raw string
		parsed[i] = s
	}
	resMap, err := CallProcedure(client, procedure, parsed)
	if err != nil {
		return "", err
	}

	// JSON encode the map so that Python receives a plain string, avoiding
	// complex Go interface{} conversions.
	jsonBytes, err := json.Marshal(resMap)
	if err != nil {
		return "", errors.Wrap(err, "marshal result to json")
	}

	return string(jsonBytes), nil
}

// ==========================================
//           ATTESTATION FUNCTIONS
// ==========================================

// RequestAttestation submits an attestation request and returns the transaction ID
// argsJSON should be a JSON-encoded array of arguments
// maxFee should be a string representation of NUMERIC(78,0) (e.g., "100000000000000000000")
func RequestAttestation(
	client *tnclient.Client,
	dataProvider string,
	streamID string,
	actionName string,
	argsJSON string,
	encryptSig bool,
	maxFee string,
) (string, error) {
	ctx := context.Background()

	// Load attestation actions
	attestationActions, err := client.LoadAttestationActions()
	if err != nil {
		return "", errors.Wrap(err, "failed to load attestation actions")
	}

	// Decode JSON args with number preservation
	var args []any
	if argsJSON != "" && argsJSON != "[]" {
		decoder := json.NewDecoder(strings.NewReader(argsJSON))
		decoder.UseNumber() // Preserve numbers as json.Number
		err = decoder.Decode(&args)
		if err != nil {
			return "", errors.Wrap(err, "failed to unmarshal args JSON")
		}

		// Convert json.Number to int64 where possible, otherwise float64
		for i, arg := range args {
			if num, ok := arg.(json.Number); ok {
				// Try int64 first
				if intVal, err := num.Int64(); err == nil {
					args[i] = intVal
				} else if floatVal, err := num.Float64(); err == nil {
					args[i] = floatVal
				}
			}
		}
	}

	// Build input
	input := types.RequestAttestationInput{
		DataProvider: dataProvider,
		StreamID:     streamID,
		ActionName:   actionName,
		Args:         args,
		EncryptSig:   encryptSig,
		MaxFee:       maxFee,
	}

	// Call sdk-go
	result, err := attestationActions.RequestAttestation(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to request attestation")
	}

	return result.RequestTxID, nil
}

// GetSignedAttestation retrieves a signed attestation payload
func GetSignedAttestation(client *tnclient.Client, requestTxID string) ([]byte, error) {
	ctx := context.Background()

	attestationActions, err := client.LoadAttestationActions()
	if err != nil {
		return nil, errors.Wrap(err, "failed to load attestation actions")
	}

	input := types.GetSignedAttestationInput{
		RequestTxID: requestTxID,
	}

	result, err := attestationActions.GetSignedAttestation(ctx, input)
	if err != nil {
		return nil, errors.Wrap(err, "failed to get signed attestation")
	}

	return result.Payload, nil
}

// ListAttestations lists attestation metadata with optional filtering
func ListAttestations(
	client *tnclient.Client,
	requester []byte,
	limit int,
	offset int,
	orderBy string,
) ([]map[string]string, error) {
	ctx := context.Background()

	attestationActions, err := client.LoadAttestationActions()
	if err != nil {
		return nil, errors.Wrap(err, "failed to load attestation actions")
	}

	// Build input
	input := types.ListAttestationsInput{}

	if len(requester) > 0 {
		input.Requester = requester
	}

	if limit != -1 {
		input.Limit = &limit
	}

	if offset != -1 {
		input.Offset = &offset
	}

	if orderBy != "" {
		input.OrderBy = &orderBy
	}

	results, err := attestationActions.ListAttestations(ctx, input)
	if err != nil {
		return nil, errors.Wrap(err, "failed to list attestations")
	}

	// Convert to map slice for Python
	output := make([]map[string]string, len(results))
	for i, metadata := range results {
		// Convert signed_height (nullable int64) to string
		signedHeightStr := ""
		if metadata.SignedHeight != nil {
			signedHeightStr = strconv.FormatInt(*metadata.SignedHeight, 10)
		}

		output[i] = map[string]string{
			"RequestTxID":     metadata.RequestTxID,
			"AttestationHash": convertBytesToHex(metadata.AttestationHash),
			"Requester":       convertBytesToHex(metadata.Requester),
			"CreatedHeight":   strconv.FormatInt(metadata.CreatedHeight, 10),
			"SignedHeight":    signedHeightStr,
			"EncryptSig":      strconv.FormatBool(metadata.EncryptSig),
		}
	}

	return output, nil
}

// ParseAttestationPayload parses a canonical attestation payload (without signature)
// Returns a JSON string containing the parsed payload structure
func ParseAttestationPayload(payload []byte) (string, error) {
	parsed, err := contractsapi.ParseAttestationPayload(payload)
	if err != nil {
		return "", errors.Wrap(err, "failed to parse attestation payload")
	}

	// Convert to JSON for Python consumption
	jsonBytes, err := json.Marshal(parsed)
	if err != nil {
		return "", errors.Wrap(err, "failed to marshal parsed payload to JSON")
	}

	return string(jsonBytes), nil
}

// VerifyAttestationSignature extracts and verifies the signature from an attestation payload
// Returns the validator's Ethereum address as a hex string (0x...)
func VerifyAttestationSignature(fullPayload []byte) (string, error) {
	// Validate minimum length
	if len(fullPayload) < 66 {
		return "", fmt.Errorf("payload too short (%d bytes), expected at least 66", len(fullPayload))
	}

	// Extract canonical payload and signature
	signatureOffset := len(fullPayload) - 65
	canonicalPayload := fullPayload[:signatureOffset]
	signature := fullPayload[signatureOffset:]

	// Hash the canonical payload
	hash := sha256.Sum256(canonicalPayload)

	// Adjust signature format (Ethereum V=27/28 -> raw V=0/1)
	adjustedSig := make([]byte, 65)
	copy(adjustedSig, signature)
	if signature[64] >= 27 {
		adjustedSig[64] = signature[64] - 27
	}

	// Recover public key
	pubKey, err := crypto.RecoverSecp256k1KeyFromSigHash(hash[:], adjustedSig)
	if err != nil {
		return "", errors.Wrap(err, "failed to recover public key from signature")
	}

	// Derive Ethereum address
	validatorAddr := crypto.EthereumAddressFromPubKey(pubKey)
	return fmt.Sprintf("0x%x", validatorAddr), nil
}

// ==========================================
//     TRANSACTION LEDGER FUNCTIONS
// ==========================================

// GetTransactionEvent retrieves detailed transaction information by tx hash
func GetTransactionEvent(client *tnclient.Client, txID string) (map[string]string, error) {
	ctx := context.Background()

	// Load transaction actions
	txActions, err := client.LoadTransactionActions()
	if err != nil {
		return nil, errors.Wrap(err, "failed to load transaction actions")
	}

	// Build input
	input := types.GetTransactionEventInput{
		TxID: txID,
	}

	// Call SDK-Go
	result, err := txActions.GetTransactionEvent(ctx, input)
	if err != nil {
		return nil, errors.Wrap(err, "failed to get transaction event")
	}

	// Convert to map[string]string for gopy compatibility
	// gopy has trouble with complex structs, so we flatten everything
	response := make(map[string]string)
	response["TxID"] = result.TxID
	response["BlockHeight"] = strconv.FormatInt(result.BlockHeight, 10)
	response["Method"] = result.Method
	response["Caller"] = result.Caller
	response["FeeAmount"] = result.FeeAmount

	// Handle nullable fields
	if result.FeeRecipient != nil {
		response["FeeRecipient"] = *result.FeeRecipient
	} else {
		response["FeeRecipient"] = ""
	}

	if result.Metadata != nil {
		response["Metadata"] = *result.Metadata
	} else {
		response["Metadata"] = ""
	}

	// Encode fee distributions as JSON for easy parsing in Python
	if len(result.FeeDistributions) > 0 {
		distributionsJSON, err := json.Marshal(result.FeeDistributions)
		if err != nil {
			return nil, errors.Wrap(err, "failed to marshal fee distributions")
		}
		response["FeeDistributions"] = string(distributionsJSON)
	} else {
		response["FeeDistributions"] = "[]"
	}

	return response, nil
}

// ListTransactionFees returns transactions filtered by wallet and mode
func ListTransactionFees(
	client *tnclient.Client,
	wallet string,
	mode string,
	limit int,
	offset int,
) ([]map[string]string, error) {
	ctx := context.Background()

	// Load transaction actions
	txActions, err := client.LoadTransactionActions()
	if err != nil {
		return nil, errors.Wrap(err, "failed to load transaction actions")
	}

	// Convert limit/offset sentinel values to pointers
	var limitPtr *int
	var offsetPtr *int

	if limit > 0 {
		limitPtr = &limit
	}
	if offset >= 0 {
		offsetPtr = &offset
	}

	// Build input
	input := types.ListTransactionFeesInput{
		Wallet: wallet,
		Mode:   types.TransactionFeeMode(mode),
		Limit:  limitPtr,
		Offset: offsetPtr,
	}

	// Call SDK-Go
	results, err := txActions.ListTransactionFees(ctx, input)
	if err != nil {
		return nil, errors.Wrap(err, "failed to list transaction fees")
	}

	// Convert to slice of maps for gopy compatibility
	response := make([]map[string]string, 0, len(results))
	for _, entry := range results {
		entryMap := make(map[string]string)
		entryMap["TxID"] = entry.TxID
		entryMap["BlockHeight"] = strconv.FormatInt(entry.BlockHeight, 10)
		entryMap["Method"] = entry.Method
		entryMap["Caller"] = entry.Caller
		entryMap["TotalFee"] = entry.TotalFee

		// Handle nullable fields
		if entry.FeeRecipient != nil {
			entryMap["FeeRecipient"] = *entry.FeeRecipient
		} else {
			entryMap["FeeRecipient"] = ""
		}

		if entry.Metadata != nil {
			entryMap["Metadata"] = *entry.Metadata
		} else {
			entryMap["Metadata"] = ""
		}

		entryMap["DistributionSequence"] = strconv.Itoa(entry.DistributionSequence)

		if entry.DistributionRecipient != nil {
			entryMap["DistributionRecipient"] = *entry.DistributionRecipient
		} else {
			entryMap["DistributionRecipient"] = ""
		}

		if entry.DistributionAmount != nil {
			entryMap["DistributionAmount"] = *entry.DistributionAmount
		} else {
			entryMap["DistributionAmount"] = ""
		}

		response = append(response, entryMap)
	}

	return response, nil
}

// ═══════════════════════════════════════════════════════════════
//           ORDER BOOK FUNCTIONS
// ═══════════════════════════════════════════════════════════════

// CreateMarket creates a new prediction market
// Parameters:
//   - bridge: Bridge namespace (hoodi_tt2, sepolia_bridge, ethereum_bridge)
//   - queryComponents: ABI-encoded tuple (address, bytes32, string, bytes)
//   - settleTime: Unix timestamp when market can be settled
//   - maxSpread: Maximum spread for LP rewards (1-50 cents)
//   - minOrderSize: Minimum order size for LP rewards
func CreateMarket(
	client *tnclient.Client,
	bridge string,
	queryComponents []byte,
	settleTime int64,
	maxSpread int,
	minOrderSize int64,
) (string, error) {
	ctx := context.Background()

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	// Validate bridge
	validBridges := map[string]bool{
		"hoodi_tt2":       true,
		"sepolia_bridge":  true,
		"ethereum_bridge": true,
	}
	if !validBridges[bridge] {
		return "", errors.New("bridge must be one of: hoodi_tt2, sepolia_bridge, ethereum_bridge")
	}

	// Validate query components (minimum ABI-encoded tuple size)
	if len(queryComponents) < 128 {
		return "", errors.New("query_components too short for ABI-encoded tuple")
	}
	if maxSpread < 1 || maxSpread > 50 {
		return "", errors.New("max_spread must be between 1 and 50")
	}
	if minOrderSize <= 0 {
		return "", errors.New("min_order_size must be positive")
	}

	input := types.CreateMarketInput{
		Bridge:          bridge,
		QueryComponents: queryComponents,
		SettleTime:      settleTime,
		MaxSpread:       maxSpread,
		MinOrderSize:    minOrderSize,
	}

	txHash, err := orderBook.CreateMarket(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to create market")
	}

	return txHash.String(), nil
}

// GetMarketInfo retrieves market details by ID
func GetMarketInfo(client *tnclient.Client, queryID int) (string, error) {
	ctx := context.Background()

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	input := types.GetMarketInfoInput{
		QueryID: queryID,
	}

	result, err := orderBook.GetMarketInfo(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to get market info")
	}

	jsonBytes, err := json.Marshal(marketInfoToMap(result))
	if err != nil {
		return "", errors.Wrap(err, "failed to marshal market info")
	}

	return string(jsonBytes), nil
}

// GetMarketByHash retrieves market details by query hash
func GetMarketByHash(client *tnclient.Client, queryHash []byte) (string, error) {
	ctx := context.Background()

	if len(queryHash) != 32 {
		return "", errors.New("query_hash must be exactly 32 bytes")
	}

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	input := types.GetMarketByHashInput{
		QueryHash: queryHash,
	}

	result, err := orderBook.GetMarketByHash(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to get market by hash")
	}

	jsonBytes, err := json.Marshal(marketInfoToMap(result))
	if err != nil {
		return "", errors.Wrap(err, "failed to marshal market info")
	}

	return string(jsonBytes), nil
}

// ListMarkets returns paginated list of markets
func ListMarkets(
	client *tnclient.Client,
	settledFilter int,
	limit int,
	offset int,
) (string, error) {
	ctx := context.Background()

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	input := types.ListMarketsInput{}

	if settledFilter != -1 {
		settled := settledFilter == 1
		input.SettledFilter = &settled
	}

	if limit > 0 {
		input.Limit = &limit
	}

	if offset > 0 {
		input.Offset = &offset
	}

	results, err := orderBook.ListMarkets(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to list markets")
	}

	markets := make([]map[string]any, len(results))
	for i, market := range results {
		markets[i] = map[string]any{
			"id":             market.ID,
			"hash":           convertBytesToHex(market.Hash),
			"settle_time":    market.SettleTime,
			"settled":        market.Settled,
			"max_spread":     market.MaxSpread,
			"min_order_size": market.MinOrderSize,
			"created_at":     market.CreatedAt,
		}

		if market.WinningOutcome != nil {
			markets[i]["winning_outcome"] = *market.WinningOutcome
		} else {
			markets[i]["winning_outcome"] = nil
		}
	}

	jsonBytes, err := json.Marshal(markets)
	if err != nil {
		return "", errors.Wrap(err, "failed to marshal markets")
	}

	return string(jsonBytes), nil
}

// MarketExists checks if market exists by hash
func MarketExists(client *tnclient.Client, queryHash []byte) (bool, error) {
	ctx := context.Background()

	if len(queryHash) != 32 {
		return false, errors.New("query_hash must be exactly 32 bytes")
	}

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return false, errors.Wrap(err, "failed to load order book")
	}

	input := types.MarketExistsInput{
		QueryHash: queryHash,
	}

	exists, err := orderBook.MarketExists(ctx, input)
	if err != nil {
		return false, errors.Wrap(err, "failed to check market existence")
	}

	return exists, nil
}

// ValidateMarketCollateral checks binary token parity and vault balance
func ValidateMarketCollateral(client *tnclient.Client, queryID int) (string, error) {
	ctx := context.Background()

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	input := types.ValidateMarketCollateralInput{
		QueryID: queryID,
	}

	result, err := orderBook.ValidateMarketCollateral(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to validate market collateral")
	}

	validation := map[string]any{
		"valid_token_binaries": result.ValidTokenBinaries,
		"valid_collateral":     result.ValidCollateral,
		"total_true":           result.TotalTrue,
		"total_false":          result.TotalFalse,
		"vault_balance":        result.VaultBalance,
		"expected_collateral":  result.ExpectedCollateral,
		"open_buys_value":      result.OpenBuysValue,
	}

	jsonBytes, err := json.Marshal(validation)
	if err != nil {
		return "", errors.Wrap(err, "failed to marshal validation")
	}

	return string(jsonBytes), nil
}

// PlaceBuyOrder places a buy order for YES or NO shares
func PlaceBuyOrder(
	client *tnclient.Client,
	queryID int,
	outcome bool,
	price int,
	amount int64,
) (string, error) {
	ctx := context.Background()

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	if price < 1 || price > 99 {
		return "", errors.New("price must be between 1 and 99 cents")
	}
	if amount <= 0 {
		return "", errors.New("amount must be positive")
	}

	input := types.PlaceBuyOrderInput{
		QueryID: queryID,
		Outcome: outcome,
		Price:   price,
		Amount:  amount,
	}

	txHash, err := orderBook.PlaceBuyOrder(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to place buy order")
	}

	return txHash.String(), nil
}

// PlaceSellOrder places a sell order for shares you own
func PlaceSellOrder(
	client *tnclient.Client,
	queryID int,
	outcome bool,
	price int,
	amount int64,
) (string, error) {
	ctx := context.Background()

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	if price < 1 || price > 99 {
		return "", errors.New("price must be between 1 and 99 cents")
	}
	if amount <= 0 {
		return "", errors.New("amount must be positive")
	}

	input := types.PlaceSellOrderInput{
		QueryID: queryID,
		Outcome: outcome,
		Price:   price,
		Amount:  amount,
	}

	txHash, err := orderBook.PlaceSellOrder(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to place sell order")
	}

	return txHash.String(), nil
}

// PlaceSplitLimitOrder mints binary pairs and lists unwanted side for sale
func PlaceSplitLimitOrder(
	client *tnclient.Client,
	queryID int,
	truePrice int,
	amount int64,
) (string, error) {
	ctx := context.Background()

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	if truePrice < 1 || truePrice > 99 {
		return "", errors.New("true_price must be between 1 and 99 cents")
	}
	if amount <= 0 {
		return "", errors.New("amount must be positive")
	}

	input := types.PlaceSplitLimitOrderInput{
		QueryID:   queryID,
		TruePrice: truePrice,
		Amount:    amount,
	}

	txHash, err := orderBook.PlaceSplitLimitOrder(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to place split limit order")
	}

	return txHash.String(), nil
}

// CancelOrder cancels an open buy or sell order
func CancelOrder(
	client *tnclient.Client,
	queryID int,
	outcome bool,
	price int,
) (string, error) {
	ctx := context.Background()

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	if price == 0 {
		return "", errors.New("cannot cancel holdings (price=0), use place_sell_order instead")
	}
	if price < -99 || price > 99 {
		return "", errors.New("price must be between -99 and 99 (excluding 0)")
	}

	input := types.CancelOrderInput{
		QueryID: queryID,
		Outcome: outcome,
		Price:   price,
	}

	txHash, err := orderBook.CancelOrder(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to cancel order")
	}

	return txHash.String(), nil
}

// ChangeBid atomically modifies buy order price and amount
func ChangeBid(
	client *tnclient.Client,
	queryID int,
	outcome bool,
	oldPrice int,
	newPrice int,
	newAmount int64,
) (string, error) {
	ctx := context.Background()

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	if oldPrice >= 0 || newPrice >= 0 {
		return "", errors.New("bid prices must be negative (buy orders)")
	}
	if newAmount <= 0 {
		return "", errors.New("new_amount must be positive")
	}

	input := types.ChangeBidInput{
		QueryID:   queryID,
		Outcome:   outcome,
		OldPrice:  oldPrice,
		NewPrice:  newPrice,
		NewAmount: newAmount,
	}

	txHash, err := orderBook.ChangeBid(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to change bid")
	}

	return txHash.String(), nil
}

// ChangeAsk atomically modifies sell order price and amount
func ChangeAsk(
	client *tnclient.Client,
	queryID int,
	outcome bool,
	oldPrice int,
	newPrice int,
	newAmount int64,
) (string, error) {
	ctx := context.Background()

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	if oldPrice <= 0 || newPrice <= 0 {
		return "", errors.New("ask prices must be positive (sell orders)")
	}
	if newAmount <= 0 {
		return "", errors.New("new_amount must be positive")
	}

	input := types.ChangeAskInput{
		QueryID:   queryID,
		Outcome:   outcome,
		OldPrice:  oldPrice,
		NewPrice:  newPrice,
		NewAmount: newAmount,
	}

	txHash, err := orderBook.ChangeAsk(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to change ask")
	}

	return txHash.String(), nil
}

// GetOrderBook retrieves all buy/sell orders for a market outcome
func GetOrderBook(client *tnclient.Client, queryID int, outcome bool) (string, error) {
	ctx := context.Background()

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	input := types.GetOrderBookInput{
		QueryID: queryID,
		Outcome: outcome,
	}

	results, err := orderBook.GetOrderBook(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to get order book")
	}

	entries := make([]map[string]any, len(results))
	for i, entry := range results {
		entries[i] = map[string]any{
			"participant_id": entry.ParticipantID,
			"wallet_address": convertBytesToHex(entry.WalletAddress),
			"price":          entry.Price,
			"amount":         entry.Amount,
			"last_updated":   entry.LastUpdated,
		}
	}

	jsonBytes, err := json.Marshal(entries)
	if err != nil {
		return "", errors.Wrap(err, "failed to marshal order book")
	}

	return string(jsonBytes), nil
}

// GetUserPositions retrieves caller's portfolio across all markets
func GetUserPositions(client *tnclient.Client) (string, error) {
	ctx := context.Background()

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	results, err := orderBook.GetUserPositions(ctx)
	if err != nil {
		return "", errors.Wrap(err, "failed to get user positions")
	}

	positions := make([]map[string]any, len(results))
	for i, pos := range results {
		positions[i] = map[string]any{
			"query_id":      pos.QueryID,
			"outcome":       pos.Outcome,
			"price":         pos.Price,
			"amount":        pos.Amount,
			"position_type": pos.PositionType,
		}
	}

	jsonBytes, err := json.Marshal(positions)
	if err != nil {
		return "", errors.Wrap(err, "failed to marshal positions")
	}

	return string(jsonBytes), nil
}

// GetMarketDepth returns aggregated volume per price level
func GetMarketDepth(client *tnclient.Client, queryID int, outcome bool) (string, error) {
	ctx := context.Background()

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	input := types.GetMarketDepthInput{
		QueryID: queryID,
		Outcome: outcome,
	}

	results, err := orderBook.GetMarketDepth(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to get market depth")
	}

	levels := make([]map[string]any, len(results))
	for i, level := range results {
		levels[i] = map[string]any{
			"price":       level.Price,
			"buy_volume":  level.BuyVolume,
			"sell_volume": level.SellVolume,
		}
	}

	jsonBytes, err := json.Marshal(levels)
	if err != nil {
		return "", errors.Wrap(err, "failed to marshal market depth")
	}

	return string(jsonBytes), nil
}

// GetBestPrices returns current bid/ask spread
func GetBestPrices(client *tnclient.Client, queryID int, outcome bool) (string, error) {
	ctx := context.Background()

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	input := types.GetBestPricesInput{
		QueryID: queryID,
		Outcome: outcome,
	}

	result, err := orderBook.GetBestPrices(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to get best prices")
	}

	prices := map[string]any{}

	if result.BestBid != nil {
		prices["best_bid"] = *result.BestBid
	} else {
		prices["best_bid"] = nil
	}

	if result.BestAsk != nil {
		prices["best_ask"] = *result.BestAsk
	} else {
		prices["best_ask"] = nil
	}

	if result.Spread != nil {
		prices["spread"] = *result.Spread
	} else {
		prices["spread"] = nil
	}

	jsonBytes, err := json.Marshal(prices)
	if err != nil {
		return "", errors.Wrap(err, "failed to marshal prices")
	}

	return string(jsonBytes), nil
}

// GetUserCollateral returns caller's total locked collateral value
func GetUserCollateral(client *tnclient.Client) (string, error) {
	ctx := context.Background()

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	result, err := orderBook.GetUserCollateral(ctx)
	if err != nil {
		return "", errors.Wrap(err, "failed to get user collateral")
	}

	collateral := map[string]any{
		"total_locked":      result.TotalLocked,
		"buy_orders_locked": result.BuyOrdersLocked,
		"shares_value":      result.SharesValue,
	}

	jsonBytes, err := json.Marshal(collateral)
	if err != nil {
		return "", errors.Wrap(err, "failed to marshal collateral")
	}

	return string(jsonBytes), nil
}

// SettleMarket settles a market using attestation results
func SettleMarket(client *tnclient.Client, queryID int) (string, error) {
	ctx := context.Background()

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	input := types.SettleMarketInput{
		QueryID: queryID,
	}

	txHash, err := orderBook.SettleMarket(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to settle market")
	}

	return txHash.String(), nil
}

// SampleLPRewards samples liquidity provider rewards for a block
func SampleLPRewards(client *tnclient.Client, queryID int, block int64) (string, error) {
	ctx := context.Background()

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	input := types.SampleLPRewardsInput{
		QueryID: queryID,
		Block:   block,
	}

	txHash, err := orderBook.SampleLPRewards(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to sample LP rewards")
	}

	return txHash.String(), nil
}

// GetDistributionSummary retrieves fee distribution summary for a market
func GetDistributionSummary(client *tnclient.Client, queryID int) (string, error) {
	ctx := context.Background()

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	input := types.GetDistributionSummaryInput{
		QueryID: queryID,
	}

	result, err := orderBook.GetDistributionSummary(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to get distribution summary")
	}

	summary := map[string]any{
		"distribution_id":        result.DistributionID,
		"total_fees_distributed": result.TotalFeesDistributed,
		"total_lp_count":         result.TotalLPCount,
		"block_count":            result.BlockCount,
		"distributed_at":         result.DistributedAt,
	}

	jsonBytes, err := json.Marshal(summary)
	if err != nil {
		return "", errors.Wrap(err, "failed to marshal distribution summary")
	}

	return string(jsonBytes), nil
}

// GetDistributionDetails retrieves per-LP reward details
func GetDistributionDetails(client *tnclient.Client, distributionID int) (string, error) {
	ctx := context.Background()

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	input := types.GetDistributionDetailsInput{
		DistributionID: distributionID,
	}

	results, err := orderBook.GetDistributionDetails(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to get distribution details")
	}

	details := make([]map[string]any, len(results))
	for i, detail := range results {
		details[i] = map[string]any{
			"wallet_address":       convertBytesToHex(detail.WalletAddress),
			"reward_amount":        detail.RewardAmount,
			"total_reward_percent": detail.TotalRewardPercent,
		}
	}

	jsonBytes, err := json.Marshal(details)
	if err != nil {
		return "", errors.Wrap(err, "failed to marshal distribution details")
	}

	return string(jsonBytes), nil
}

// GetParticipantRewardHistory retrieves reward history for a wallet
func GetParticipantRewardHistory(client *tnclient.Client, walletHex string) (string, error) {
	ctx := context.Background()

	orderBook, err := client.LoadOrderBook()
	if err != nil {
		return "", errors.Wrap(err, "failed to load order book")
	}

	input := types.GetParticipantRewardHistoryInput{
		WalletHex: walletHex,
	}

	results, err := orderBook.GetParticipantRewardHistory(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to get participant reward history")
	}

	history := make([]map[string]any, len(results))
	for i, h := range results {
		history[i] = map[string]any{
			"distribution_id":      h.DistributionID,
			"query_id":             h.QueryID,
			"reward_amount":        h.RewardAmount,
			"total_reward_percent": h.TotalRewardPercent,
			"distributed_at":       h.DistributedAt,
		}
	}

	jsonBytes, err := json.Marshal(history)
	if err != nil {
		return "", errors.Wrap(err, "failed to marshal reward history")
	}

	return string(jsonBytes), nil
}

// Helper: Convert MarketInfo to map for JSON serialization
func marketInfoToMap(market *types.MarketInfo) map[string]any {
	result := map[string]any{
		"id":               market.ID,
		"hash":             convertBytesToHex(market.Hash),
		"query_components": convertBytesToHex(market.QueryComponents),
		"bridge":           market.Bridge,
		"settle_time":      market.SettleTime,
		"settled":          market.Settled,
		"max_spread":       market.MaxSpread,
		"min_order_size":   market.MinOrderSize,
		"created_at":       market.CreatedAt,
		"creator":          convertBytesToHex(market.Creator),
	}

	if market.WinningOutcome != nil {
		result["winning_outcome"] = *market.WinningOutcome
	} else {
		result["winning_outcome"] = nil
	}

	if market.SettledAt != nil {
		result["settled_at"] = *market.SettledAt
	} else {
		result["settled_at"] = nil
	}

	return result
}

// ═══════════════════════════════════════════════════════════════
//           QUERY COMPONENTS ENCODING
// ═══════════════════════════════════════════════════════════════

// MarketData represents the structured content of a prediction market's query components
type MarketData struct {
	DataProvider string   `json:"data_provider"`
	StreamID     string   `json:"stream_id"`
	ActionID     string   `json:"action_id"`
	Type         string   `json:"type"`       // "above", "below", "between", "equals"
	Thresholds   []string `json:"thresholds"` // Formatted numeric values
}

// DecodeMarketData decodes ABI-encoded query_components into high-level MarketData JSON string
func DecodeMarketData(encoded []byte) (string, error) {
	market, err := contractsapi.DecodeMarketData(encoded)
	if err != nil {
		return "", err
	}

	// Re-map to local struct for JSON consistency if needed, 
    // or just return the contractsapi struct serialized.
    // contractsapi.MarketData is already JSON-annotated.
	jsonBytes, err := json.Marshal(market)
	if err != nil {
		return "", errors.Wrap(err, "failed to marshal market data")
	}

	return string(jsonBytes), nil
}

// DecodeQueryComponents decodes ABI-encoded query_components back to its parts JSON
func DecodeQueryComponents(encoded []byte) (string, error) {
	dataProvider, streamID, actionID, args, err := contractsapi.DecodeQueryComponents(encoded)
	if err != nil {
		return "", err
	}

	res := map[string]any{
		"data_provider": dataProvider,
		"stream_id":     streamID,
		"action_id":     actionID,
		"args":          convertBytesToHex(args),
	}

	jsonBytes, err := json.Marshal(res)
	if err != nil {
		return "", err
	}

	return string(jsonBytes), nil
}

// EncodeQueryComponents ABI-encodes query components tuple.
// Parameters:
//   - dataProvider: 0x-prefixed Ethereum address (42 chars)
//   - streamID: 32-character stream ID
//   - actionID: Action name (e.g., "price_above_threshold")
//   - args: Pre-encoded action arguments (from EncodeActionArgs)
//
// Returns the ABI-encoded query_components bytes
func EncodeQueryComponents(dataProvider, streamID, actionID string, args []byte) ([]byte, error) {
	return contractsapi.EncodeQueryComponents(dataProvider, streamID, actionID, args)
}

// DecodeActionArgs decodes canonical bytes back into action arguments JSON
func DecodeActionArgs(data []byte) (string, error) {
	args, err := contractsapi.DecodeActionArgs(data)
	if err != nil {
		return "", err
	}

	// Convert arguments to strings for easy JSON representation
	strArgs := make([]string, len(args))
	for i, arg := range args {
		strArgs[i] = convertToString(arg)
	}

	jsonBytes, err := json.Marshal(strArgs)
	if err != nil {
		return "", err
	}

	return string(jsonBytes), nil
}

// EncodeActionArgs encodes action arguments for use in query_components.
// argsJSON should be a JSON array of arguments
// (e.g., '["0x123...", "stbtc...", 1735689600, "100000", null]')
func EncodeActionArgs(argsJSON string) ([]byte, error) {
	var args []any
	if argsJSON != "" && argsJSON != "[]" {
		decoder := json.NewDecoder(strings.NewReader(argsJSON))
		decoder.UseNumber() // Preserve numbers as json.Number
		err := decoder.Decode(&args)
		if err != nil {
			return nil, errors.Wrap(err, "failed to unmarshal args JSON")
		}

		// Convert json.Number to appropriate types
		for i, arg := range args {
			if num, ok := arg.(json.Number); ok {
				if intVal, err := num.Int64(); err == nil {
					args[i] = intVal
				} else if floatVal, err := num.Float64(); err == nil {
					args[i] = floatVal
				}
			}
		}
	}

	return contractsapi.EncodeActionArgs(args)
}

// ═══════════════════════════════════════════════════════════════
//           ACTION REGISTRY
// ═══════════════════════════════════════════════════════════════

// GetActionID returns the action ID for a given action name, or 0 if not found
func GetActionID(name string) int {
	return int(types.GetActionID(name))
}

// GetActionName returns the action name for a given action ID, or empty string if not found
func GetActionName(id int) string {
	return types.GetActionName(uint16(id))
}

// IsBinaryAction returns true if the action name corresponds to a binary action (IDs 6-9)
func IsBinaryAction(name string) bool {
	return types.IsBinaryAction(name)
}

// IsBinaryActionID returns true if the action ID corresponds to a binary action (6-9)
func IsBinaryActionID(id int) bool {
	return types.IsBinaryActionID(uint16(id))
}

// ValidateActionName returns an error if the action name is not recognized
func ValidateActionName(name string) error {
	return types.ValidateActionName(name)
}

// GetActionRegistry returns the full action registry as JSON
func GetActionRegistry() (string, error) {
	registry := make(map[string]map[string]any)
	for name, info := range types.ActionRegistry {
		registry[name] = map[string]any{
			"id":          info.ID,
			"name":        info.Name,
			"is_binary":   info.IsBinary,
			"description": info.Description,
		}
	}
	jsonBytes, err := json.Marshal(registry)
	if err != nil {
		return "", errors.Wrap(err, "failed to marshal action registry")
	}
	return string(jsonBytes), nil
}

// ═══════════════════════════════════════════════════════════════
//           BOOLEAN RESULT PARSING
// ═══════════════════════════════════════════════════════════════

// ParseBooleanResult extracts a boolean result from a binary action attestation payload.
// This is specifically for binary attestation actions (IDs 6-9).
// Returns JSON with result (bool) and action_id (int).
func ParseBooleanResult(payload []byte) (string, error) {
	result, actionID, err := contractsapi.ParseBooleanResult(payload)
	if err != nil {
		return "", err
	}

	response := map[string]any{
		"result":    result,
		"action_id": int(actionID),
	}

	jsonBytes, err := json.Marshal(response)
	if err != nil {
		return "", errors.Wrap(err, "failed to marshal result")
	}
	return string(jsonBytes), nil
}

// ═══════════════════════════════════════════════════════════════
//           BINARY MARKET CREATION HELPERS
// ═══════════════════════════════════════════════════════════════

// CreatePriceAboveThresholdMarket creates a binary prediction market that settles
// TRUE if the stream value exceeds the threshold at the specified timestamp.
//
// Example: "Will BTC exceed $100,000 by December 31, 2025?"
//
// Parameters:
//   - dataProvider: 0x-prefixed Ethereum address of the data provider
//   - streamID: 32-character stream ID
//   - timestamp: Unix timestamp to check the value at
//   - threshold: Threshold value as decimal string (e.g., "100000")
//   - frozenAt: Unix timestamp to freeze the value lookup (-1 for nil)
//   - bridge: Bridge namespace (hoodi_tt2, sepolia_bridge, ethereum_bridge)
//   - settleTime: Unix timestamp when market can be settled
//   - maxSpread: Maximum spread for LP rewards (1-50 cents)
//   - minOrderSize: Minimum order size for LP rewards
func CreatePriceAboveThresholdMarket(
	client *tnclient.Client,
	dataProvider string,
	streamID string,
	timestamp int64,
	threshold string,
	frozenAt int64,
	bridge string,
	settleTime int64,
	maxSpread int,
	minOrderSize int64,
) (string, error) {
	// Build action arguments
	var frozenAtPtr *int64
	if frozenAt >= 0 {
		frozenAtPtr = &frozenAt
	}

	input := types.PriceAboveThresholdInput{
		DataProvider: dataProvider,
		StreamID:     streamID,
		Timestamp:    timestamp,
		Threshold:    threshold,
		FrozenAt:     frozenAtPtr,
	}

	queryComponents, err := contractsapi.BuildPriceAboveThresholdQueryComponents(input)
	if err != nil {
		return "", errors.Wrap(err, "failed to build query components")
	}

	return CreateMarket(client, bridge, queryComponents, settleTime, maxSpread, minOrderSize)
}

// CreatePriceBelowThresholdMarket creates a binary prediction market that settles
// TRUE if the stream value is below the threshold at the specified timestamp.
//
// Example: "Will unemployment drop below 4% by Q2 2025?"
func CreatePriceBelowThresholdMarket(
	client *tnclient.Client,
	dataProvider string,
	streamID string,
	timestamp int64,
	threshold string,
	frozenAt int64,
	bridge string,
	settleTime int64,
	maxSpread int,
	minOrderSize int64,
) (string, error) {
	var frozenAtPtr *int64
	if frozenAt >= 0 {
		frozenAtPtr = &frozenAt
	}

	input := types.PriceBelowThresholdInput{
		DataProvider: dataProvider,
		StreamID:     streamID,
		Timestamp:    timestamp,
		Threshold:    threshold,
		FrozenAt:     frozenAtPtr,
	}

	queryComponents, err := contractsapi.BuildPriceBelowThresholdQueryComponents(input)
	if err != nil {
		return "", errors.Wrap(err, "failed to build query components")
	}

	return CreateMarket(client, bridge, queryComponents, settleTime, maxSpread, minOrderSize)
}

// CreateValueInRangeMarket creates a binary prediction market that settles
// TRUE if the stream value is within the specified range (inclusive) at the timestamp.
//
// Example: "Will BTC stay between $90k-$110k on settlement date?"
func CreateValueInRangeMarket(
	client *tnclient.Client,
	dataProvider string,
	streamID string,
	timestamp int64,
	minValue string,
	maxValue string,
	frozenAt int64,
	bridge string,
	settleTime int64,
	maxSpread int,
	minOrderSize int64,
) (string, error) {
	var frozenAtPtr *int64
	if frozenAt >= 0 {
		frozenAtPtr = &frozenAt
	}

	input := types.ValueInRangeInput{
		DataProvider: dataProvider,
		StreamID:     streamID,
		Timestamp:    timestamp,
		MinValue:     minValue,
		MaxValue:     maxValue,
		FrozenAt:     frozenAtPtr,
	}

	queryComponents, err := contractsapi.BuildValueInRangeQueryComponents(input)
	if err != nil {
		return "", errors.Wrap(err, "failed to build query components")
	}

	return CreateMarket(client, bridge, queryComponents, settleTime, maxSpread, minOrderSize)
}

// CreateValueEqualsMarket creates a binary prediction market that settles
// TRUE if the stream value equals the target (within tolerance) at the timestamp.
//
// Example: "Will the Fed rate be exactly 5.25%?"
func CreateValueEqualsMarket(
	client *tnclient.Client,
	dataProvider string,
	streamID string,
	timestamp int64,
	targetValue string,
	tolerance string,
	frozenAt int64,
	bridge string,
	settleTime int64,
	maxSpread int,
	minOrderSize int64,
) (string, error) {
	var frozenAtPtr *int64
	if frozenAt >= 0 {
		frozenAtPtr = &frozenAt
	}

	input := types.ValueEqualsInput{
		DataProvider: dataProvider,
		StreamID:     streamID,
		Timestamp:    timestamp,
		TargetValue:  targetValue,
		Tolerance:    tolerance,
		FrozenAt:     frozenAtPtr,
	}

	queryComponents, err := contractsapi.BuildValueEqualsQueryComponents(input)
	if err != nil {
		return "", errors.Wrap(err, "failed to build query components")
	}

	return CreateMarket(client, bridge, queryComponents, settleTime, maxSpread, minOrderSize)
}

// ═══════════════════════════════════════════════════════════════
//           BRIDGE FUNCTIONS
// ═══════════════════════════════════════════════════════════════

// GetWalletBalance retrieves the wallet balance for a specific bridge instance
func GetWalletBalance(client *tnclient.Client, bridgeIdentifier string, walletAddress string) (string, error) {
	ctx := context.Background()
	balance, err := client.GetWalletBalance(ctx, bridgeIdentifier, walletAddress)
	if err != nil {
		return "", errors.Wrap(err, "failed to get wallet balance")
	}
	return balance, nil
}

// Withdraw performs a withdrawal operation by bridging tokens from TN to a destination chain
func Withdraw(client *tnclient.Client, bridgeIdentifier string, amount string, recipient string) (string, error) {
	ctx := context.Background()
	txHash, err := client.Withdraw(ctx, bridgeIdentifier, amount, recipient)
	if err != nil {
		return "", errors.Wrap(err, "failed to withdraw tokens")
	}
	return txHash, nil
}

// GetWithdrawalProof retrieves the proofs and signatures needed to claim a withdrawal on EVM.
func GetWithdrawalProof(client *tnclient.Client, bridgeIdentifier string, wallet string) (string, error) {
	ctx := context.Background()

	input := types.GetWithdrawalProofInput{
		BridgeIdentifier: bridgeIdentifier,
		Wallet:           wallet,
	}

	actions, err := client.LoadActions()
	if err != nil {
		return "", errors.Wrap(err, "failed to load actions")
	}

	results, err := actions.GetWithdrawalProof(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to get withdrawal proof")
	}

	jsonBytes, err := json.Marshal(results)
	if err != nil {
		return "", errors.Wrap(err, "failed to marshal withdrawal proofs")
	}

	return string(jsonBytes), nil
}

// GetHistory retrieves the transaction history for a wallet on a specific bridge
func GetHistory(client *tnclient.Client, bridgeIdentifier string, wallet string, limit int, offset int) (string, error) {
	ctx := context.Background()

	input := types.GetHistoryInput{
		BridgeIdentifier: bridgeIdentifier,
		Wallet:           wallet,
		Limit:            &limit,
		Offset:           &offset,
	}

	actions, err := client.LoadActions()
	if err != nil {
		return "", errors.Wrap(err, "failed to load actions")
	}

	results, err := actions.GetHistory(ctx, input)
	if err != nil {
		return "", errors.Wrap(err, "failed to get bridge history")
	}

	jsonBytes, err := json.Marshal(results)
	if err != nil {
		return "", errors.Wrap(err, "failed to marshal bridge history")
	}

	return string(jsonBytes), nil
}
