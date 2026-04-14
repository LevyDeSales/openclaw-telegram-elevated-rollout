# Troubleshooting

## 1. Rescue helper points to principal

**Symptom**
- rescue preflight fails with principal path/state

**Fix**
- use the bundled rescue wrapper and rescue helpers
- clear accidental overrides like `OPENCLAW_RESCUE_STATE_DIR="$HOME/.openclaw"`

## 2. Principal helper points to rescue

**Symptom**
- principal preflight or planner fails because the state dir still looks like rescue

**Fix**
- use the bundled principal wrapper
- clear accidental overrides like `OPENCLAW_PRINCIPAL_STATE_DIR="$HOME/.openclaw-rescue"`
- do not trust `openclaw --profile default ...` in this workspace

## 3. Principal planner refuses to continue

**Symptom**
- planner says some agents still have no decision

**Fix**
- keep that failure
- add explicit `--allow-agent` / `--block-agent` decisions for every principal agent
- do not weaken this guardrail just to make the planner pass

## 4. Rescue apply reports no changes

**Symptom**
- apply succeeds but prints `none (config already matches validated rescue shape)`

**Meaning**
- this is fine
- it means the rescue config already matches the validated target shape

## 5. Post-restart validation passes but Telegram still does not work

**Meaning**
- shell/config validation and runtime/chat validation diverged

**Fix**
- validate the real Telegram session next
- check whether the intended agent and sender are actually the ones receiving the chat
- confirm whether `/elevated on` or `/elevated full` was used and whether approvals still apply
