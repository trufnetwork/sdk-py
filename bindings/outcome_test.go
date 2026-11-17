package exports

// Unit tests for the outcome market bindings (ids 13-16). sdk-py
// tests/test_outcome_markets.py checks the same bindings from Python.

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
	"math/big"
	"strings"
	"testing"

	"github.com/ethereum/go-ethereum/accounts/abi"
	"github.com/trufnetwork/sdk-go/core/contractsapi"
	"github.com/trufnetwork/sdk-go/core/types"
)

const (
	testProvider = "0x4710a8d8f0d845da110086812a32de6d90d7ff5c"
	testStream   = "stbtcusd000000000000000000000000"
)

// outcomePayload builds a canonical attestation payload for actionID whose
// result is one data point with the given value.
func outcomePayload(t *testing.T, actionID uint16, value *big.Int) []byte {
	t.Helper()

	uints, err := abi.NewType("uint256[]", "", nil)
	if err != nil {
		t.Fatal(err)
	}
	ints, err := abi.NewType("int256[]", "", nil)
	if err != nil {
		t.Fatal(err)
	}
	result, err := abi.Arguments{{Type: uints}, {Type: ints}}.Pack(
		[]*big.Int{big.NewInt(1767225600)}, []*big.Int{value})
	if err != nil {
		t.Fatal(err)
	}

	var buf bytes.Buffer
	lp := func(b []byte) {
		_ = binary.Write(&buf, binary.BigEndian, uint32(len(b)))
		buf.Write(b)
	}
	buf.Write([]byte{1, 0})
	_ = binary.Write(&buf, binary.BigEndian, uint64(123))
	lp([]byte(testProvider))
	lp([]byte(testStream))
	_ = binary.Write(&buf, binary.BigEndian, actionID)
	lp([]byte{0, 0, 0, 0})
	lp(result)
	return buf.Bytes()
}

func TestParseOutcomeResult_ReturnsOutcomeAndActionID(t *testing.T) {
	unit := new(big.Int).Exp(big.NewInt(10), big.NewInt(18), nil)
	cases := []struct {
		value *big.Int
		want  int
	}{
		{unit, 1},
		{big.NewInt(0), 0},
		{new(big.Int).Neg(unit), -1},
	}
	for _, id := range []uint16{13, 14, 15, 16} {
		for _, c := range cases {
			got, err := ParseOutcomeResult(outcomePayload(t, id, c.value))
			if err != nil {
				t.Fatalf("id %d value %s: %v", id, c.value, err)
			}
			var decoded map[string]any
			if err := json.Unmarshal([]byte(got), &decoded); err != nil {
				t.Fatal(err)
			}
			if len(decoded) != 2 || decoded["outcome"] != float64(c.want) || decoded["action_id"] != float64(id) {
				t.Fatalf("id %d value %s: got %s", id, c.value, got)
			}
		}
	}
}

func TestParseOutcomeResult_RefusesOtherActionsAndValues(t *testing.T) {
	unit := new(big.Int).Exp(big.NewInt(10), big.NewInt(18), nil)
	if _, err := ParseOutcomeResult(outcomePayload(t, 12, unit)); err == nil {
		t.Fatal("id 12 is binary and must be refused")
	}
	if _, err := ParseOutcomeResult(outcomePayload(t, 14, new(big.Int).Mul(unit, big.NewInt(2)))); err == nil {
		t.Fatal("2e18 is not an outcome and must be refused")
	}
	if _, err := ParseBooleanResult(outcomePayload(t, 14, unit)); err == nil {
		t.Fatal("ParseBooleanResult must refuse an outcome action")
	}
}

// TestBuildV2_EmptyStringIsAnOpenBound checks that "" reaches sdk-go as nil,
// so the bytes match a build with a nil bound.
func TestBuildV2_EmptyStringIsAnOpenBound(t *testing.T) {
	low := "100"
	want, err := contractsapi.BuildValueInRangeV2QueryComponents(types.ValueInRangeV2Input{
		DataProvider: testProvider, StreamID: testStream,
		Timestamp: 1767139200, Window: 259200, Tolerance: 86400,
		MinValue: &low,
	})
	if err != nil {
		t.Fatal(err)
	}
	got, err := BuildValueInRangeV2QueryComponents(testProvider, testStream, 1767139200, 259200, 86400, "100", "")
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(got, want) {
		t.Fatal("an empty max_value must build the same bytes as a nil one")
	}

	high := "3"
	want, err = contractsapi.BuildIndexChangeInRangeV2QueryComponents(types.IndexChangeInRangeV2Input{
		DataProvider: testProvider, StreamID: testStream,
		Timestamp: 1759276800, Window: 7776000, Tolerance: 172800, TimeInterval: 31536000,
		MaxChange: &high,
	})
	if err != nil {
		t.Fatal(err)
	}
	got, err = BuildIndexChangeInRangeV2QueryComponents(testProvider, testStream, 1759276800, 7776000, 172800, 31536000, "", "3")
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(got, want) {
		t.Fatal("an empty min_change must build the same bytes as a nil one")
	}

	if _, err := BuildValueInRangeV2QueryComponents(testProvider, testStream, 1767139200, 259200, 86400, "", ""); err == nil ||
		!strings.Contains(err.Error(), "at least one of min_value or max_value") {
		t.Fatalf("both bounds open must be refused, got %v", err)
	}
}

func TestGetActionRegistry_CarriesTheOutcomeFlag(t *testing.T) {
	raw, err := GetActionRegistry()
	if err != nil {
		t.Fatal(err)
	}
	var registry map[string]map[string]any
	if err := json.Unmarshal([]byte(raw), &registry); err != nil {
		t.Fatal(err)
	}
	for name, info := range registry {
		id := uint16(info["id"].(float64))
		outcome, ok := info["is_outcome"].(bool)
		if !ok {
			t.Fatalf("%s has no is_outcome flag", name)
		}
		if want := id >= 13 && id <= 16; outcome != want {
			t.Fatalf("%s (id %d): is_outcome %v, want %v", name, id, outcome, want)
		}
		if outcome && info["is_binary"].(bool) {
			t.Fatalf("%s is both binary and outcome", name)
		}
	}
}

// TestCreateV2_ChecksInputsBeforeTheClient checks that a create binding refuses
// bad inputs before it touches the client, so nothing is sent.
func TestCreateV2_ChecksInputsBeforeTheClient(t *testing.T) {
	_, err := CreateValueInRangeV2Market(nil, testProvider, testStream, 1767139200, 86400, 259200,
		"1", "2", "eth_usdc", 1767484800, 5, 20)
	if err == nil || !strings.Contains(err.Error(), "must not be less than tolerance") {
		t.Fatalf("window < tolerance must be refused before the client is used, got %v", err)
	}
	_, err = CreatePriceAboveThresholdV2Market(nil, testProvider, testStream, 1767139200, 259200, 86400,
		"", "eth_usdc", 1767484800, 5, 20)
	if err == nil || !strings.Contains(err.Error(), "threshold is required") {
		t.Fatalf("an empty threshold must be refused before the client is used, got %v", err)
	}
	_, err = CreateIndexChangeInRangeV2Market(nil, testProvider, testStream, 1759276800, 7776000, 172800,
		345600, "2", "", "eth_usdc", 1767484800, 5, 20)
	if err == nil || !strings.Contains(err.Error(), "more than twice tolerance") {
		t.Fatalf("time_interval <= 2*tolerance must be refused before the client is used, got %v", err)
	}
}
