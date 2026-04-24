#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, Iterable, List, Set


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


def ensure_list(parent: Dict[str, Any], key: str) -> List[Any]:
    value = parent.get(key)
    if value is None:
        value = []
        parent[key] = value
    if not isinstance(value, list):
        fail(f"expected list at key '{key}'")
    return value


def allowlist_contains(entries: Iterable[Any], sender: str) -> bool:
    sender_str = str(sender)
    for entry in entries:
        entry_str = str(entry)
        if entry_str == sender_str or entry_str == f"id:{sender_str}":
            return True
    return False


def add_sender(entries: List[Any], sender: str) -> bool:
    if allowlist_contains(entries, sender):
        return False
    try:
        entries.append(int(sender))
    except ValueError:
        entries.append(sender)
    return True


def run_wrapper(*args: str) -> str:
    proc = subprocess.run([WRAPPER, *args], capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        fail(f"wrapper command failed: {' '.join(args)}")
    return proc.stdout


def normalize_target_paths() -> str:
    state_dir = os.path.abspath(os.environ.get("OPENCLAW_PRINCIPAL_STATE_DIR", EXPECTED_STATE_DIR))
    if state_dir != EXPECTED_STATE_DIR:
        fail(f"principal state dir does not match expected principal target: {state_dir}")
    if ".openclaw-rescue" in state_dir:
        fail(f"principal state dir still points to rescue: {state_dir}")
    return os.path.join(state_dir, "openclaw.json")


def get_agent(config: Dict[str, Any], agent_id: str) -> Dict[str, Any]:
    agents_root = config.setdefault("agents", {})
    if not isinstance(agents_root, dict):
        fail("config.agents is not an object")
    agents_list = agents_root.setdefault("list", [])
    if not isinstance(agents_list, list):
        fail("config.agents.list is not a list")
    for agent in agents_list:
        if isinstance(agent, dict) and agent.get("id") == agent_id:
            return agent
    fail(f"principal agent not found: {agent_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply a controlled principal Telegram elevated config with explicit allow/block decisions.")
    parser.add_argument("--sender", help="Telegram sender id to allow globally and for allowed agents. Defaults to TELEGRAM_SENDER_ID when set.")
    parser.add_argument("--allow-agent", action="append", default=[], help="Agent id to explicitly allow. Repeat as needed.")
    parser.add_argument("--block-agent", action="append", default=[], help="Agent id to explicitly block. Repeat as needed.")
    parser.add_argument("--dry-run", action="store_true", help="Show the planned delta without writing the config")
    args = parser.parse_args()
    sender = resolve_sender(args.sender)

    if not os.path.exists(WRAPPER) or not os.access(WRAPPER, os.X_OK):
        fail(f"wrapper not executable: {WRAPPER}")

    config_path = normalize_target_paths()
    if not os.path.isfile(config_path):
        fail(f"principal config missing: {config_path}")

    status_output = run_wrapper("gateway", "status", "--require-rpc")
    if "Config (cli): ~/.openclaw/openclaw.json" not in status_output:
        fail("gateway status did not prove principal cli config before apply")
    if "Config (service): ~/.openclaw/openclaw.json" not in status_output:
        fail("gateway status did not prove principal service config before apply")
    if not re.search(r"^(?:RPC|Read|Connectivity) probe:\s*ok$", status_output, re.M):
        fail("principal probe is not ok before apply")

    config = load_json(config_path)

    agents_root = config.get("agents") or {}
    if not isinstance(agents_root, dict):
        fail("principal config.agents is not an object")
    agents = agents_root.get("list") or []
    if not isinstance(agents, list):
        fail("principal config.agents.list is not a list")
    agent_ids: List[str] = []
    for agent in agents:
        if isinstance(agent, dict) and agent.get("id"):
            agent_ids.append(str(agent["id"]))
    if not agent_ids:
        fail("principal config has no agent ids to apply against")

    allow_agents: Set[str] = set(args.allow_agent)
    block_agents: Set[str] = set(args.block_agent)
    overlap = sorted(allow_agents & block_agents)
    if overlap:
        fail(f"agent(s) declared as both allow and block: {', '.join(overlap)}")

    unknown = sorted((allow_agents | block_agents) - set(agent_ids))
    if unknown:
        fail(f"unknown agent id(s) in requested apply: {', '.join(unknown)}")

    undecided = sorted(set(agent_ids) - allow_agents - block_agents)
    if undecided:
        fail(
            "principal apply requires explicit decision for every agent; missing decision for: "
            + ", ".join(undecided)
        )

    if not allow_agents:
        fail("principal apply requires at least one explicitly allowed agent")

    changes: List[str] = []

    tools = config.setdefault("tools", {})
    if not isinstance(tools, dict):
        fail("config.tools is not an object")
    elevated = tools.setdefault("elevated", {})
    if not isinstance(elevated, dict):
        fail("config.tools.elevated is not an object")
    if elevated.get("enabled") is not True:
        elevated["enabled"] = True
        changes.append("set tools.elevated.enabled=true")
    elevated_allow_from = elevated.setdefault("allowFrom", {})
    if not isinstance(elevated_allow_from, dict):
        fail("config.tools.elevated.allowFrom is not an object")
    global_telegram = ensure_list(elevated_allow_from, "telegram")
    if add_sender(global_telegram, sender):
        changes.append(f"add sender {sender} to tools.elevated.allowFrom.telegram")

    for agent_id in sorted(allow_agents):
        agent = get_agent(config, agent_id)
        agent_tools = agent.setdefault("tools", {})
        if not isinstance(agent_tools, dict):
            fail(f"{agent_id}.tools is not an object")
        agent_elevated = agent_tools.setdefault("elevated", {})
        if not isinstance(agent_elevated, dict):
            fail(f"{agent_id}.tools.elevated is not an object")
        if agent_elevated.get("enabled") is not True:
            agent_elevated["enabled"] = True
            changes.append(f"set {agent_id}.tools.elevated.enabled=true")
        agent_allow_from = agent_elevated.setdefault("allowFrom", {})
        if not isinstance(agent_allow_from, dict):
            fail(f"{agent_id}.tools.elevated.allowFrom is not an object")
        agent_telegram = ensure_list(agent_allow_from, "telegram")
        if add_sender(agent_telegram, sender):
            changes.append(f"add sender {sender} to {agent_id}.tools.elevated.allowFrom.telegram")

    for agent_id in sorted(block_agents):
        agent = get_agent(config, agent_id)
        agent_tools = agent.setdefault("tools", {})
        if not isinstance(agent_tools, dict):
            fail(f"{agent_id}.tools is not an object")
        agent_elevated = agent_tools.setdefault("elevated", {})
        if not isinstance(agent_elevated, dict):
            fail(f"{agent_id}.tools.elevated is not an object")
        if agent_elevated.get("enabled") is not False:
            agent_elevated["enabled"] = False
            changes.append(f"set {agent_id}.tools.elevated.enabled=false")

    if args.dry_run:
        print("Apply principal elevated config (dry-run)")
        print(f"Config    : {config_path}")
        print(f"Sender    : {sender}")
        print(f"Allow     : {', '.join(sorted(allow_agents))}")
        print(f"Block     : {', '.join(sorted(block_agents))}")
        if changes:
            print("Changes:")
            for change in changes:
                print(f"- {change}")
        else:
            print("Changes:\n- none (config already matches requested principal shape)")
        return

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = f"{config_path}.bak-{timestamp}-telegram-elevated-principal-apply"
    shutil.copy2(config_path, backup_path)

    if changes:
        with open(config_path, "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    print("Apply principal elevated config")
    print(f"Config    : {config_path}")
    print(f"Backup    : {backup_path}")
    print(f"Sender    : {sender}")
    print(f"Allow     : {', '.join(sorted(allow_agents))}")
    print(f"Block     : {', '.join(sorted(block_agents))}")
    if changes:
        print("Changes:")
        for change in changes:
            print(f"- {change}")
    else:
        print("Changes:\n- none (config already matches requested principal shape)")


if __name__ == "__main__":
    main()
