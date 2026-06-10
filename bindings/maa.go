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
	"github.com/trufnetwork/sdk-go/core/tnclient"
)

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
