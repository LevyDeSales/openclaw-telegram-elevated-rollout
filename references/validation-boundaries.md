# Validation boundaries

Treat these as two different kinds of proof.

## What the scripts can prove

- target gateway context
- config path and service config path
- `RPC probe: ok`
- current `tools.elevated` state
- current Telegram allowlists
- per-agent overrides
- rollout delta for the principal

## What the scripts cannot prove alone

- that the real Telegram chat is attached to the intended gateway
- that `/elevated on` or `/elevated full` was actually used in the live session
- that runtime approval state in chat matches the operator’s assumption
- that a browser or another channel inherited the same policy behavior

## Practical rule

For rescue, shell/config success is only platform-complete after Telegram-side validation confirms the host exec path.

For principal, config/apply success is not runtime/chat success.
It only proves that the target is understood, the delta is explicit, and the config was written and restarted on the intended gateway.
