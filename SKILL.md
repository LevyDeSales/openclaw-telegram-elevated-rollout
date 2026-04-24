---
name: openclaw-telegram-elevated-rollout
description: Configure and validate the proven Telegram elevated rollout for the local rescue gateway, and inspect, plan, and apply a constrained Telegram elevated rollout on the local principal gateway from the rescue workspace. Use when enabling `tools.elevated` for Telegram on rescue, auditing current elevated gates, or doing a principal rollout with explicit allow/block decisions for a specific target agent or minimal agent set.
---

Use this skill with two explicit targets only:
- `rescue-local`
- `principal-local`

Treat them as different maturity levels.

## Supported matrix in v1

Read first when scope is unclear:
- `references/supported-matrix.md`

In v1:
- `rescue-local` = **configure + validate**
- `principal-local` = **inspect + preflight + plan**

In v2:
- `principal-local` = **apply + restart + post-validate** after explicit allow/block proof

Do **not** use this skill as if apply on `principal-local` were implicit or broad:
- SSH / other hosts
- channels other than Telegram
- `/bash`
- auto-approval
- broad support for arbitrary senders or agent sets

## Preserve the validation boundary

Read when the user treats shell/config success as if it already proved chat/runtime behavior:
- `references/validation-boundaries.md`

The bundled scripts can prove:
- gateway target and config path
- health / gateway probe ok (`gateway status --require-rpc`; current OpenClaw prints `Read probe: ok`)
- current elevated gates and allowlists
- rollout delta for the principal

They cannot prove by themselves:
- the real Telegram session is attached to the intended gateway
- `/elevated on` or `/elevated full` was used in the live session
- runtime approval/policy state in chat

## Choose the target path first

### Rescue local
Use this when the task is to reproduce the already-validated rescue setup.

Fast path:
1. Run `./skills/openclaw-telegram-elevated-rollout/scripts/rescue-elevated-preflight.sh`
2. Inspect current state with `python3 ./skills/openclaw-telegram-elevated-rollout/scripts/inspect_telegram_elevated.py --target rescue-local`
3. Apply the validated rescue shape with `python3 ./skills/openclaw-telegram-elevated-rollout/scripts/apply_rescue_elevated_config.py`
4. Restart rescue with `./skills/openclaw-telegram-elevated-rollout/scripts/rescue-openclaw.sh gateway restart`
5. Validate after restart with `./skills/openclaw-telegram-elevated-rollout/scripts/validate_rescue_post_restart.sh`
6. Ask for the real Telegram-side validation (`/elevated on` + minimal host exec) before declaring end-to-end success

### Principal local
Use this when the task is to audit or plan a constrained principal rollout from the rescue workspace.

Fast path:
1. Run `./skills/openclaw-telegram-elevated-rollout/scripts/principal-elevated-preflight.sh`
2. Inspect current state with `python3 ./skills/openclaw-telegram-elevated-rollout/scripts/inspect_telegram_elevated.py --target principal-local`
3. Run the planner with explicit decisions for **every** principal agent
4. Treat the output as read-only plan, not as live rollout completion

Example minimal plan shape:
- `--allow-agent main`
- every other agent declared with `--block-agent <id>`

If the request is explicitly for another single principal agent, use that agent as the sole allow target instead of `main`.

If any agent lacks an explicit decision, the planner must fail and you should keep it that way.

### Principal apply
Use this only after the explicit principal proof path has been satisfied.

Fast path:
1. Run `python3 ./skills/openclaw-telegram-elevated-rollout/scripts/apply_principal_elevated_config.py --allow-agent <target> --block-agent <others...>`
2. Restart the principal with `./skills/openclaw-telegram-elevated-rollout/scripts/principal-openclaw.sh gateway restart`
3. Validate with `./skills/openclaw-telegram-elevated-rollout/scripts/principal-elevated-preflight.sh`
4. Inspect again with `python3 ./skills/openclaw-telegram-elevated-rollout/scripts/inspect_telegram_elevated.py --target principal-local`
5. Keep the Telegram-side runtime proof separate from config proof

## Core behavior rules

- Prefer the bundled wrappers over handwritten `openclaw ...` variants.
- From rescue, do **not** trust `openclaw --profile default ...` to reach the principal.
- Keep rescue scope narrow: sender `TELEGRAM_SENDER_ID`, `watchdog` allowed, `updater` blocked.
- Keep principal scope honest: explicit allow target, explicit blocks for the rest, and no broad sender/agent expansion.
- Fail closed on target ambiguity.
- Do not imply that principal apply is broad or implicit.

## Troubleshooting

Read when the flow deviates:
- `references/troubleshooting.md`
