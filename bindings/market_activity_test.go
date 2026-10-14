package exports

// Unit tests for marketActivityJSON, the step that turns sdk-go's MarketActivity
// into the JSON Python decodes. sdk-py tests/test_market_activity.py guards the
// Python side of the same JSON.

import (
	"bytes"
	"encoding/json"
	"reflect"
	"testing"

	"github.com/trufnetwork/sdk-go/core/types"
)

// decodeActivityJSON marshals a MarketActivity the way GetMarketActivity does
// and decodes it with every number kept as its literal text.
func decodeActivityJSON(t *testing.T, a *types.MarketActivity) map[string]any {
	t.Helper()

	raw, err := json.Marshal(marketActivityJSON(a))
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var got map[string]any
	if err := dec.Decode(&got); err != nil {
		t.Fatalf("decode %s: %v", raw, err)
	}
	return got
}

func TestMarketActivityJSON_UsesTheActionColumnNames(t *testing.T) {
	first, last := int64(1791407913), int64(1791476117)
	got := decodeActivityJSON(t, &types.MarketActivity{
		Bridge:            "eth_usdc",
		VolumeCents:       "1145",
		DirectCents:       "545",
		MintBurnCents:     "600",
		UniqueTraders:     2,
		FillCount:         6,
		DirectFillCount:   4,
		SharesTraded:      20,
		FirstEventTs:      &first,
		LastEventTs:       &last,
		CoverageFromBlock: 2692744,
		CoverageComplete:  true,
	})

	want := map[string]any{
		"bridge":              "eth_usdc",
		"volume_cents":        "1145",
		"direct_cents":        "545",
		"mint_burn_cents":     "600",
		"unique_traders":      json.Number("2"),
		"fill_count":          json.Number("6"),
		"direct_fill_count":   json.Number("4"),
		"shares_traded":       json.Number("20"),
		"first_event_ts":      json.Number("1791407913"),
		"last_event_ts":       json.Number("1791476117"),
		"coverage_from_block": json.Number("2692744"),
		"coverage_complete":   true,
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got  %#v\nwant %#v", got, want)
	}
}

func TestMarketActivityJSON_KeepsCentsAsStrings(t *testing.T) {
	// Above math.MaxInt64: only a string carries it exactly.
	got := decodeActivityJSON(t, &types.MarketActivity{
		Bridge:        "eth_usdc",
		VolumeCents:   "123456789012345678901234567890",
		DirectCents:   "123456789012345678901234567290",
		MintBurnCents: "600",
	})

	for key, want := range map[string]string{
		"volume_cents":    "123456789012345678901234567890",
		"direct_cents":    "123456789012345678901234567290",
		"mint_burn_cents": "600",
	} {
		if s, ok := got[key].(string); !ok || s != want {
			t.Errorf("%s = %#v, want the string %q", key, got[key], want)
		}
	}
}

func TestMarketActivityJSON_NothingTraded(t *testing.T) {
	// What a node holding no order events returns for a market that exists.
	got := decodeActivityJSON(t, &types.MarketActivity{
		Bridge:        "hoodi_tt2",
		VolumeCents:   "0",
		DirectCents:   "0",
		MintBurnCents: "0",
	})

	for _, key := range []string{"first_event_ts", "last_event_ts"} {
		v, present := got[key]
		if !present || v != nil {
			t.Errorf("%s = %#v (present %t), want null", key, v, present)
		}
	}
	if got["coverage_from_block"] != json.Number("0") {
		t.Errorf("coverage_from_block = %#v, want 0", got["coverage_from_block"])
	}
	if got["coverage_complete"] != false {
		t.Errorf("coverage_complete = %#v, want false", got["coverage_complete"])
	}
}
