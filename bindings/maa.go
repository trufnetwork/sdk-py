package exports

// Modular Agent Address (MAA / "agent wallet") action bindings — migration 048.
//
// Off-chain address derivation lives in Python (trufnetwork_sdk_py.utils, a byte-exact keccak mirror of
// the node precompiles), so these bindings only submit the on-chain rule actions and expose the public
// read surface. Reads return the CallProcedure {column_names, values} shape JSON-encoded so Python can
// parse rows without any gopy interface{} conversion; writes return the transaction hash.

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"strings"

	"github.com/pkg/errors"
	kwilTypes "github.com/trufnetwork/kwil-db/core/types"
	"github.com/trufnetwork/sdk-go/core/tnclient"
	"github.com/trufnetwork/sdk-go/core/types"
)

// maaTypeKey marks a JSON object as a typed argument (rather than a plain scalar) inside the maa_exec
// argument array. The only typed argument today is "numeric": a NUMERIC value carried as a string plus
// its precision/scale, because JSON has no decimal type and the on-chain route does not coerce text to
// NUMERIC — so a NUMERIC action parameter (e.g. maa_withdraw's $amount or insert_records' $value) can
// only be driven by reconstructing a *types.Decimal with the EXACT precision/scale the parameter
// declares. The Python side emits this shape; see trufnetwork_sdk_py.client.MAANumericArg.
const maaTypeKey = "__tn_type__"

// MAACreateRule submits maa_create_rule (the caller becomes the restricted agent) and returns the tx
// hash. bodyHashesHex is parallel to namespaces/actions; an empty element is an unpinned (NULL) entry.
func MAACreateRule(
	client *tnclient.Client,
	salt []byte,
	feeMode string,
	feeBps int,
	feeFlat string,
	namespaces []string,
	actions []string,
	bodyHashesHex []string,
) (string, error) {
	ctx := context.Background()
	act, err := client.LoadActions()
	if err != nil {
		return "", errors.Wrap(err, "load actions")
	}

	bodyHashes := make([][]byte, len(bodyHashesHex))
	for i, h := range bodyHashesHex {
		if h == "" {
			bodyHashes[i] = nil // unpinned -> NULL
			continue
		}
		h = strings.TrimPrefix(strings.TrimPrefix(h, "0x"), "0X")
		decoded, derr := hex.DecodeString(h)
		if derr != nil {
			return "", errors.Wrapf(derr, "body_hash[%d]", i)
		}
		bodyHashes[i] = decoded
	}

	txHash, err := act.ExecuteProcedure(ctx, "maa_create_rule", [][]any{
		{salt, feeMode, feeBps, feeFlat, namespaces, actions, bodyHashes},
	})
	if err != nil {
		return "", errors.Wrap(err, "maa_create_rule")
	}
	return txHash.String(), nil
}

// MAAJoin submits maa_join (the caller becomes the unrestricted owner/funder) and returns the tx hash.
func MAAJoin(client *tnclient.Client, ruleID []byte) (string, error) {
	ctx := context.Background()
	act, err := client.LoadActions()
	if err != nil {
		return "", errors.Wrap(err, "load actions")
	}
	txHash, err := act.ExecuteProcedure(ctx, "maa_join", [][]any{{ruleID}})
	if err != nil {
		return "", errors.Wrap(err, "maa_join")
	}
	return txHash.String(), nil
}

// MAAExec submits a maa_exec transaction: run one allow-listed inner action AS the agent wallet. The
// caller (signer) acts as its component key — restricted agent or unrestricted owner — and the node
// rewrites @caller to the wallet after checking the rule's role and allow-list. The owner-exit actions
// (maa_withdraw / maa_bridge_out) are reachable here for the unrestricted owner. namespace "" defaults
// to "main". argsJSON is a JSON array of the inner action's arguments (a single call), e.g.
// `["0xabc...", 100, "5.5"]`; it is decoded with the same number handling the action-args encoder uses
// so integers reach the node as integers (not floats) at any nesting depth, and a NUMERIC argument
// encoded as a {"__tn_type__":"numeric",...} marker reaches the node as a precision/scale-exact
// *types.Decimal. Returns the tx hash.
func MAAExec(client *tnclient.Client, maaAddress []byte, namespace string, action string, argsJSON string) (string, error) {
	args, err := decodeMAAArgs(argsJSON)
	if err != nil {
		return "", err
	}
	ctx := context.Background()
	act, err := client.LoadActions()
	if err != nil {
		return "", errors.Wrap(err, "load actions")
	}
	txHash, err := act.ExecuteAgentAction(ctx, types.MAAExecuteInput{
		MAAAddress: maaAddress,
		Namespace:  namespace,
		Action:     action,
		Args:       args,
	})
	if err != nil {
		return "", errors.Wrap(err, "maa_exec")
	}
	return txHash, nil
}

// decodeMAAArgs parses a JSON array of inner-action arguments. It mirrors EncodeActionArgs's number
// handling (UseNumber, then int64-or-float64) so a JSON integer reaches the action as an int64 rather
// than a float64 — recursively, so an element of an INT[] array is an int64 too, not the float64 a
// shallow conversion would leave (which the action-args encoder rejects). A JSON object is interpreted
// as a typed-argument marker (see maaTypeKey); the only kind today is "numeric", which becomes a
// precision/scale-exact *types.Decimal. An empty string or "[]" yields no arguments.
func decodeMAAArgs(argsJSON string) ([]any, error) {
	if argsJSON == "" || argsJSON == "[]" {
		return nil, nil
	}
	decoder := json.NewDecoder(strings.NewReader(argsJSON))
	decoder.UseNumber()
	var raw []any
	if err := decoder.Decode(&raw); err != nil {
		return nil, errors.Wrap(err, "decode maa_exec arguments JSON")
	}
	args := make([]any, len(raw))
	for i, arg := range raw {
		conv, err := convertMAAArg(arg)
		if err != nil {
			return nil, err
		}
		args[i] = conv
	}
	return args, nil
}

// convertMAAArg normalizes one decoded JSON value into the Go type the action-args encoder expects,
// recursing into arrays so the conversion is applied at every depth (not just the top level). JSON
// numbers become int64 (or float64 when they do not fit); typed-argument objects become their native
// value (currently only NUMERIC -> *types.Decimal); everything else passes through unchanged.
func convertMAAArg(v any) (any, error) {
	switch t := v.(type) {
	case json.Number:
		if intVal, err := t.Int64(); err == nil {
			return intVal, nil
		}
		if floatVal, err := t.Float64(); err == nil {
			return floatVal, nil
		}
		return nil, errors.Errorf("cannot represent JSON number %q as int64 or float64", t.String())
	case []any:
		for i := range t {
			conv, err := convertMAAArg(t[i])
			if err != nil {
				return nil, err
			}
			t[i] = conv
		}
		return t, nil
	case map[string]any:
		return decodeMAATypedArg(t)
	default:
		return v, nil
	}
}

// decodeMAATypedArg turns a typed-argument marker object into its native Go value. A bare JSON object
// is never a valid inner-action argument on its own, so anything that is not a recognized marker is an
// error rather than a silent pass-through.
func decodeMAATypedArg(m map[string]any) (any, error) {
	kind, _ := m[maaTypeKey].(string)
	switch kind {
	case "numeric":
		return decodeMAANumeric(m)
	case "":
		return nil, errors.Errorf("unexpected object in maa_exec arguments (missing %q marker)", maaTypeKey)
	default:
		return nil, errors.Errorf("unsupported maa_exec typed argument %q", kind)
	}
}

// decodeMAANumeric reconstructs a NUMERIC argument from its marker: ParseDecimalExplicit with the
// declared precision/scale yields a *types.Decimal whose type matches the action parameter exactly,
// which the engine requires (it compares precision and scale, and does not cast text to NUMERIC).
func decodeMAANumeric(m map[string]any) (*kwilTypes.Decimal, error) {
	value, ok := m["value"].(string)
	if !ok {
		return nil, errors.New("numeric maa_exec argument requires a string \"value\"")
	}
	precision, err := maaUint16Field(m, "precision")
	if err != nil {
		return nil, err
	}
	scale, err := maaUint16Field(m, "scale")
	if err != nil {
		return nil, err
	}
	dec, err := kwilTypes.ParseDecimalExplicit(value, precision, scale)
	if err != nil {
		return nil, errors.Wrapf(err, "parse numeric maa_exec argument %q as NUMERIC(%d,%d)", value, precision, scale)
	}
	return dec, nil
}

// maaUint16Field reads a non-negative integer JSON field (decoded as json.Number under UseNumber) and
// range-checks it to uint16, the type ParseDecimalExplicit expects for precision/scale.
func maaUint16Field(m map[string]any, key string) (uint16, error) {
	num, ok := m[key].(json.Number)
	if !ok {
		return 0, errors.Errorf("numeric maa_exec argument requires integer %q", key)
	}
	n, err := num.Int64()
	if err != nil {
		return 0, errors.Wrapf(err, "numeric maa_exec argument %q", key)
	}
	if n < 0 || n > 65535 {
		return 0, errors.Errorf("numeric maa_exec argument %q out of uint16 range: %d", key, n)
	}
	return uint16(n), nil
}

// maaCallJSON runs a read (VIEW) action and returns its {column_names, values} result JSON-encoded.
func maaCallJSON(client *tnclient.Client, procedure string, args []any) (string, error) {
	res, err := CallProcedure(client, procedure, args)
	if err != nil {
		return "", err
	}
	jsonBytes, err := json.Marshal(res)
	if err != nil {
		return "", errors.Wrap(err, "marshal result to json")
	}
	return string(jsonBytes), nil
}

// MAAGetRule reads a rule's terms (maa_get_rule).
func MAAGetRule(client *tnclient.Client, ruleID []byte) (string, error) {
	return maaCallJSON(client, "maa_get_rule", []any{ruleID})
}

// MAAGetAllowedActions reads a rule's allow-list (maa_get_allowed_actions).
func MAAGetAllowedActions(client *tnclient.Client, ruleID []byte) (string, error) {
	return maaCallJSON(client, "maa_get_allowed_actions", []any{ruleID})
}

// MAAGetInstance reads an agent wallet and its two component keys (maa_get_instance).
func MAAGetInstance(client *tnclient.Client, maaAddress []byte) (string, error) {
	return maaCallJSON(client, "maa_get_instance", []any{maaAddress})
}

// MAAGetBalance reads an agent wallet's escrow balance on a bridge (maa_get_balance). maaAddress is
// passed as raw bytes (the action's parameter is BYTEA), so the read goes through the same typed-arg
// path as the other getters rather than the string-coercing call_procedure helper.
func MAAGetBalance(client *tnclient.Client, maaAddress []byte, bridge string) (string, error) {
	return maaCallJSON(client, "maa_get_balance", []any{maaAddress, bridge})
}

// MAAListByRestricted lists the rules an agent created (maa_list_by_restricted). agent is a 0x-hex address.
func MAAListByRestricted(client *tnclient.Client, agent string, limit int, offset int) (string, error) {
	return maaCallJSON(client, "maa_list_by_restricted", []any{agent, limit, offset})
}

// MAAListByUnrestricted lists the wallets an owner funded (maa_list_by_unrestricted). owner is a 0x-hex address.
func MAAListByUnrestricted(client *tnclient.Client, owner string, limit int, offset int) (string, error) {
	return maaCallJSON(client, "maa_list_by_unrestricted", []any{owner, limit, offset})
}

// MAAListInstancesByRule lists every wallet funded under a rule (maa_list_instances_by_rule).
func MAAListInstancesByRule(client *tnclient.Client, ruleID []byte, limit int, offset int) (string, error) {
	return maaCallJSON(client, "maa_list_instances_by_rule", []any{ruleID, limit, offset})
}

// MAAGetEvents reads a rule's append-only audit log (maa_get_events).
func MAAGetEvents(client *tnclient.Client, ruleID []byte, limit int, offset int) (string, error) {
	return maaCallJSON(client, "maa_get_events", []any{ruleID, limit, offset})
}

// MAAIsKnown reports whether an address is a known (joined) agent wallet (maa_is_known).
func MAAIsKnown(client *tnclient.Client, maaAddress []byte) (string, error) {
	return maaCallJSON(client, "maa_is_known", []any{maaAddress})
}
