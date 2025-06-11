package exports

import (
	"context"
	"encoding/json"
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
	StreamTypeComposed  types.StreamType    = types.StreamTypeComposed
	StreamTypePrimitive types.StreamType    = types.StreamTypePrimitive
	VisibilityPublic    util.VisibilityEnum = util.PublicVisibility
	VisibilityPrivate   util.VisibilityEnum = util.PrivateVisibility
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

	if frozenAt != -1 {
		result.FrozenAt = &frozenAt
	}

	if after != -1 {
		result.After = &after
	}

	return result
}

// GetFirstRecord retrieves the first record of a stream after a given date
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
	result["date"] = convertToString(record.EventTime)
	result["value"] = convertToString(record.Value)

	return result, nil
}

// GetIndex retrieves index values from a stream
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
func NewTaxonomyItemInput(client *tnclient.Client, stream_id string, weight float64) types.TaxonomyItem {
	streamIdObj, err := util.NewStreamId(stream_id)
	if err != nil {
		return types.TaxonomyItem{}
	}

	return types.TaxonomyItem{
		ChildStream: client.OwnStreamLocator(*streamIdObj),
		Weight:      weight,
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
			"stream_id": childStream.ChildStream.StreamId.String(),
			"weight":    convertToString(childStream.Weight),
		})
	}
	childStreamsJSON, err := json.Marshal(childStreams)
	if err != nil {
		return map[string]string{}, err
	}

	res := map[string]string{
		"stream_id":      streamId,
		"child_streams":  string(childStreamsJSON),
		"start_date":     parseUnixTimestamp(result.StartDate),
		"created_at":     parseUnixTimestamp(&result.CreatedAt),
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

func parseUnixTimestamp(timestamp *int) string {
	if timestamp == nil {
		return ""
	}

	unixTimestamp := int64(*timestamp)
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
	case util.EthereumAddress:
		return v.Address()
	case *util.EthereumAddress:
		return v.Address()
	case fmt.Stringer:
		return v.String()
	default:
		log.Printf("Warning: Failed to convert argument to string from type %T: %v\n", val, val)
		return fmt.Sprintf("%v", val)
	}
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
// NOTE: This assumes that the underlying go-sdk's IRoleManagement interface
// has been updated to include an AreMembersOf method, and that corresponding
// input (AreMembersOfInput) and output (e.g. []*RoleMemberStatus) types exist.
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
