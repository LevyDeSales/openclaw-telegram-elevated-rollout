#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Optional, Set


HOME_DIR = os.path.expanduser("~")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WRAPPER = os.path.join(SCRIPT_DIR, "principal-openclaw.sh")
EXPECTED_STATE_DIR = os.path.join(HOME_DIR, ".openclaw")
EXPECTED_CONFIG_PATH = os.path.join(EXPECTED_STATE_DIR, "openclaw.json")
def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    raise SystemExit(1)


def resolve_sender(cli_value: str | None) -> str:
    sender = cli_value or os.environ.get("TELEGRAM_SENDER_ID")
    if not sender:
        fail("telegram sender id is required; pass --sender or set TELEGRAM_SENDER_ID")
    return str(sender)


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        fail(f"config is not a JSON object: {path}")
    return data


def allowlist_contains(entries: Iterable[Any], sender: str) -> bool:
    sender_str = str(sender)
    for entry in entries:
        entry_str = str(entry)
        if entry_str == sender_str or entry_str == f"id:{sender_str}":
            return True
    return False


def summarize_allowlist(entries: Iterable[Any]) -> str:
    values = [str(entry) for entry in entries]
    return ", ".join(values) if values else "none"


def run_wrapper(*args: str) -> str:
    proc = subprocess.run([WRAPPER, *args], capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        fail(f"wrapper command failed: {' '.join(args)}")
    return proc.stdout


def current_agent_state(agent: Dict[str, Any], sender: str, global_enabled: bool, global_sender_allowed: bool) -> Dict[str, str]:
    tools = agent.get("tools") or {}
    if not isinstance(tools, dict):
        tools = {}
    elevated = tools.get("elevated")
    override_enabled = "inherit"
    override_allow: List[Any] = []
    override_sender_allowed = "inherit"
    effective_enabled = global_enabled
    effective_sender_allowed = global_sender_allowed

    if isinstance(elevated, dict):
        if "enabled" in elevated:
            effective_enabled = global_enabled and (elevated.get("enabled") is True)
            override_enabled = str(elevated.get("enabled") is True).lower()
        allow_from = elevated.get("allowFrom") or {}
        if isinstance(allow_from, dict) and "telegram" in allow_from:
            override_allow = allow_from.get("telegram") or []
            allowed = allowlist_contains(override_allow, sender)
            override_sender_allowed = str(allowed).lower()
            effective_sender_allowed = global_sender_allowed and allowed

    return {
        "override_enabled": override_enabled,
        "override_allowlist": summarize_allowlist(override_allow) if override_allow else "inherit",
        "override_sender_allowed": override_sender_allowed,
        "effective_enabled": str(effective_enabled).lower(),
        "effective_sender_allowed": str(effective_sender_allowed).lower(),
        "effective_available_sender": str(effective_enabled and effective_sender_allowed).lower(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only planner for principal Telegram elevated rollout. Requires explicit agent decisions.")
    parser.add_argument("--sender", help="Telegram sender id to plan for. Defaults to TELEGRAM_SENDER_ID when set.")
    parser.add_argument("--allow-agent", action="append", default=[], help="Agent id to explicitly allow in the rollout plan. Repeat as needed.")
    parser.add_argument("--block-agent", action="append", default=[], help="Agent id to explicitly block in the rollout plan. Repeat as needed.")
    args = parser.parse_args()
    sender = resolve_sender(args.sender)

    if not os.path.exists(WRAPPER) or not os.access(WRAPPER, os.X_OK):
        fail(f"wrapper not executable: {WRAPPER}")

    state_dir = os.path.abspath(os.environ.get("OPENCLAW_PRINCIPAL_STATE_DIR", EXPECTED_STATE_DIR))
    if state_dir != EXPECTED_STATE_DIR:
        fail(f"principal state dir does not match expected principal target: {state_dir}")
    if ".openclaw-rescue" in state_dir:
        fail(f"principal state dir still points to rescue: {state_dir}")
    if not os.path.isfile(EXPECTED_CONFIG_PATH):
        fail(f"principal config missing: {EXPECTED_CONFIG_PATH}")

    status_output = run_wrapper("gateway", "status")
    if "Config (cli): ~/.openclaw/openclaw.json" not in status_output:
        fail("gateway status did not prove principal cli config")
    if "Config (service): ~/.openclaw/openclaw.json" not in status_output:
        fail("gateway status did not prove principal service config")
    if "RPC probe: ok" not in status_output:
        fail("principal RPC probe is not ok")
    if ".openclaw-rescue" in status_output:
        fail("principal planner still references rescue")

    config = load_json(EXPECTED_CONFIG_PATH)
    tools = config.get("tools") or {}
    if not isinstance(tools, dict):
        tools = {}
    global_elevated = tools.get("elevated") or {}
    if not isinstance(global_elevated, dict):
        global_elevated = {}

    global_enabled = global_elevated.get("enabled") is True
    global_allow_from = global_elevated.get("allowFrom") or {}
    if not isinstance(global_allow_from, dict):
        global_allow_from = {}
    global_telegram = global_allow_from.get("telegram") or []
    global_sender_allowed = allowlist_contains(global_telegram, sender)

    agents_root = config.get("agents") or {}
    if not isinstance(agents_root, dict):
        fail("principal config.agents is not an object")
    agents = agents_root.get("list") or []
    if not isinstance(agents, list):
        fail("principal config.agents.list is not a list")

    agent_map: Dict[str, Dict[str, Any]] = {}
    for agent in agents:
        if isinstance(agent, dict) and agent.get("id"):
            agent_map[str(agent["id"])] = agent

    if not agent_map:
        fail("principal config has no agent ids to plan against")

    allow_agents: Set[str] = set(args.allow_agent)
    block_agents: Set[str] = set(args.block_agent)
    overlap = sorted(allow_agents & block_agents)
    if overlap:
        fail(f"agent(s) declared as both allow and block: {', '.join(overlap)}")

    unknown = sorted((allow_agents | block_agents) - set(agent_map.keys()))
    if unknown:
        fail(f"unknown agent id(s) in requested rollout: {', '.join(unknown)}")

    undecided = sorted(set(agent_map.keys()) - allow_agents - block_agents)
    if undecided:
        fail(
            "principal rollout plan requires explicit decision for every agent; missing decision for: "
            + ", ".join(undecided)
        )

    if not allow_agents:
        fail("principal rollout plan requires at least one explicitly allowed agent")

    out: List[str] = []
    out.append("Principal Telegram elevated rollout plan (read-only)")
    out.append(f"Requested sender    : telegram:{sender}")
    out.append(f"Wrapper             : {WRAPPER}")
    out.append(f"Expected state dir  : {EXPECTED_STATE_DIR}")
    out.append(f"Expected config     : {EXPECTED_CONFIG_PATH}")
    out.append("")
    out.append("Current global elevated state")
    out.append(f"- enabled           : {str(global_enabled).lower()}")
    out.append(f"- telegram allowlist: {summarize_allowlist(global_telegram)}")
    out.append(f"- sender allowed    : {str(global_sender_allowed).lower()}")
    out.append("")
    out.append("Requested rollout decisions")
    out.append(f"- allow agents      : {', '.join(sorted(allow_agents))}")
    out.append(f"- block agents      : {', '.join(sorted(block_agents))}")
    out.append("")
    out.append(f"Agents ({len(agent_map)})")
    for agent_id in sorted(agent_map.keys()):
        state = current_agent_state(agent_map[agent_id], sender, global_enabled, global_sender_allowed)
        decision = "allow" if agent_id in allow_agents else "block"
        out.append(f"- {agent_id}")
        out.append(f"  - decision                  : {decision}")
        out.append(f"  - current.override.enabled  : {state['override_enabled']}")
        out.append(f"  - current.override.telegram : {state['override_allowlist']}")
        out.append(f"  - current.availableSender   : {state['effective_available_sender']}")
    out.append("")
    out.append("Planned delta")
    if global_enabled:
        out.append("- keep tools.elevated.enabled=true")
    else:
        out.append("- set tools.elevated.enabled=true")
    if global_sender_allowed:
        out.append(f"- keep sender {sender} in tools.elevated.allowFrom.telegram")
    else:
        out.append(f"- add sender {sender} to tools.elevated.allowFrom.telegram")
    for agent_id in sorted(allow_agents):
        state = current_agent_state(agent_map[agent_id], sender, global_enabled, global_sender_allowed)
        if state["override_enabled"] != "true":
            out.append(f"- set {agent_id}.tools.elevated.enabled=true")
        else:
            out.append(f"- keep {agent_id}.tools.elevated.enabled=true")
        if state["override_allowlist"] == "inherit":
            out.append(f"- add explicit sender {sender} to {agent_id}.tools.elevated.allowFrom.telegram")
        elif sender in state["override_allowlist"].split(", "):
            out.append(f"- keep sender {sender} in {agent_id}.tools.elevated.allowFrom.telegram")
        else:
            out.append(f"- add sender {sender} to {agent_id}.tools.elevated.allowFrom.telegram")
    for agent_id in sorted(block_agents):
        state = current_agent_state(agent_map[agent_id], sender, global_enabled, global_sender_allowed)
        if state["override_enabled"] != "false":
            out.append(f"- set {agent_id}.tools.elevated.enabled=false")
        else:
            out.append(f"- keep {agent_id}.tools.elevated.enabled=false")
    out.append("")
    out.append("Cross-checks")
    out.append("[OK] principal gateway context proved for read-only planning")
    out.append(f"[OK] explicit decision provided for all {len(agent_map)} agent(s)")
    if allow_agents == {"main"}:
        out.append("[OK] rollout remains minimal: only `main` is explicitly allowed")
    else:
        out.append("[WARN] rollout is broader than the recommended minimal start on `main`")
    if block_agents:
        out.append(f"[OK] non-target agents are explicitly blocked: {', '.join(sorted(block_agents))}")

    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
