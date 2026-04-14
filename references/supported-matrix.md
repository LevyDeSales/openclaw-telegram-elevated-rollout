# Supported matrix

## v1

| Target | Status | Supported capability |
|---|---|---|
| `rescue-local` | supported | inspect, preflight, apply, restart, post-validate |
| `principal-local` | supported with restrictions | inspect, preflight, plan, apply, restart, post-validate for an explicit single-agent target or constrained allow/block set |

## Not supported

- SSH / other hosts
- channels other than Telegram
- arbitrary broad sender/agent combinations
- `/bash`
- auto-approval
- treating `/elevated full` as normal path

## Canonical rollout shape

### Rescue local
- global Telegram allowlist contains `TELEGRAM_SENDER_ID`
- `watchdog` explicitly enabled
- `updater` explicitly disabled

### Principal local
- rollout starts with one explicitly allowed agent and every other agent must receive an explicit `block` decision in the plan
- `main` is the default minimal start, but a different single target agent may be used when explicitly requested
- principal apply requires explicit allow/block proof, backup, restart, and post-validate before any runtime claims
