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
from typing import Any, Dict, List, Tuple


HOME_DIR = os.path.expanduser("~")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WRAPPER = os.path.join(SCRIPT_DIR, "rescue-openclaw.sh")
EXPECTED_STATE_DIR = os.path.join(HOME_DIR, ".openclaw-rescue")
EXPECTED_CONFIG_PATH = os.path.join(EXPECTED_STATE_DIR, "openclaw.json")
REQUIRED_ALLOWED_AGENT = "watchdog"
REQUIRED_BLOCKED_AGENT = "updater"


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


def allowlist_contains(entries: List[Any], sender: str) -> bool:
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
    fail(f"required rescue agent not found: {agent_id}")


def normalize_target_paths() -> Tuple[str, str]:
    state_dir = os.path.abspath(os.environ.get("OPENCLAW_RESCUE_STATE_DIR", EXPECTED_STATE_DIR))
    config_path = os.path.abspath(os.environ.get("OPENCLAW_RESCUE_CONFIG_PATH", EXPECTED_CONFIG_PATH))
    if state_dir != EXPECTED_STATE_DIR:
        fail(f"rescue state dir does not match expected rescue target: {state_dir}")
    if config_path != EXPECTED_CONFIG_PATH:
        fail(f"rescue config path does not match expected rescue target: {config_path}")
    return state_dir, config_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply the validated rescue Telegram elevated config with backup-first semantics.")
    parser.add_argument("--sender", help="Telegram sender id to ensure in allowlists. Defaults to TELEGRAM_SENDER_ID when set.")
    parser.add_argument("--dry-run", action="store_true", help="Show the planned delta without writing the config")
    args = parser.parse_args()
    sender = resolve_sender(args.sender)

    if not os.path.exists(WRAPPER) or not os.access(WRAPPER, os.X_OK):
        fail(f"wrapper not executable: {WRAPPER}")

    _, config_path = normalize_target_paths()
    if not os.path.isfile(config_path):
        fail(f"rescue config missing: {config_path}")

    status_output = run_wrapper("gateway", "status", "--require-rpc")
    if "Config (cli): ~/.openclaw-rescue/openclaw.json" not in status_output:
        fail("gateway status did not prove rescue cli config before apply")
    if "Config (service): ~/.openclaw-rescue/openclaw.json" not in status_output:
        fail("gateway status did not prove rescue service config before apply")
    if not re.search(r"^(?:RPC|Read|Connectivity) probe:\s*ok$", status_output, re.M):
        fail("rescue probe is not ok before apply")

    config = load_json(config_path)
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

    watchdog = get_agent(config, REQUIRED_ALLOWED_AGENT)
    updater = get_agent(config, REQUIRED_BLOCKED_AGENT)

    watchdog_tools = watchdog.setdefault("tools", {})
    if not isinstance(watchdog_tools, dict):
        fail("watchdog.tools is not an object")
    watchdog_elevated = watchdog_tools.setdefault("elevated", {})
    if not isinstance(watchdog_elevated, dict):
        fail("watchdog.tools.elevated is not an object")
    if watchdog_elevated.get("enabled") is not True:
        watchdog_elevated["enabled"] = True
        changes.append("set watchdog.tools.elevated.enabled=true")
    watchdog_allow_from = watchdog_elevated.setdefault("allowFrom", {})
    if not isinstance(watchdog_allow_from, dict):
        fail("watchdog.tools.elevated.allowFrom is not an object")
    watchdog_telegram = ensure_list(watchdog_allow_from, "telegram")
    if add_sender(watchdog_telegram, sender):
        changes.append(f"add sender {sender} to watchdog.tools.elevated.allowFrom.telegram")

    updater_tools = updater.setdefault("tools", {})
    if not isinstance(updater_tools, dict):
        fail("updater.tools is not an object")
    updater_elevated = updater_tools.setdefault("elevated", {})
    if not isinstance(updater_elevated, dict):
        fail("updater.tools.elevated is not an object")
    if updater_elevated.get("enabled") is not False:
        updater_elevated["enabled"] = False
        changes.append("set updater.tools.elevated.enabled=false")

    if args.dry_run:
        print("Apply rescue elevated config (dry-run)")
        print(f"Config    : {config_path}")
        print(f"Sender    : {sender}")
        if changes:
            print("Changes:")
            for change in changes:
                print(f"- {change}")
        else:
            print("Changes:\n- none (config already matches validated rescue shape)")
        return

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = f"{config_path}.bak-{timestamp}-telegram-elevated-rescue-apply"
    shutil.copy2(config_path, backup_path)

    if changes:
        with open(config_path, "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    print("Apply rescue elevated config")
    print(f"Config    : {config_path}")
    print(f"Backup    : {backup_path}")
    print(f"Sender    : {sender}")
    if changes:
        print("Changes:")
        for change in changes:
            print(f"- {change}")
    else:
        print("Changes:\n- none (config already matches validated rescue shape)")


if __name__ == "__main__":
    main()
