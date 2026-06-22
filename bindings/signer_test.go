package exports

import (
	"bytes"
	"testing"
)

// the canonical hex private key 0x..01 (no prefix)
const testHexKey = "0000000000000000000000000000000000000000000000000000000000000001"

func TestNormalizeHexKey(t *testing.T) {
	cases := []struct {
		name string
		in   string
		want string
	}{
		{"bare", testHexKey, testHexKey},
		{"0x prefix", "0x" + testHexKey, testHexKey},
		{"0X prefix", "0X" + testHexKey, testHexKey},
		{"surrounding whitespace", "  0x" + testHexKey + "\n", testHexKey},
		{"leading-zero hex untouched", "0a" + testHexKey[2:], "0a" + testHexKey[2:]},
		{"empty", "", ""},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := normalizeHexKey(c.in); got != c.want {
				t.Fatalf("normalizeHexKey(%q) = %q, want %q", c.in, got, c.want)
			}
		})
	}
}

// createSigner must accept the key with or without the 0x prefix and derive the SAME
// identity for every accepted form — this is the regression guard for the live-testnet
// "encoding/hex: invalid byte: U+0078 'x'" failure on 0x-prefixed keys.
func TestCreateSignerAcceptsOptional0xPrefix(t *testing.T) {
	var want []byte
	for _, in := range []string{testHexKey, "0x" + testHexKey, "0X" + testHexKey, "  0x" + testHexKey + "  "} {
		s, err := createSigner(in)
		if err != nil {
			t.Fatalf("createSigner(%q) unexpected error: %v", in, err)
		}
		id := s.CompactID()
		if len(id) == 0 {
			t.Fatalf("createSigner(%q) produced empty identity", in)
		}
		if want == nil {
			want = id
			continue
		}
		if !bytes.Equal(id, want) {
			t.Fatalf("createSigner(%q) identity %x != %x from the bare key", in, id, want)
		}
	}
}

// A malformed key must still error (the normalization must not mask bad input).
func TestCreateSignerRejectsInvalidKey(t *testing.T) {
	if _, err := createSigner("0xnot-hex"); err == nil {
		t.Fatal("createSigner(invalid) returned nil error, want a decode failure")
	}
}
