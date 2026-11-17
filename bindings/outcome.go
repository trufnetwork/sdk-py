package exports

// Outcome market bindings: the actions with ids 13-16 (node migration 063).
// Each answers YES, NO or INVALID, and a market on one is refunded (INVALID)
// when its print has not arrived by block time timestamp + window.
//
// gopy cannot carry Python's None into a Go string, so an open bound arrives
// as "", the same sentinel the v1 index-change bindings use. The Python layer
// refuses "" from callers, so here it can only mean None.

import (
	"encoding/json"

	"github.com/pkg/errors"
	"github.com/trufnetwork/sdk-go/core/contractsapi"
	"github.com/trufnetwork/sdk-go/core/tnclient"
	"github.com/trufnetwork/sdk-go/core/types"
)

// openBound turns the "" sentinel into nil (an open tail) and anything else
// into a pointer to its own copy.
func openBound(value string) *string {
	if value == "" {
		return nil
	}
	v := value
	return &v
}

// BuildPriceAboveThresholdV2QueryComponents builds the query components of a
// price_above_threshold_v2 market without submitting anything.
func BuildPriceAboveThresholdV2QueryComponents(
	dataProvider string,
	streamID string,
	timestamp int64,
	window int64,
	tolerance int64,
	threshold string,
) ([]byte, error) {
	return contractsapi.BuildPriceAboveThresholdV2QueryComponents(types.PriceAboveThresholdV2Input{
		DataProvider: dataProvider,
		StreamID:     streamID,
		Timestamp:    timestamp,
		Window:       window,
		Tolerance:    tolerance,
		Threshold:    threshold,
	})
}

// BuildPriceBelowThresholdV2QueryComponents builds the query components of a
// price_below_threshold_v2 market without submitting anything.
func BuildPriceBelowThresholdV2QueryComponents(
	dataProvider string,
	streamID string,
	timestamp int64,
	window int64,
	tolerance int64,
	threshold string,
) ([]byte, error) {
	return contractsapi.BuildPriceBelowThresholdV2QueryComponents(types.PriceBelowThresholdV2Input{
		DataProvider: dataProvider,
		StreamID:     streamID,
		Timestamp:    timestamp,
		Window:       window,
		Tolerance:    tolerance,
		Threshold:    threshold,
	})
}

// BuildValueInRangeV2QueryComponents builds the query components of a
// value_in_range_v2 market without submitting anything. "" is an open bound.
func BuildValueInRangeV2QueryComponents(
	dataProvider string,
	streamID string,
	timestamp int64,
	window int64,
	tolerance int64,
	minValue string,
	maxValue string,
) ([]byte, error) {
	return contractsapi.BuildValueInRangeV2QueryComponents(types.ValueInRangeV2Input{
		DataProvider: dataProvider,
		StreamID:     streamID,
		Timestamp:    timestamp,
		Window:       window,
		Tolerance:    tolerance,
		MinValue:     openBound(minValue),
		MaxValue:     openBound(maxValue),
	})
}

// BuildIndexChangeInRangeV2QueryComponents builds the query components of an
// index_change_in_range_v2 market without submitting anything. "" is an open
// bound.
func BuildIndexChangeInRangeV2QueryComponents(
	dataProvider string,
	streamID string,
	timestamp int64,
	window int64,
	tolerance int64,
	timeInterval int64,
	minChange string,
	maxChange string,
) ([]byte, error) {
	return contractsapi.BuildIndexChangeInRangeV2QueryComponents(types.IndexChangeInRangeV2Input{
		DataProvider: dataProvider,
		StreamID:     streamID,
		Timestamp:    timestamp,
		Window:       window,
		Tolerance:    tolerance,
		TimeInterval: timeInterval,
		MinChange:    openBound(minChange),
		MaxChange:    openBound(maxChange),
	})
}

// CreatePriceAboveThresholdV2Market creates a market that settles YES if the
// latest record stamped in [timestamp - tolerance, timestamp] is above the
// threshold, NO if not, and is refunded if no such record exists by block
// time timestamp + window.
func CreatePriceAboveThresholdV2Market(
	client *tnclient.Client,
	dataProvider string,
	streamID string,
	timestamp int64,
	window int64,
	tolerance int64,
	threshold string,
	bridge string,
	settleTime int64,
	maxSpread int,
	minOrderSize int64,
) (string, error) {
	queryComponents, err := BuildPriceAboveThresholdV2QueryComponents(
		dataProvider, streamID, timestamp, window, tolerance, threshold)
	if err != nil {
		return "", errors.Wrap(err, "failed to build query components")
	}
	return CreateMarket(client, bridge, queryComponents, settleTime, maxSpread, minOrderSize)
}

// CreatePriceBelowThresholdV2Market creates a market that settles YES if the
// latest record stamped in [timestamp - tolerance, timestamp] is below the
// threshold, NO if not, and is refunded if no such record exists by block
// time timestamp + window.
func CreatePriceBelowThresholdV2Market(
	client *tnclient.Client,
	dataProvider string,
	streamID string,
	timestamp int64,
	window int64,
	tolerance int64,
	threshold string,
	bridge string,
	settleTime int64,
	maxSpread int,
	minOrderSize int64,
) (string, error) {
	queryComponents, err := BuildPriceBelowThresholdV2QueryComponents(
		dataProvider, streamID, timestamp, window, tolerance, threshold)
	if err != nil {
		return "", errors.Wrap(err, "failed to build query components")
	}
	return CreateMarket(client, bridge, queryComponents, settleTime, maxSpread, minOrderSize)
}

// CreateValueInRangeV2Market creates a market that settles YES if the latest
// record stamped in [timestamp - tolerance, timestamp] is in
// [minValue, maxValue), NO if not, and is refunded if no such record exists by
// block time timestamp + window. "" is an open bound.
func CreateValueInRangeV2Market(
	client *tnclient.Client,
	dataProvider string,
	streamID string,
	timestamp int64,
	window int64,
	tolerance int64,
	minValue string,
	maxValue string,
	bridge string,
	settleTime int64,
	maxSpread int,
	minOrderSize int64,
) (string, error) {
	queryComponents, err := BuildValueInRangeV2QueryComponents(
		dataProvider, streamID, timestamp, window, tolerance, minValue, maxValue)
	if err != nil {
		return "", errors.Wrap(err, "failed to build query components")
	}
	return CreateMarket(client, bridge, queryComponents, settleTime, maxSpread, minOrderSize)
}

// CreateIndexChangeInRangeV2Market creates a market that settles YES if the
// stream's percent change over timeInterval is in [minChange, maxChange), NO
// if not, and is refunded if a record is missing by block time
// timestamp + window. "" is an open bound.
func CreateIndexChangeInRangeV2Market(
	client *tnclient.Client,
	dataProvider string,
	streamID string,
	timestamp int64,
	window int64,
	tolerance int64,
	timeInterval int64,
	minChange string,
	maxChange string,
	bridge string,
	settleTime int64,
	maxSpread int,
	minOrderSize int64,
) (string, error) {
	queryComponents, err := BuildIndexChangeInRangeV2QueryComponents(
		dataProvider, streamID, timestamp, window, tolerance, timeInterval, minChange, maxChange)
	if err != nil {
		return "", errors.Wrap(err, "failed to build query components")
	}
	return CreateMarket(client, bridge, queryComponents, settleTime, maxSpread, minOrderSize)
}

// ParseOutcomeResult reads the result of an outcome action attestation
// (ids 13-16) from its canonical payload (without the signature).
// Returns JSON with outcome (1 YES, 0 NO, -1 INVALID) and action_id. Any other
// action id, and any value other than 1e18, 0 or -1e18, is an error.
func ParseOutcomeResult(payload []byte) (string, error) {
	outcome, actionID, err := contractsapi.ParseOutcomeResult(payload)
	if err != nil {
		return "", err
	}
	jsonBytes, err := json.Marshal(map[string]any{
		"outcome":   outcome,
		"action_id": int(actionID),
	})
	if err != nil {
		return "", errors.Wrap(err, "failed to marshal result")
	}
	return string(jsonBytes), nil
}
