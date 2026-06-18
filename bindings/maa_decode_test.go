package exports

// Unit tests for decodeMAAArgs — the JSON -> native-Go-argument step of a maa_exec submission.
//
// These are the Go counterpart to sdk-py tests/test_maa_exec.py (which guards the Python-side JSON
// the binding receives). Here we guard what the binding turns that JSON into: the action-args encoder
// downstream (kwil EncodeValue) rejects json.Number and only produces a NUMERIC EncodedValue from a
// *types.Decimal, so the two behaviors that matter are (1) every JSON integer becomes an int64 at any
// depth and (2) a numeric marker becomes a precision/scale-exact *types.Decimal.

import (
	"testing"

	kwilTypes "github.com/trufnetwork/kwil-db/core/types"
)

func TestDecodeMAAArgs_EmptyYieldsNoArgs(t *testing.T) {
	for _, in := range []string{"", "[]"} {
		args, err := decodeMAAArgs(in)
		if err != nil {
			t.Fatalf("decodeMAAArgs(%q) error: %v", in, err)
		}
		if args != nil {
			t.Fatalf("decodeMAAArgs(%q) = %#v, want nil", in, args)
		}
	}
}

func TestDecodeMAAArgs_TopLevelScalars(t *testing.T) {
	args, err := decodeMAAArgs(`["0xabc", 42, true, null]`)
	if err != nil {
		t.Fatalf("decodeMAAArgs error: %v", err)
	}
	if len(args) != 4 {
		t.Fatalf("got %d args, want 4", len(args))
	}
	if s, ok := args[0].(string); !ok || s != "0xabc" {
		t.Fatalf("args[0] = %#v, want string \"0xabc\"", args[0])
	}
	if i, ok := args[1].(int64); !ok || i != 42 {
		t.Fatalf("args[1] = %#v, want int64 42", args[1])
	}
	if b, ok := args[2].(bool); !ok || !b {
		t.Fatalf("args[2] = %#v, want bool true", args[2])
	}
	if args[3] != nil {
		t.Fatalf("args[3] = %#v, want nil", args[3])
	}
}

// The regression this whole change is about: an integer INSIDE an array must decode to int64, not the
// float64 a shallow (top-level-only) conversion left behind — the encoder rejects json.Number/float64
// for an INT8[] parameter like insert_records' $event_time.
func TestDecodeMAAArgs_NestedIntsBecomeInt64(t *testing.T) {
	args, err := decodeMAAArgs(`[["0xabc"], ["st"], [100, 200]]`)
	if err != nil {
		t.Fatalf("decodeMAAArgs error: %v", err)
	}
	times, ok := args[2].([]any)
	if !ok {
		t.Fatalf("args[2] = %#v, want []any", args[2])
	}
	for i, v := range times {
		if _, ok := v.(int64); !ok {
			t.Fatalf("times[%d] = %#v (%T), want int64", i, v, v)
		}
	}
	if times[0].(int64) != 100 || times[1].(int64) != 200 {
		t.Fatalf("times = %#v, want [100 200]", times)
	}
}

func TestDecodeMAAArgs_ScalarNumericMarker(t *testing.T) {
	args, err := decodeMAAArgs(`["eth_truf", {"__tn_type__":"numeric","value":"110000000000000000000","precision":78,"scale":0}]`)
	if err != nil {
		t.Fatalf("decodeMAAArgs error: %v", err)
	}
	dec, ok := args[1].(*kwilTypes.Decimal)
	if !ok {
		t.Fatalf("args[1] = %#v (%T), want *types.Decimal", args[1], args[1])
	}
	if got := dec.String(); got != "110000000000000000000" {
		t.Fatalf("decimal value = %q, want 110000000000000000000", got)
	}
	if p, s := dec.Precision(), dec.Scale(); p != 78 || s != 0 {
		t.Fatalf("decimal precision/scale = (%d,%d), want (78,0)", p, s)
	}
}

func TestDecodeMAAArgs_NumericArrayMarker(t *testing.T) {
	args, err := decodeMAAArgs(`[[{"__tn_type__":"numeric","value":"42.5","precision":36,"scale":18},{"__tn_type__":"numeric","value":"43.75","precision":36,"scale":18}]]`)
	if err != nil {
		t.Fatalf("decodeMAAArgs error: %v", err)
	}
	vals, ok := args[0].([]any)
	if !ok {
		t.Fatalf("args[0] = %#v, want []any", args[0])
	}
	if len(vals) != 2 {
		t.Fatalf("got %d values, want 2", len(vals))
	}
	for i, want := range []string{"42.500000000000000000", "43.750000000000000000"} {
		dec, ok := vals[i].(*kwilTypes.Decimal)
		if !ok {
			t.Fatalf("vals[%d] = %#v (%T), want *types.Decimal", i, vals[i], vals[i])
		}
		if p, s := dec.Precision(), dec.Scale(); p != 36 || s != 18 {
			t.Fatalf("vals[%d] precision/scale = (%d,%d), want (36,18)", i, p, s)
		}
		if got := dec.String(); got != want {
			t.Fatalf("vals[%d] = %q, want %q", i, got, want)
		}
	}
}

func TestDecodeMAAArgs_RejectsBadMarkers(t *testing.T) {
	cases := []string{
		`[{"foo":"bar"}]`,                                               // object without the type marker
		`[{"__tn_type__":"date","value":"x"}]`,                          // unsupported typed argument
		`[{"__tn_type__":"numeric","value":1,"precision":78,"scale":0}]`, // value must be a string
		`[{"__tn_type__":"numeric","value":"1","scale":0}]`,             // missing precision
		`[{"__tn_type__":"numeric","value":"x","precision":78,"scale":0}]`, // unparseable decimal
	}
	for _, in := range cases {
		if _, err := decodeMAAArgs(in); err == nil {
			t.Fatalf("decodeMAAArgs(%q) = nil error, want an error", in)
		}
	}
}
